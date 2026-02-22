"""
弱命令处理器 - 处理自然语言触发的迭代请求

支持的自然语言模式：
- "麦麦帮我优化代码"
- "帮我改一下XX文件"
- "重构一下message_router"
- "修复bug"
- "优化日志输出"
等等
"""

import re
from typing import Tuple, Optional
from src.plugin_system import BaseEventHandler, EventType
from src.common.logger import get_logger

from ..core.state import iteration_state

logger = get_logger("self_iterative_plugin.handlers.weak_command")


class WeakIterateHandler(BaseEventHandler):
    """
    弱命令处理器 - 通过自然语言触发迭代流程
    
    监听用户消息，当检测到迭代相关的自然语言表达时，
    自动触发迭代流程，而无需使用 /iterate 命令。
    """
    
    event_type = EventType.POST_LLM  # 在LLM调用前处理
    handler_name = "weak_iterate_handler"
    handler_description = "通过自然语言触发自我迭代流程"
    weight = 50  # 中等权重，在其他处理器之后
    intercept_message = False  # 不拦截消息，只是触发迭代提示
    
    # 自然语言触发模式（正则表达式）
    WEAK_PATTERNS = [
        # 优化类
        r"(?:麦麦|mai|麦麦)?.*(?:帮我|帮我)?.*(?:优化|改进|完善|重构|修改|调整|更新|升级).*(?:代码|文件|模块|功能|逻辑|输出|日志)",
        r"(?:麦麦|mai|麦麦)?.*(?:优化|改进|完善|重构|修改|调整|更新|升级).*(?:代码|文件|模块|功能|逻辑|输出|日志)",
        
        # 修复类
        r"(?:麦麦|mai|麦麦)?.*(?:帮我|帮我)?.*(?:修复|解决|处理|调试|排查).*(?:bug|错误|问题|异常|报错|故障)",
        r"(?:麦麦|mai|麦麦)?.*(?:修复|解决|处理|调试|排查).*(?:bug|错误|问题|异常|报错|故障)",
        
        # 查看类
        r"(?:麦麦|mai|麦麦)?.*(?:帮我|帮我)?.*(?:查看|检查|分析|看看|瞅瞅).*(?:代码|文件|模块)",
        r"(?:麦麦|mai|麦麦)?.*(?:查看|检查|分析|看看|瞅瞅).*(?:代码|文件|模块)",
        
        # 具体文件操作
        r"(?:麦麦|mai|麦麦)?.*(?:帮我|帮我)?.*(?:改|修|调|写|加|删).*(?:src/|plugins/|config/|\.py|\.json|\.toml|\.yaml)",
        r"(?:麦麦|mai|麦麦)?.*(?:改|修|调|写|加|删).*(?:src/|plugins/|config/|\.py|\.json|\.toml|\.yaml)",
        
        # 迭代相关
        r"(?:麦麦|mai|麦麦)?.*(?:迭代|自优化|自我改进|自我完善)",
        
        # 简洁模式
        r"^(?:优化|改进|重构|修复|修改|调整|更新).*(?:代码|文件|模块|功能|bug|问题|输出|日志)",
    ]
    
    # 排除模式（避免误触发）
    EXCLUDE_PATTERNS = [
        r"^/",  # 排除命令
        r"^(?:iterate|approve|reject|diff|status|rollback|backups)",  # 排除英文命令
        r"^(?:迭代|审核|差异|状态|回滚|备份)",  # 排除中文命令
        r".*(?:不要|别|不用|无需).*(?:优化|修改|重构|修复)",  # 排除否定语气
        r".*(?:已经|已|早就).*(?:优化|修改|重构|修复)",  # 排除完成语气
    ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plugin_config = kwargs.get("plugin_config", {})
    
    def _is_enabled(self) -> bool:
        """检查弱命令功能是否启用"""
        return self.plugin_config.get("features", {}).get("enable_weak_command", True)
    
    def _is_weak_command(self, text: str) -> bool:
        """
        检查文本是否是弱命令
        
        Args:
            text: 用户输入文本
            
        Returns:
            bool: 是否是弱命令
        """
        if not text:
            return False
        
        text = text.strip().lower()
        
        # 先检查排除模式
        for pattern in self.EXCLUDE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return False
        
        # 检查触发模式
        for pattern in self.WEAK_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def _extract_target(self, text: str) -> Optional[str]:
        """
        从弱命令中提取目标
        
        Args:
            text: 用户输入文本
            
        Returns:
            Optional[str]: 提取的目标，如果没有则返回None
        """
        # 尝试提取文件路径
        file_patterns = [
            r"(src/[\w/]+\.py)",
            r"(plugins/[\w/]+\.py)",
            r"(config/[\w/]+\.(?:toml|json|yaml))",
            r"([\w_]+\.py)",
        ]
        
        for pattern in file_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        # 尝试提取模块名
        module_patterns = [
            r"(?:优化|改进|重构|修改|调整|更新|修复).*(?:模块|功能|逻辑)\s*[:：]?\s*(\w+)",
            r"(\w+)\s*(?:模块|功能|逻辑).*(?:优化|改进|重构|修改|调整|更新|修复)",
        ]
        
        for pattern in module_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    async def execute(self, message) -> Tuple[bool, bool, Optional[str], None, None]:
        """
        执行弱命令检测
        
        Args:
            message: 消息对象
            
        Returns:
            Tuple[是否继续, 是否成功, 消息, None, None]
        """
        try:
            # 检查功能是否启用
            if not self._is_enabled():
                return True, True, "弱命令已禁用", None, None
            
            # 基础验证
            if not message:
                logger.debug("[WeakIterate] 无消息对象，跳过")
                return True, True, "无消息对象", None, None
            
            # 获取消息文本
            text = ""
            if hasattr(message, 'plain_text') and message.plain_text:
                text = message.plain_text
            elif hasattr(message, 'message') and message.message:
                text = str(message.message)
            elif hasattr(message, 'raw_message') and message.raw_message:
                text = str(message.raw_message)
            
            if not text:
                logger.debug("[WeakIterate] 消息文本为空，跳过")
                return True, True, "消息文本为空", None, None
            
            # 检查是否是弱命令
            if not self._is_weak_command(text):
                return True, True, "非弱命令", None, None
            
            # 检查是否有待审核的迭代
            if iteration_state.is_pending():
                logger.debug("[WeakIterate] 已有待审核迭代，跳过")
                return True, True, "已有待审核迭代", None, None
            
            # 提取目标
            target = self._extract_target(text)
            
            # 构建提示消息
            hint_message = "🤖 **检测到迭代请求**\n\n"
            hint_message += f"💬 你的请求: \"{text[:50]}{'...' if len(text) > 50 else ''}\"\n\n"
            
            if target:
                hint_message += f"🎯 识别目标: `{target}`\n\n"
            
            hint_message += "💡 **我可以帮你:**\n"
            hint_message += "• 读取和分析代码文件\n"
            hint_message += "• 识别问题和优化点\n"
            hint_message += "• 生成修改后的代码\n"
            hint_message += "• 创建差异报告供你审核\n\n"
            hint_message += "📝 **你可以这样告诉我具体需求:**\n"
            hint_message += "• \"帮我优化src/plugins/example.py的性能\"\n"
            hint_message += "• \"修复message_router.py中的bug\"\n"
            hint_message += "• \"重构一下日志输出逻辑\"\n\n"
            hint_message += "⚠️ 修改完成后需要管理员审核通过才会生效。"
            
            logger.info(f"[WeakIterate] 检测到弱命令: {text[:50]}")
            
            # 返回提示消息，但不拦截原始消息
            return True, True, hint_message, None, None
            
        except Exception as e:
            logger.error(f"[WeakIterate] 处理弱命令时出错: {e}")
            return True, True, f"处理出错: {e}", None, None
