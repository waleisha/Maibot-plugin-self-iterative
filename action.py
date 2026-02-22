from typing import Tuple, Optional
from src.plugin_system.base.base_action import BaseAction
from src.plugin_system.base.component_types import ActionActivationType, ChatMode
from src.common.logger import get_logger

logger = get_logger("self_iterative_plugin.action")

class SelfIterateAction(BaseAction):
    """自我迭代与代码修改动作，智能检测用户的改代码需求"""

    action_name = "self_iterate"
    action_description = (
        "自我迭代与代码修改核心动作。"
        "当你需要读取源代码文件、分析bug、重构模块或优化自身系统代码时，必须调用此动作。"
        "包含代码读取、写入和终端执行能力。"
    )

    # 使用关键词唤醒，让 Planner 留意
    activation_type = ActionActivationType.KEYWORD
    mode_enable = ChatMode.ALL
    parallel_action = False

    activation_keywords = [
        "优化代码", "帮我优化", "改一下", "重构",
        "修复bug", "代码", "查看文件", "迭代"
    ]
    keyword_case_sensitive = False

    # 就像画图插件提取 description 一样，让大模型自动帮你把需求提取出来！
    action_parameters = {
        "target_path": "用户想查看或修改的目标文件路径或模块名，例如 'src/chat'（如果没有明确提，可为空）",
        "requirement": "用户的具体修改需求，例如 '优化一下逻辑，提升性能'"
    }

    action_require = [
        "当用户明确要求你修改、优化、重构、修复代码或查看项目文件时使用",
        "如果用户只是普通聊天，绝对不要使用此动作",
        "作为AI助手，你可以直接通过后续的工具链去读取和修改代码"
    ]

    async def execute(self) -> Tuple[bool, Optional[str]]:
        """执行动作"""
        target = self.action_data.get("target_path", "").strip()
        requirement = self.action_data.get("requirement", "").strip()

        # 1. 权限检查 (复用你之前的逻辑)
        # 如果需要鉴权，可以在这里通过 self.message 获取 user_id 判断

        # 2. 组装给用户的提示消息
        hint_message = "🤖 **已接收到代码迭代任务**\n\n"
        if target:
            hint_message += f"🎯 锁定目标: `{target}`\n"
        hint_message += f"💡 分析需求: {requirement}\n\n"
        hint_message += "正在启动自我迭代流程，即将调用代码工具进行分析..."

        # 发送提示消息给用户
        await self.send_text(hint_message)
        logger.info(f"[SelfIterateAction] 触发迭代，目标: {target}, 需求: {requirement}")

        # 3. 这里你可以选择通过代码直接调用你写的 ReadFileTool/SelfIterateTool
        # 或者仅仅作为桥梁，依靠后续的 LLM 自动处理。

        return True, "迭代流程已启动"