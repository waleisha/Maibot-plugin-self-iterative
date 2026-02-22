"""
自我迭代工具 - 让AI能够执行完整的代码迭代流程
"""

import os
import ast
import shutil
import difflib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple
from src.plugin_system import BaseTool, ToolParamType
from src.common.logger import get_logger

logger = get_logger("self_iterative_plugin.tools.iterator")


class SelfIterateTool(BaseTool):
    """
    自我迭代工具 - 执行完整的代码迭代流程
    
    功能:
    - 读取目标文件
    - 生成修改建议
    - 写入影子工作区
    - 生成差异报告
    - 等待人工审核
    """
    
    name = "self_iterate"
    description = """执行完整的自我迭代流程：读取文件 -> 分析 -> 生成修改 -> 写入影子区 -> 生成Diff报告。
    
    使用场景:
    - 优化现有代码逻辑
    - 修复bug
    - 添加新功能
    - 重构代码结构
    
    注意: 修改不会立即生效，需要管理员审核通过后才能应用。"""
    
    available_for_llm = True
    
    parameters = [
        ("target_path", ToolParamType.STRING, "要修改的目标文件路径（相对于MaiBot根目录）", True, None),
        ("modification_description", ToolParamType.STRING, "修改描述，说明要做什么样的修改", True, None),
        ("new_content", ToolParamType.STRING, "修改后的完整文件内容", True, None),
    ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plugin_dir = Path(__file__).parent.parent
        self.mai_bot_root = self._find_maibot_root()
        self.shadow_dir = self._get_shadow_dir()
        self.backup_dir = self._get_backup_dir()
    
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
    
    def _get_backup_dir(self) -> Path:
        """获取备份目录"""
        backup_path = self.get_config("iteration.backup_path", "storage/.backups")
        if os.path.isabs(backup_path):
            return Path(backup_path)
        return self.plugin_dir / backup_path
    
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
        abs_target = self.mai_bot_root / target_path
        abs_target = abs_target.resolve()
        
        allowed_paths = self._get_allowed_write_paths()
        in_whitelist = any(
            self._is_subpath(abs_target, allowed)
            for allowed in allowed_paths
        )
        if not in_whitelist:
            return False, f"目标路径不在允许的白名单内: {target_path}"
        
        forbidden_patterns = self.get_config("security.forbidden_patterns", [
            ".*\\.env.*", ".*token.*", ".*password.*", ".*secret.*",
            ".*credential.*", ".*api_key.*", ".*private.*"
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
    
    def _generate_diff(self, original: str, modified: str, file_path: str) -> str:
        """生成Git风格的diff报告"""
        original_lines = original.splitlines(keepends=True)
        modified_lines = modified.splitlines(keepends=True)
        
        # 确保每行都有换行符
        original_lines = [line if line.endswith('\n') else line + '\n' for line in original_lines]
        modified_lines = [line if line.endswith('\n') else line + '\n' for line in modified_lines]
        
        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm=''
        )
        
        return ''.join(diff)
    
    async def execute(self, function_args: Dict[str, Any]) -> Dict[str, Any]:
        """执行自我迭代流程"""
        target_path_str = function_args.get("target_path", "")
        modification_description = function_args.get("modification_description", "")
        new_content = function_args.get("new_content", "")
        
        try:
            target_path = Path(target_path_str)
            
            # 安全检查
            is_allowed, error_msg = self._is_write_allowed(target_path)
            if not is_allowed:
                logger.warning(f"[SelfIterateTool] 拒绝迭代: {error_msg}")
                return {
                    "name": self.name,
                    "content": f"❌ 迭代被拒绝: {error_msg}",
                    "success": False
                }
            
            # 读取原文件内容
            original_file_path = self.mai_bot_root / target_path
            original_content = ""
            if original_file_path.exists():
                try:
                    with open(original_file_path, 'r', encoding='utf-8', errors='replace') as f:
                        original_content = f.read()
                except Exception as e:
                    logger.warning(f"[SelfIterateTool] 读取原文件失败: {e}")
            
            # 语法检查
            enable_syntax_check = self.get_config("iteration.enable_syntax_check", True)
            if enable_syntax_check and target_path_str.endswith('.py'):
                syntax_ok, syntax_msg = self._syntax_check(new_content, target_path_str)
                if not syntax_ok:
                    logger.error(f"[SelfIterateTool] 语法检查失败: {syntax_msg}")
                    return {
                        "name": self.name,
                        "content": f"❌ 语法检查失败: {syntax_msg}\n\n请修复语法错误后再试。",
                        "success": False
                    }
            
            # 写入影子工作区
            shadow_path = self.shadow_dir / target_path
            shadow_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(shadow_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            # 生成差异报告
            enable_diff = self.get_config("iteration.enable_diff_report", True)
            diff_report = ""
            if enable_diff and original_content:
                diff_report = self._generate_diff(original_content, new_content, target_path_str)
            
            # 生成迭代ID
            iteration_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            logger.info(f"[SelfIterateTool] 迭代任务创建成功: {iteration_id}")
            
            # 构建结果
            result = f"✅ **自我迭代任务已创建**\n\n"
            result += f"🆔 迭代ID: `{iteration_id}`\n"
            result += f"📁 目标文件: `{target_path_str}`\n"
            result += f"📝 修改描述: {modification_description}\n"
            result += f"📏 原内容: {len(original_content)} 字符\n"
            result += f"📏 新内容: {len(new_content)} 字符\n"
            result += f"✅ {syntax_msg if enable_syntax_check else '语法检查已跳过'}\n\n"
            
            if diff_report:
                result += "📊 **差异报告:**\n"
                result += "```diff\n"
                # 限制diff长度
                if len(diff_report) > 1500:
                    result += diff_report[:1500] + "\n... (差异报告已截断)"
                else:
                    result += diff_report
                result += "\n```\n\n"
            
            result += "⏳ **等待管理员审核**\n"
            result += "管理员可以使用以下命令:\n"
            result += f"• `/approve` - 审核通过并应用修改\n"
            result += f"• `/reject` - 打回修改\n"
            result += f"• `/diff {target_path_str}` - 查看完整差异\n"
            
            return {
                "name": self.name,
                "content": result,
                "success": True,
                "iteration_id": iteration_id,
                "target_path": target_path_str,
                "shadow_path": str(shadow_path),
                "diff_report": diff_report,
                "original_length": len(original_content),
                "new_length": len(new_content)
            }
            
        except Exception as e:
            error_msg = f"执行自我迭代时发生错误: {str(e)}"
            logger.error(f"[SelfIterateTool] {error_msg}")
            return {
                "name": self.name,
                "content": f"❌ {error_msg}",
                "success": False
            }
