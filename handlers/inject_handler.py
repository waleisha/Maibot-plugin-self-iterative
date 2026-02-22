"""
LLM注入处理器 - 在LLM调用前将自我迭代工具信息注入到Prompt中

这是本插件的核心——让 LLM 感知到自我迭代工具的存在
"""

from typing import Tuple, Optional, Dict, Any
from src.plugin_system import BaseEventHandler, EventType
from src.common.logger import get_logger

logger = get_logger("self_iterative_plugin.handlers.inject")


class SelfIterativeInjectHandler(BaseEventHandler):
    """
    自我迭代工具注入处理器
    
    在 LLM 调用前，将自我迭代工具的信息注入到 Prompt 中。
    让机器人能够感知到自己有自我修改代码的能力，从而在合适的时机调用这些工具。

    注意：在 MaiCore 中，组装好 prompt 准备发给 LLM 之前的事件叫 POST_LLM
    """

    event_type = EventType.POST_LLM  # 修复：原为 PRE_LLM，在当前 MaiCore 版本中应为 POST_LLM
    handler_name = "self_iterative_inject_handler"
    handler_description = "将自我迭代工具信息注入 LLM Prompt"
    weight = 100  # 提高权重，确保在其他处理器之前执行
    intercept_message = False  # 不拦截消息，只是注入信息

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plugin_config = kwargs.get("plugin_config", {})

    async def execute(self, message) -> Tuple[bool, bool, Optional[str], None, None]:
        """
        执行注入

        Returns:
            Tuple[是否继续, 是否成功, 消息, None, None]
        """
        try:
            # 基础验证
            if not message:
                logger.debug("[SelfIterativeInject] 无消息对象，跳过注入")
                return True, True, "无消息对象", None, None

            # 检查是否有 llm_prompt 属性
            if not hasattr(message, "llm_prompt"):
                logger.debug("[SelfIterativeInject] 消息对象无 llm_prompt 属性，跳过注入")
                return True, True, "无 LLM prompt 属性", None, None

            # 检查插件是否启用
            enabled = self.plugin_config.get("plugin", {}).get("enabled", True)
            if not enabled:
                logger.debug("[SelfIterativeInject] 插件已禁用，跳过注入")
                return True, True, "插件已禁用", None, None

            # 检查是否启用工具注入
            enable_tools = self.plugin_config.get("features", {}).get("enable_tool_inject", True)
            if not enable_tools:
                logger.debug("[SelfIterativeInject] 工具注入已禁用")
                return True, True, "工具注入已禁用", None, None

            # 构建注入内容
            inject_content = self._build_inject_content()

            # 获取当前 prompt
            current_prompt = message.llm_prompt
            if not current_prompt:
                current_prompt = ""

            # 检查是否已经注入过（避免重复注入）
            if "【系统能力通知 - 自我迭代工具】" in current_prompt:
                logger.debug("[SelfIterativeInject] 已经注入过，跳过")
                return True, True, "已经注入过", None, None

            # 修改 Prompt - 在末尾添加注入内容
            new_prompt = current_prompt + "\n\n" + inject_content

            # 使用 modify_llm_prompt 方法
            if hasattr(message, 'modify_llm_prompt'):
                message.modify_llm_prompt(new_prompt, suppress_warning=True)
                logger.info("[SelfIterativeInject] 自我迭代工具信息已通过 modify_llm_prompt 注入")
            else:
                # 如果方法不存在，直接修改属性
                message.llm_prompt = new_prompt
                logger.info("[SelfIterativeInject] 自我迭代工具信息已直接注入 llm_prompt")

            return True, True, "自我迭代工具信息已注入", None, message

        except Exception as e:
            logger.error(f"[SelfIterativeInject] 注入失败: {e}")
            return True, False, f"注入失败: {str(e)}", None, message

    def _build_inject_content(self) -> str:
        """构建注入内容"""

        inject_content = """
【系统能力通知 - 自我迭代工具】

你拥有自我迭代和自我优化的能力！当用户提出以下类型的请求时，你可以调用相应的工具来完成任务：

📖 **可用工具:**

1. **read_file** - 读取源代码文件
   - 用途: 查看MaiBot框架或插件的当前代码实现
   - 参数: file_path (文件路径), offset (起始行), limit (读取行数)
   - 示例: 读取 src/plugins/example.py 的第1-100行

2. **write_file** - 写入源代码到影子工作区
   - 用途: 将修改后的代码写入等待审核的区域
   - 参数: target_path (目标路径), content (文件内容), append (是否追加)
   - 注意: 不会直接覆盖原文件，需要管理员审核

3. **execute_terminal** - 执行安全的系统命令
   - 用途: 执行pip install、git操作等安全命令
   - 参数: command (命令), timeout (超时), working_dir (工作目录)
   - 限制: 只能执行白名单内的命令

4. **self_iterate** - 执行完整的自我迭代流程
   - 用途: 一键完成读取、修改、生成Diff、等待审核的完整流程
   - 参数: target_path (目标路径), modification_description (修改描述), new_content (新内容)

🎯 **使用场景:**
- 用户说"优化一下你的XX功能" → 使用 read_file 查看代码，然后使用 self_iterate 提交修改
- 用户说"修复XX bug" → 读取相关文件，分析问题，提交修复
- 用户说"添加XX功能" → 查看现有代码结构，添加新功能
- 用户说"重构XX模块" → 分析代码，提交重构版本

⚠️ **重要提醒:**
- 所有修改都会进入影子工作区，不会立即生效
- 修改需要管理员审核通过后才能应用
- 每次修改前会自动备份原文件，支持一键回滚
- 请确保修改后的代码语法正确（会进行AST检查）

💡 **工作流程:**
1. 用户提出修改需求
2. 你使用工具读取相关代码
3. 分析并生成修改后的代码
4. 使用 self_iterate 或 write_file 提交修改
5. 通知用户修改已提交，等待审核
6. 管理员审核通过后，修改才会生效

【结束系统能力通知】
"""
        return inject_content.strip()


class SelfIterativePostHandler(BaseEventHandler):
    """
    自我迭代工具后置处理器 (AFTER_LLM版本)

    在 LLM 调用后处理工具调用结果
    """

    event_type = EventType.AFTER_LLM  # 修复：原为 POST_LLM，在当前 MaiCore 版本中应为 AFTER_LLM
    handler_name = "self_iterative_post_handler"
    handler_description = "处理自我迭代工具调用结果"
    weight = 10
    intercept_message = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plugin_config = kwargs.get("plugin_config", {})

    async def execute(self, message) -> Tuple[bool, bool, Optional[str], None, None]:
        """执行后置处理"""
        # 可以在这里处理工具调用的结果
        # 例如：记录工具调用日志、更新状态等
        return True, True, "后置处理完成", None, None