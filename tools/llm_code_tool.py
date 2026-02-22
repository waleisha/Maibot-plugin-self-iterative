"""
LLM代码生成工具 - 使用独立LLM模型生成代码修改

这个工具允许AI直接调用配置的独立LLM模型来生成代码修改，
而不需要AI自己生成修改后的代码。
"""

import os
from pathlib import Path
from typing import Dict, Any, List, Tuple
from src.plugin_system import BaseTool, ToolParamType
from src.common.logger import get_logger

from ..core.llm_client import get_llm_client

logger = get_logger("self_iterative_plugin.tools.llm_code")


class LLMCodeGenerateTool(BaseTool):
    """
    LLM代码生成工具
    
    使用配置的独立LLM模型（Claude、Gemini、Kimi等）来生成代码修改。
    这个工具让AI可以调用更强大的模型来生成高质量的代码。
    
    使用场景:
    - 复杂的代码重构
    - Bug修复
    - 功能添加
    - 代码优化
    """
    
    name = "llm_generate_code"
    description = """使用独立LLM模型生成代码修改。当你需要修改代码但不确定如何修改时，可以使用这个工具让专业的代码模型来生成修改。

使用场景:
- 复杂的代码重构
- Bug修复
- 添加新功能
- 代码优化

注意: 这个工具会调用配置的独立LLM模型（如Claude、Gemini等），可能需要额外的API调用时间。"""
    
    available_for_llm = True
    
    parameters = [
        ("file_path", ToolParamType.STRING, "要修改的文件路径（相对于MaiBot根目录）", True, None),
        ("task_description", ToolParamType.STRING, "修改任务描述，例如：优化日志输出、修复第50行的bug等", True, None),
        ("offset", ToolParamType.INTEGER, "起始行号（从1开始），默认读取整个文件", False, 1),
        ("limit", ToolParamType.INTEGER, "最多读取行数，默认读取500行", False, 500),
    ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plugin_dir = Path(__file__).parent.parent
        self.mai_bot_root = self._find_maibot_root()
        self._llm_client = None
    
    def _find_maibot_root(self) -> Path:
        """查找MaiBot根目录"""
        current = self.plugin_dir
        while current.parent != current:
            if (current / "bot.py").exists() or (current / "main.py").exists():
                return current
            current = current.parent
        return self.plugin_dir.parent.parent
    
    def _get_llm_client(self):
        """获取LLM客户端"""
        if self._llm_client is None:
            # 构建配置字典
            config = {
                "plugin": {"enabled": True},
                "llm": {
                    "provider": self.get_config("llm.provider", "default"),
                    "temperature": self.get_config("llm.temperature", 0.3),
                    "max_tokens": self.get_config("llm.max_tokens", 4096),
                    "openai": {
                        "model": self.get_config("llm.openai.model", "gpt-4o"),
                        "api_key": self.get_config("llm.openai.api_key", ""),
                        "base_url": self.get_config("llm.openai.base_url", "https://api.openai.com/v1"),
                    },
                    "anthropic": {
                        "model": self.get_config("llm.anthropic.model", "claude-3-5-sonnet-20241022"),
                        "api_key": self.get_config("llm.anthropic.api_key", ""),
                        "base_url": self.get_config("llm.anthropic.base_url", "https://api.anthropic.com/v1"),
                    },
                    "google": {
                        "model": self.get_config("llm.google.model", "gemini-2.0-flash-exp"),
                        "api_key": self.get_config("llm.google.api_key", ""),
                    },
                    "moonshot": {
                        "model": self.get_config("llm.moonshot.model", "kimi-latest"),
                        "api_key": self.get_config("llm.moonshot.api_key", ""),
                        "base_url": self.get_config("llm.moonshot.base_url", "https://api.moonshot.cn/v1"),
                    },
                    "deepseek": {
                        "model": self.get_config("llm.deepseek.model", "deepseek-coder"),
                        "api_key": self.get_config("llm.deepseek.api_key", ""),
                        "base_url": self.get_config("llm.deepseek.base_url", "https://api.deepseek.com/v1"),
                    },
                },
            }
            self._llm_client = get_llm_client(config)
        return self._llm_client
    
    def _get_allowed_read_paths(self) -> List[Path]:
        """获取允许的读取路径列表"""
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
        abs_target = self.mai_bot_root / target_path
        abs_target = abs_target.resolve()
        
        allowed_paths = self._get_allowed_read_paths()
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
    
    async def execute(self, function_args: Dict[str, Any]) -> Dict[str, Any]:
        """执行代码生成"""
        file_path_str = function_args.get("file_path", "")
        task_description = function_args.get("task_description", "")
        offset = function_args.get("offset", 1)
        limit = function_args.get("limit", 500)
        
        try:
            # 安全检查
            is_allowed, error_msg = self._is_path_allowed(Path(file_path_str))
            if not is_allowed:
                logger.warning(f"[LLMCodeGenerateTool] 拒绝读取: {error_msg}")
                return {
                    "name": self.name,
                    "content": f"❌ 读取被拒绝: {error_msg}",
                    "success": False
                }
            
            # 读取文件
            file_path = self.mai_bot_root / file_path_str
            if not file_path.exists():
                return {
                    "name": self.name,
                    "content": f"❌ 文件不存在: {file_path_str}",
                    "success": False
                }
            
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
            
            total_lines = len(lines)
            start_idx = max(0, offset - 1)
            end_idx = min(total_lines, start_idx + limit)
            selected_lines = lines[start_idx:end_idx]
            code = ''.join(selected_lines)
            
            logger.info(f"[LLMCodeGenerateTool] 读取文件: {file_path_str} ({total_lines}行)")
            
            # 使用LLM生成修改
            llm_client = self._get_llm_client()
            
            provider = self.get_config("llm.provider", "default")
            logger.info(f"[LLMCodeGenerateTool] 使用LLM模型: {provider}")
            
            success, new_code = await llm_client.analyze_code(
                file_path=file_path_str,
                code=code,
                task_description=task_description
            )
            
            if not success:
                return {
                    "name": self.name,
                    "content": f"❌ 代码生成失败: {new_code}",
                    "success": False
                }
            
            # 生成修改描述
            description = await llm_client.generate_diff_description(code, new_code)
            
            logger.info(f"[LLMCodeGenerateTool] 代码生成成功")
            
            return {
                "name": self.name,
                "content": f"✅ **代码生成成功**\n\n📝 **修改描述**: {description}\n\n📏 **原代码**: {len(code)} 字符\n📏 **新代码**: {len(new_code)} 字符\n\n💡 **下一步**: 你可以使用 `self_iterate` 工具提交这个修改:\n```json\n{{\n  \"target_path\": \"{file_path_str}\",\n  \"modification_description\": \"{description}\",\n  \"new_content\": \"...生成的代码...\"\n}}\n```",
                "success": True,
                "target_path": file_path_str,
                "modification_description": description,
                "new_content": new_code,
                "original_length": len(code),
                "new_length": len(new_code)
            }
            
        except Exception as e:
            error_msg = f"代码生成时发生错误: {str(e)}"
            logger.error(f"[LLMCodeGenerateTool] {error_msg}")
            return {
                "name": self.name,
                "content": f"❌ {error_msg}",
                "success": False
            }
