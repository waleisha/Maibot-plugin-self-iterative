"""
源码读取工具 - 让大模型能够查看当前框架或插件的代码实现
"""

import os
from pathlib import Path
from typing import Dict, Any, List, Tuple
from src.plugin_system import BaseTool, ToolParamType
from src.common.logger import get_logger

logger = get_logger("self_iterative_plugin.tools.reader")


class ReadFileTool(BaseTool):
    """
    源码读取工具 - 安全读取白名单内的源代码
    
    安全特性:
    - 目录白名单控制，防止读取敏感文件
    - 文件黑名单过滤，禁止访问 .env, token 等敏感文件
    - 支持行号范围读取，避免一次性加载大文件
    """
    
    name = "read_file"
    description = "读取MaiBot框架或插件的源代码文件。支持Python、JSON、TOML、Markdown等文本文件。必须在白名单路径内。"
    available_for_llm = True
    
    parameters = [
        ("file_path", ToolParamType.STRING, "要读取的文件路径（相对于MaiBot根目录，如 'src/plugins/plugin.py'）", True, None),
        ("offset", ToolParamType.INTEGER, "起始行号（从1开始），默认从第1行开始", False, 1),
        ("limit", ToolParamType.INTEGER, "最多读取行数，默认读取100行", False, 100),
    ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plugin_dir = Path(__file__).parent.parent
        self.mai_bot_root = self._find_maibot_root()
    
    def _find_maibot_root(self) -> Path:
        """查找MaiBot根目录"""
        current = self.plugin_dir
        while current.parent != current:
            if (current / "bot.py").exists() or (current / "main.py").exists():
                return current
            current = current.parent
        # 如果找不到，返回插件目录的上两级
        return self.plugin_dir.parent.parent
    
    def _get_allowed_paths(self) -> List[Path]:
        """获取允许读取的路径列表"""
        allowed = self.get_config("security.allowed_read_paths", [
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
    
    def _is_path_allowed(self, target_path: Path) -> Tuple[bool, str]:
        """检查目标路径是否允许读取"""
        # 解析为绝对路径
        abs_target = self.mai_bot_root / target_path
        abs_target = abs_target.resolve()
        
        # 检查是否在白名单内
        allowed_paths = self._get_allowed_paths()
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
    
    async def execute(self, function_args: Dict[str, Any]) -> Dict[str, Any]:
        """执行文件读取"""
        file_path_str = function_args.get("file_path", "")
        offset = function_args.get("offset", 1)
        limit = function_args.get("limit", 100)
        
        try:
            # 解析路径
            file_path = self.mai_bot_root / file_path_str
            file_path = file_path.resolve()
            
            # 安全检查
            is_allowed, error_msg = self._is_path_allowed(Path(file_path_str))
            if not is_allowed:
                logger.warning(f"[ReadFileTool] 拒绝读取文件: {error_msg}")
                return {
                    "name": self.name,
                    "content": f"❌ 读取被拒绝: {error_msg}",
                    "success": False
                }
            
            # 检查文件是否存在
            if not file_path.exists():
                return {
                    "name": self.name,
                    "content": f"❌ 文件不存在: {file_path_str}",
                    "success": False
                }
            
            # 检查是否是文件
            if not file_path.is_file():
                return {
                    "name": self.name,
                    "content": f"❌ 路径不是文件: {file_path_str}",
                    "success": False
                }
            
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
            
            total_lines = len(lines)
            
            # 计算读取范围
            start_idx = max(0, offset - 1)
            end_idx = min(total_lines, start_idx + limit)
            
            # 提取指定范围的行
            selected_lines = lines[start_idx:end_idx]
            content = ''.join(selected_lines)
            
            # 格式化输出
            result = f"📄 文件: {file_path_str}\n"
            result += f"📊 总行数: {total_lines}, 显示行: {start_idx + 1} - {end_idx}\n"
            result += "=" * 50 + "\n"
            result += content
            
            if end_idx < total_lines:
                result += f"\n... (还有 {total_lines - end_idx} 行未显示)"
            
            logger.info(f"[ReadFileTool] 成功读取文件: {file_path_str} ({total_lines}行)")
            return {
                "name": self.name,
                "content": result,
                "success": True,
                "file_path": str(file_path),
                "total_lines": total_lines,
                "displayed_lines": end_idx - start_idx
            }
            
        except Exception as e:
            error_msg = f"读取文件时发生错误: {str(e)}"
            logger.error(f"[ReadFileTool] {error_msg}")
            return {
                "name": self.name,
                "content": f"❌ {error_msg}",
                "success": False
            }
