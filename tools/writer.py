"""
源码写入工具 - 将大模型修改后的代码写入影子工作区
"""

import os
import ast
from pathlib import Path
from typing import Dict, Any, List, Tuple
from src.plugin_system import BaseTool, ToolParamType
from src.common.logger import get_logger

logger = get_logger("self_iterative_plugin.tools.writer")


class WriteFileTool(BaseTool):
    """
    源码写入工具 - 将修改后的代码写入影子工作区
    
    安全特性:
    - 绝不直接覆盖原文件
    - 所有写入都重定向到影子工作区
    - 写入后自动进行AST语法检查
    """
    
    name = "write_file"
    description = "将修改后的代码写入影子工作区，等待人工审核。支持Python、JSON、TOML等文本文件。写入前会进行AST语法校验。"
    available_for_llm = True
    
    parameters = [
        ("target_path", ToolParamType.STRING, "目标文件路径（相对于MaiBot根目录，如 'src/plugins/plugin.py'）", True, None),
        ("content", ToolParamType.STRING, "要写入的文件内容", True, None),
        ("append", ToolParamType.BOOLEAN, "是否追加模式，默认为False（覆盖）", False, False),
    ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plugin_dir = Path(__file__).parent.parent
        self.mai_bot_root = self._find_maibot_root()
        self.shadow_dir = self._get_shadow_dir()
    
    def _find_maibot_root(self) -> Path:
        """查找MaiBot根目录"""
        current = self.plugin_dir
        while current.parent != current:
            if (current / "bot.py").exists() or (current / "main.py").exists():
                return current
            current = current.parent
        return self.plugin_dir.parent.parent
    
    def _get_shadow_dir(self) -> Path:
        """获取影子工作区目录"""
        shadow_path = self.get_config("iteration.shadow_workspace_path", "storage/.shadow")
        if os.path.isabs(shadow_path):
            return Path(shadow_path)
        return self.plugin_dir / shadow_path
    
    def _get_allowed_write_paths(self) -> List[Path]:
        """获取允许的写入路径列表"""
        allowed = self.get_config("security.allowed_write_paths", [
            "src",
            "plugins",
            "maibot_plugin_self_iterative"
        ])
        paths = []
        for path_str in allowed:
            if os.path.isabs(path_str):
                paths.append(Path(path_str))
            else:
                paths.append(self.mai_bot_root / path_str)
        return paths
    
    def _is_write_allowed(self, target_path: Path) -> Tuple[bool, str]:
        """检查目标路径是否允许写入"""
        # 解析为绝对路径
        abs_target = self.mai_bot_root / target_path
        abs_target = abs_target.resolve()
        
        # 检查是否在写入白名单内
        allowed_paths = self._get_allowed_write_paths()
        in_whitelist = any(
            self._is_subpath(abs_target, allowed)
            for allowed in allowed_paths
        )
        if not in_whitelist:
            return False, f"目标路径不在允许的白名单内: {target_path}"
        
        # 检查禁止模式
        forbidden_patterns = self.get_config("security.forbidden_patterns", [
            ".*\\.env.*",
            ".*token.*",
            ".*password.*",
            ".*secret.*",
            ".*credential.*",
            ".*api_key.*",
            ".*private.*"
        ])
        
        import re
        target_str = str(abs_target).lower()
        for pattern in forbidden_patterns:
            try:
                if re.match(pattern, target_str, re.IGNORECASE):
                    return False, f"目标路径匹配禁止模式: {pattern}"
            except re.error:
                continue
        
        return True, ""
    
    def _is_subpath(self, path: Path, potential_parent: Path) -> bool:
        """检查path是否是potential_parent的子路径"""
        try:
            path.relative_to(potential_parent)
            return True
        except ValueError:
            return False
    
    def _syntax_check(self, content: str, file_path: str) -> Tuple[bool, str]:
        """对Python代码进行AST语法检查"""
        if not file_path.endswith('.py'):
            return True, "非Python文件，跳过语法检查"
        
        try:
            ast.parse(content)
            return True, "语法检查通过"
        except SyntaxError as e:
            return False, f"语法错误: 第{e.lineno}行 - {e.msg}"
        except Exception as e:
            return False, f"语法检查异常: {str(e)}"
    
    async def execute(self, function_args: Dict[str, Any]) -> Dict[str, Any]:
        """执行文件写入"""
        target_path_str = function_args.get("target_path", "")
        content = function_args.get("content", "")
        append = function_args.get("append", False)
        
        try:
            # 解析目标路径
            target_path = Path(target_path_str)
            
            # 安全检查
            is_allowed, error_msg = self._is_write_allowed(target_path)
            if not is_allowed:
                logger.warning(f"[WriteFileTool] 拒绝写入文件: {error_msg}")
                return {
                    "name": self.name,
                    "content": f"❌ 写入被拒绝: {error_msg}",
                    "success": False
                }
            
            # 语法检查
            enable_syntax_check = self.get_config("iteration.enable_syntax_check", True)
            if enable_syntax_check and target_path_str.endswith('.py'):
                syntax_ok, syntax_msg = self._syntax_check(content, target_path_str)
                if not syntax_ok:
                    logger.error(f"[WriteFileTool] 语法检查失败: {syntax_msg}")
                    return {
                        "name": self.name,
                        "content": f"❌ 语法检查失败: {syntax_msg}\n\n请修复语法错误后再试。",
                        "success": False
                    }
            
            # 构建影子文件路径
            shadow_path = self.shadow_dir / target_path
            shadow_path = shadow_path.resolve()
            
            # 确保影子目录存在
            shadow_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入影子文件
            mode = 'a' if append else 'w'
            with open(shadow_path, mode, encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"[WriteFileTool] 成功写入影子文件: {shadow_path}")
            
            # 计算相对路径用于显示
            try:
                rel_path = shadow_path.relative_to(self.mai_bot_root)
            except ValueError:
                rel_path = shadow_path
            
            return {
                "name": self.name,
                "content": f"✅ 文件已写入影子工作区\n\n📁 影子路径: {rel_path}\n📝 目标文件: {target_path_str}\n📏 内容长度: {len(content)} 字符\n✅ {syntax_msg if enable_syntax_check else '语法检查已跳过'}",
                "success": True,
                "shadow_path": str(shadow_path),
                "target_path": target_path_str,
                "content_length": len(content)
            }
            
        except Exception as e:
            error_msg = f"写入文件时发生错误: {str(e)}"
            logger.error(f"[WriteFileTool] {error_msg}")
            return {
                "name": self.name,
                "content": f"❌ {error_msg}",
                "success": False
            }
