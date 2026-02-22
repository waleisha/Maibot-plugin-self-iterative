"""
命令处理器 - 处理各种管理命令

所有命令都设置了 intercept_message = True，确保命令被正确拦截处理
"""

import os
import re
import shutil
from pathlib import Path
from datetime import datetime
from typing import Tuple, List, Dict, Any
from src.plugin_system import BaseCommand
from src.common.logger import get_logger

from ..core.state import iteration_state
from ..core.differ import DiffGenerator
from ..core.patcher import patcher

logger = get_logger("self_iterative_plugin.handlers.command")


def get_user_id_from_message(message) -> str:
    """
    从消息对象中安全地获取用户ID
    兼容不同版本的MaiBot消息对象结构
    """
    if not message:
        return "unknown"

    try:
        # 方式1: 直接获取 (旧版本)
        if hasattr(message, 'user_id') and message.user_id:
            return str(message.user_id)

        # 方式2: 通过 message_info.user_info.user_id (新版本)
        if hasattr(message, 'message_info') and message.message_info:
            if hasattr(message.message_info, 'user_info') and message.message_info.user_info:
                if hasattr(message.message_info.user_info, 'user_id'):
                    return str(message.message_info.user_info.user_id)

        # 方式3: 通过 message_base_info (某些版本)
        if hasattr(message, 'message_base_info') and message.message_base_info:
            user_id = message.message_base_info.get('user_id')
            if user_id:
                return str(user_id)

        # 方式4: 通过 sender 属性
        if hasattr(message, 'sender') and message.sender:
            if hasattr(message.sender, 'user_id'):
                return str(message.sender.user_id)

        # 方式5: 通过 raw_message 解析
        if hasattr(message, 'raw_message') and message.raw_message:
            # 尝试从原始消息中解析用户ID
            pass

        logger.warning(f"[get_user_id] 无法从消息对象获取用户ID，消息类型: {type(message)}")
        return "unknown"

    except Exception as e:
        logger.warning(f"[get_user_id] 获取用户ID时出错: {e}")
        return "unknown"


class IterateCommand(BaseCommand):
    """
    触发自我迭代命令（强命令）
    用法: /iterate [目标文件或描述]
    示例: /iterate 优化message_router.py的日志输出
    
    注意: 这个命令只是触发迭代流程，实际的代码修改由AI调用工具完成
    """

    command_name = "iterate"
    command_description = "触发自我迭代流程，让AI开始分析和修改代码"
    command_pattern = r"^/iterate(?:\s+(?P<target>.+))?$"
    command_help = "触发自我迭代流程。用法: /iterate [目标文件或描述]"
    command_examples = [
        "/iterate",
        "/iterate 优化日志输出",
        "/iterate src/plugins/message_router.py"
    ]
    intercept_message = True  # 拦截消息，不让AI当作普通对话处理

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
        return self.plugin_dir.parent.parent

    def _is_admin(self, user_id: str) -> bool:
        """检查用户是否是管理员"""
        admin_qqs = self.get_config("security.admin_qqs", [])
        if not admin_qqs:
            return True
        return str(user_id) in [str(qq) for qq in admin_qqs]

    async def execute(self) -> Tuple[bool, str, bool]:
        """执行迭代命令"""
        # 检查权限 - 使用修复后的用户ID获取方法
        user_id = get_user_id_from_message(self.message)

        if not self._is_admin(user_id):
            return True, "❌ 你没有权限执行此操作，请联系管理员。", True

        # 获取目标参数
        target = ""
        if hasattr(self, 'matched_groups') and self.matched_groups:
            target = self.matched_groups.get("target", "").strip()

        # 检查是否有待审核的迭代
        if iteration_state.is_pending():
            return True, (
                f"⏳ 当前有等待审核的迭代任务 (ID: {iteration_state.iteration_id})\n"
                f"📁 目标: {iteration_state.target_path}\n\n"
                f"请先处理当前任务:\n"
                f"• /approve - 审核通过\n"
                f"• /reject - 打回修改"
            ), True

        # 构建提示消息
        message = "🚀 **自我迭代流程已启动**\n\n"

        if target:
            message += f"🎯 目标: {target}\n\n"

        message += "💡 **你可以这样跟我说:**\n"
        message += "• \"帮我优化一下XX模块的代码\"\n"
        message += "• \"查看一下src/plugins/example.py，修复里面的bug\"\n"
        message += "• \"重构一下message_router.py，让代码更清晰\"\n\n"
        message += "🤖 AI会自动调用工具来读取、分析和修改代码。\n"
        message += "⚠️ 修改完成后需要管理员审核通过才会生效。"

        logger.info(f"[IterateCommand] 用户 {user_id} 启动了迭代流程")
        return True, message, True


class ApproveCommand(BaseCommand):
    """
    审核通过命令 - 应用影子工作区的修改
    用法: /approve 或 /同意 或 /通过
    """

    command_name = "approve"
    command_description = "审核通过并应用影子工作区的修改"
    command_pattern = r"^/(approve|同意|通过|确认|apply)$"
    command_help = "审核通过并应用修改。用法: /approve"
    command_examples = ["/approve", "/同意", "/通过"]
    intercept_message = True  # 拦截消息

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plugin_dir = Path(__file__).parent.parent
        self.mai_bot_root = self._find_maibot_root()
        self.shadow_dir = self._get_shadow_dir()
        self.backup_dir = self._get_backup_dir()

    def _find_maibot_root(self) -> Path:
        current = self.plugin_dir
        while current.parent != current:
            if (current / "bot.py").exists() or (current / "main.py").exists():
                return current
            current = current.parent
        return self.plugin_dir.parent.parent

    def _get_shadow_dir(self) -> Path:
        shadow_path = self.get_config("iteration.shadow_workspace_path", "storage/.shadow")
        if os.path.isabs(shadow_path):
            return Path(shadow_path)
        return self.plugin_dir / shadow_path

    def _get_backup_dir(self) -> Path:
        backup_path = self.get_config("iteration.backup_path", "storage/.backups")
        if os.path.isabs(backup_path):
            return Path(backup_path)
        return self.plugin_dir / backup_path

    def _is_admin(self, user_id: str) -> bool:
        """检查用户是否是管理员"""
        admin_qqs = self.get_config("security.admin_qqs", [])
        if not admin_qqs:
            return True
        return str(user_id) in [str(qq) for qq in admin_qqs]

    async def execute(self) -> Tuple[bool, str, bool]:
        """执行审核通过操作"""
        user_id = get_user_id_from_message(self.message)

        # 检查权限
        if not self._is_admin(user_id):
            return True, "❌ 你没有权限执行此操作，请联系管理员。", True

        # 检查是否有待审核的迭代
        if not iteration_state.is_pending():
            return True, "ℹ️ 当前没有等待审核的迭代请求。", True

        try:
            applied_files = []
            backup_files = []

            # 应用所有待处理的文件
            for target_path_str, shadow_path_str in iteration_state.pending_files.items():
                target_path = self.mai_bot_root / target_path_str
                shadow_path = Path(shadow_path_str)

                # 备份原文件
                if target_path.exists():
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    relative_path = target_path_str.replace(os.sep, '_')
                    backup_name = f"{relative_path}.{timestamp}.bak"
                    backup_path = self.backup_dir / backup_name
                    backup_path.parent.mkdir(parents=True, exist_ok=True)

                    shutil.copy2(target_path, backup_path)
                    backup_files.append(str(backup_path))

                # 确保目标目录存在
                target_path.parent.mkdir(parents=True, exist_ok=True)

                # 写入目标文件
                if shadow_path.exists():
                    shutil.copy2(shadow_path, target_path)
                    applied_files.append(target_path_str)
                    logger.info(f"[ApproveCommand] 已应用修改: {target_path}")
                else:
                    logger.warning(f"[ApproveCommand] 影子文件不存在: {shadow_path}")

            # 清理影子文件
            for shadow_path_str in iteration_state.pending_files.values():
                try:
                    Path(shadow_path_str).unlink(missing_ok=True)
                except Exception as e:
                    logger.warning(f"[ApproveCommand] 清理影子文件失败: {e}")

            # 更新状态
            iteration_state.approve()
            iteration_state.apply()

            # 构建结果消息
            message = "✅ **修改已应用**\n\n"
            message += f"🆔 迭代ID: {iteration_state.iteration_id}\n"
            message += f"👤 审核者: {user_id}\n"
            message += f"🕐 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

            if applied_files:
                message += "📁 **已应用的文件:**\n"
                for f in applied_files:
                    message += f"• {f}\n"

            if backup_files:
                message += "\n💾 **备份文件:**\n"
                for f in backup_files:
                    message += f"• {f}\n"

            message += "\n⚠️ **注意:** 部分修改可能需要重启MaiBot才能生效。"
            message += "\n💡 使用 `/rollback` 可以回滚到之前的版本。"

            logger.info(f"[ApproveCommand] 迭代 {iteration_state.iteration_id} 已审核通过")

            # 重置状态
            iteration_state.reset()

            return True, message, True

        except Exception as e:
            iteration_state.set_error(str(e))
            error_msg = f"❌ 应用修改时发生错误: {str(e)}"
            logger.error(f"[ApproveCommand] {error_msg}")
            return True, error_msg, True


class RejectCommand(BaseCommand):
    """
    打回修改命令 - 拒绝并清理影子工作区
    用法: /reject 或 /拒绝 或 /打回 或 /不同意
    """

    command_name = "reject"
    command_description = "打回修改请求，清理影子工作区"
    command_pattern = r"^/(reject|拒绝|打回|不同意|cancel)$"
    command_help = "打回修改请求。用法: /reject"
    command_examples = ["/reject", "/拒绝", "/打回"]
    intercept_message = True  # 拦截消息

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plugin_dir = Path(__file__).parent.parent

    def _is_admin(self, user_id: str) -> bool:
        """检查用户是否是管理员"""
        admin_qqs = self.get_config("security.admin_qqs", [])
        if not admin_qqs:
            return True
        return str(user_id) in [str(qq) for qq in admin_qqs]

    async def execute(self) -> Tuple[bool, str, bool]:
        """执行打回操作"""
        user_id = get_user_id_from_message(self.message)

        # 检查权限
        if not self._is_admin(user_id):
            return True, "❌ 你没有权限执行此操作，请联系管理员。", True

        # 检查是否有待审核的迭代
        if not iteration_state.is_pending():
            return True, "ℹ️ 当前没有等待审核的迭代请求。", True

        try:
            # 清理影子文件
            deleted_files = []
            for shadow_path_str in iteration_state.pending_files.values():
                try:
                    Path(shadow_path_str).unlink(missing_ok=True)
                    deleted_files.append(shadow_path_str)
                except Exception as e:
                    logger.warning(f"[RejectCommand] 清理影子文件失败: {e}")

            # 更新状态
            iteration_id = iteration_state.iteration_id
            iteration_state.reject()

            message = "🚫 **修改已打回**\n\n"
            message += f"🆔 迭代ID: {iteration_id}\n"
            message += f"👤 操作者: {user_id}\n"
            message += f"🕐 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

            if deleted_files:
                message += f"🗑️ 已清理 {len(deleted_files)} 个影子文件\n"

            message += "\n💡 你可以重新发起迭代请求。"

            logger.info(f"[RejectCommand] 迭代 {iteration_id} 已打回")
            return True, message, True

        except Exception as e:
            error_msg = f"❌ 打回修改时发生错误: {str(e)}"
            logger.error(f"[RejectCommand] {error_msg}")
            return True, error_msg, True


class DiffCommand(BaseCommand):
    """
    查看差异命令 - 显示影子工作区与原始文件的差异
    用法: /diff [文件路径]
    示例: /diff src/plugins/plugin.py
    """

    command_name = "diff"
    command_description = "查看影子工作区与原始文件的差异"
    command_pattern = r"^/diff(?:\s+(?P<file_path>.+))?$"
    command_help = "查看代码差异。用法: /diff [文件路径]"
    command_examples = ["/diff", "/diff src/plugins/plugin.py"]
    intercept_message = True  # 拦截消息

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plugin_dir = Path(__file__).parent.parent
        self.mai_bot_root = self._find_maibot_root()
        self.shadow_dir = self._get_shadow_dir()

    def _find_maibot_root(self) -> Path:
        current = self.plugin_dir
        while current.parent != current:
            if (current / "bot.py").exists() or (current / "main.py").exists():
                return current
            current = current.parent
        return self.plugin_dir.parent.parent

    def _get_shadow_dir(self) -> Path:
        shadow_path = self.get_config("iteration.shadow_workspace_path", "storage/.shadow")
        if os.path.isabs(shadow_path):
            return Path(shadow_path)
        return self.plugin_dir / shadow_path

    def _is_admin(self, user_id: str) -> bool:
        """检查用户是否是管理员"""
        admin_qqs = self.get_config("security.admin_qqs", [])
        if not admin_qqs:
            return True
        return str(user_id) in [str(qq) for qq in admin_qqs]

    async def execute(self) -> Tuple[bool, str, bool]:
        """执行查看差异操作"""
        user_id = get_user_id_from_message(self.message)

        # 检查权限
        if not self._is_admin(user_id):
            return True, "❌ 你没有权限执行此操作，请联系管理员。", True

        # 获取文件路径参数
        file_path = ""
        if hasattr(self, 'matched_groups') and self.matched_groups:
            file_path = self.matched_groups.get("file_path", "").strip()

        # 如果没有指定文件路径，显示所有待处理文件的差异
        if not file_path:
            if not iteration_state.is_pending():
                return True, "ℹ️ 当前没有等待审核的迭代请求。", True

            # 显示所有待处理文件的差异
            message = "📊 **待审核文件的差异报告**\n\n"

            for target_path_str, shadow_path_str in iteration_state.pending_files.items():
                diff = self._generate_diff(target_path_str, shadow_path_str)
                if diff:
                    message += f"**{target_path_str}:**\n"
                    message += "```diff\n"
                    message += self._truncate_diff(diff, 50)
                    message += "\n```\n\n"

            return True, message, True

        # 显示指定文件的差异
        target_path = self.mai_bot_root / file_path
        shadow_path = self.shadow_dir / file_path

        if not shadow_path.exists():
            return True, f"❌ 影子文件不存在: {file_path}", True

        diff = self._generate_diff(file_path, str(shadow_path))

        message = f"📊 **{file_path} 的差异报告**\n\n"
        message += "```diff\n"
        message += self._truncate_diff(diff, 100)
        message += "\n```\n"

        return True, message, True

    def _generate_diff(self, target_path_str: str, shadow_path_str: str) -> str:
        """生成差异报告"""
        try:
            target_path = self.mai_bot_root / target_path_str
            shadow_path = Path(shadow_path_str)

            original_content = ""
            if target_path.exists():
                with open(target_path, 'r', encoding='utf-8', errors='replace') as f:
                    original_content = f.read()

            shadow_content = ""
            if shadow_path.exists():
                with open(shadow_path, 'r', encoding='utf-8', errors='replace') as f:
                    shadow_content = f.read()

            differ = DiffGenerator()
            return differ.generate(original_content, shadow_content,
                                   f"a/{target_path_str}", f"b/{target_path_str}")
        except Exception as e:
            logger.error(f"[DiffCommand] 生成差异失败: {e}")
            return f"生成差异失败: {e}"

    def _truncate_diff(self, diff: str, max_lines: int = 50) -> str:
        """截断差异报告"""
        lines = diff.splitlines()
        if len(lines) <= max_lines:
            return diff

        head_lines = max_lines // 2
        tail_lines = max_lines - head_lines

        head = lines[:head_lines]
        tail = lines[-tail_lines:]

        return '\n'.join(head) + f"\n... ({len(lines) - max_lines} 行省略) ...\n" + '\n'.join(tail)


class StatusCommand(BaseCommand):
    """
    查看状态命令 - 显示当前迭代状态
    用法: /status 或 /状态
    """

    command_name = "status"
    command_description = "查看当前自我迭代状态"
    command_pattern = r"^/(status|状态|state)$"
    command_help = "查看迭代状态。用法: /status"
    command_examples = ["/status", "/状态"]
    intercept_message = True  # 拦截消息

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plugin_dir = Path(__file__).parent.parent

    def _is_admin(self, user_id: str) -> bool:
        """检查用户是否是管理员"""
        admin_qqs = self.get_config("security.admin_qqs", [])
        if not admin_qqs:
            return True
        return str(user_id) in [str(qq) for qq in admin_qqs]

    async def execute(self) -> Tuple[bool, str, bool]:
        """执行查看状态操作"""
        user_id = get_user_id_from_message(self.message)

        # 检查权限
        if not self._is_admin(user_id):
            return True, "❌ 你没有权限执行此操作，请联系管理员。", True

        state_dict = iteration_state.to_dict()

        message = "📋 **自我迭代状态**\n\n"
        message += f"📊 当前状态: {self._format_status(state_dict['status'])}\n"

        if state_dict['iteration_id']:
            message += f"🆔 迭代ID: {state_dict['iteration_id']}\n"

        if state_dict['target_path']:
            message += f"📁 目标文件: {state_dict['target_path']}\n"

        if state_dict['requester_id']:
            message += f"👤 请求者: {state_dict['requester_id']}\n"

        if state_dict['modification_description']:
            message += f"📝 修改描述: {state_dict['modification_description']}\n"

        if state_dict['pending_files_count']:
            message += f"📄 待处理文件数: {state_dict['pending_files_count']}\n"

        if state_dict['created_at']:
            message += f"🕐 创建时间: {state_dict['created_at']}\n"

        if state_dict['error_message']:
            message += f"❌ 错误信息: {state_dict['error_message']}\n"

        message += "\n💡 **可用命令:**\n"
        message += "• `/iterate` - 启动迭代流程\n"
        message += "• `/approve` - 审核通过\n"
        message += "• `/reject` - 打回修改\n"
        message += "• `/diff` - 查看差异\n"
        message += "• `/rollback` - 回滚版本\n"
        message += "• `/backups` - 查看备份列表"

        return True, message, True

    def _format_status(self, status: str) -> str:
        """格式化状态显示"""
        status_map = {
            "idle": "🟢 空闲",
            "pending": "⏳ 等待审核",
            "approved": "✅ 已批准",
            "rejected": "🚫 已拒绝",
            "applied": "📦 已应用",
            "error": "❌ 错误"
        }
        return status_map.get(status, status)


class RollbackCommand(BaseCommand):
    """
    回滚命令 - 恢复到指定备份版本
    用法: /rollback [时间戳]
    示例: /rollback 20240115_143022
    """

    command_name = "rollback"
    command_description = "回滚到指定备份版本"
    command_pattern = r"^/rollback(?:\s+(?P<timestamp>\S+))?$"
    command_help = "回滚到指定备份版本。用法: /rollback [时间戳]"
    command_examples = ["/rollback", "/rollback 20240115_143022"]
    intercept_message = True  # 拦截消息

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plugin_dir = Path(__file__).parent.parent
        self.mai_bot_root = self._find_maibot_root()
        self.backup_dir = self._get_backup_dir()

    def _find_maibot_root(self) -> Path:
        current = self.plugin_dir
        while current.parent != current:
            if (current / "bot.py").exists() or (current / "main.py").exists():
                return current
            current = current.parent
        return self.plugin_dir.parent.parent

    def _get_backup_dir(self) -> Path:
        backup_path = self.get_config("iteration.backup_path", "storage/.backups")
        if os.path.isabs(backup_path):
            return Path(backup_path)
        return self.plugin_dir / backup_path

    def _is_admin(self, user_id: str) -> bool:
        """检查用户是否是管理员"""
        admin_qqs = self.get_config("security.admin_qqs", [])
        if not admin_qqs:
            return True
        return str(user_id) in [str(qq) for qq in admin_qqs]

    def _list_backups(self) -> List[Tuple[str, Path]]:
        """列出所有备份文件"""
        backups = []

        if not self.backup_dir.exists():
            return backups

        for backup_file in self.backup_dir.glob("*.bak"):
            parts = backup_file.stem.split('.')
            if len(parts) >= 2:
                timestamp = parts[-1]
                backups.append((timestamp, backup_file))

        return sorted(backups, reverse=True)

    async def execute(self) -> Tuple[bool, str, bool]:
        """执行回滚操作"""
        user_id = get_user_id_from_message(self.message)

        # 检查权限
        if not self._is_admin(user_id):
            return True, "❌ 你没有权限执行此操作，请联系管理员。", True

        # 获取时间戳参数
        timestamp = ""
        if hasattr(self, 'matched_groups') and self.matched_groups:
            timestamp = self.matched_groups.get("timestamp", "").strip()

        backups = self._list_backups()

        # 如果没有指定时间戳，显示备份列表
        if not timestamp:
            message = "📋 **可用备份列表**\n\n"

            if not backups:
                message += "ℹ️ 暂无备份文件。\n"
            else:
                message += f"共找到 {len(backups)} 个备份:\n\n"
                for i, (ts, backup_path) in enumerate(backups[:10], 1):
                    message += f"{i}. `{ts}` - {backup_path.name}\n"

                if len(backups) > 10:
                    message += f"\n... 还有 {len(backups) - 10} 个备份"

            message += "\n💡 使用 `/rollback <时间戳>` 回滚到指定版本。"
            return True, message, True

        # 查找指定时间戳的备份
        matching_backups = [(ts, bp) for ts, bp in backups if timestamp in ts]

        if not matching_backups:
            return True, f"❌ 未找到匹配 '{timestamp}' 的备份文件。\n使用 `/rollback` 查看可用备份列表。", True

        if len(matching_backups) > 1:
            message = f"⚠️ 找到多个匹配 '{timestamp}' 的备份:\n\n"
            for ts, bp in matching_backups:
                message += f"• `{ts}` - {bp.name}\n"
            message += "\n请提供更精确的时间戳。"
            return True, message, True

        # 执行回滚
        ts, backup_path = matching_backups[0]

        try:
            # 从备份文件名解析目标路径
            # 格式: path_to_file.py.timestamp.bak
            stem = backup_path.stem  # 去掉.bak
            parts = stem.split('.')

            # 最后一部分是时间戳，前面的是文件路径
            target_path_str = '.'.join(parts[:-1]).replace('_', os.sep)
            target_path = self.mai_bot_root / target_path_str

            # 确保目标目录存在
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # 复制备份文件到目标位置
            shutil.copy2(backup_path, target_path)

            message = "🔄 **回滚成功**\n\n"
            message += f"📁 目标文件: {target_path_str}\n"
            message += f"💾 备份文件: {backup_path.name}\n"
            message += f"🕐 回滚时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            message += "⚠️ **注意:** 部分修改可能需要重启MaiBot才能生效。"

            logger.info(f"[RollbackCommand] 回滚成功: {backup_path} -> {target_path}")
            return True, message, True

        except Exception as e:
            error_msg = f"❌ 回滚失败: {str(e)}"
            logger.error(f"[RollbackCommand] {error_msg}")
            return True, error_msg, True


class ListBackupsCommand(BaseCommand):
    """
    列出备份命令 - 显示所有可用的备份文件
    用法: /backups
    """

    command_name = "backups"
    command_description = "列出所有可用的备份文件"
    command_pattern = r"^/(backups|备份列表|list_backups)$"
    command_help = "列出所有备份。用法: /backups"
    command_examples = ["/backups", "/备份列表"]
    intercept_message = True  # 拦截消息

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plugin_dir = Path(__file__).parent.parent
        self.backup_dir = self._get_backup_dir()

    def _get_backup_dir(self) -> Path:
        backup_path = self.get_config("iteration.backup_path", "storage/.backups")
        if os.path.isabs(backup_path):
            return Path(backup_path)
        return self.plugin_dir / backup_path

    def _is_admin(self, user_id: str) -> bool:
        """检查用户是否是管理员"""
        admin_qqs = self.get_config("security.admin_qqs", [])
        if not admin_qqs:
            return True
        return str(user_id) in [str(qq) for qq in admin_qqs]

    async def execute(self) -> Tuple[bool, str, bool]:
        """执行列出备份操作"""
        user_id = get_user_id_from_message(self.message)

        # 检查权限
        if not self._is_admin(user_id):
            return True, "❌ 你没有权限执行此操作，请联系管理员。", True

        if not self.backup_dir.exists():
            return True, "ℹ️ 备份目录不存在。", True

        backups = []
        for backup_file in self.backup_dir.glob("*.bak"):
            parts = backup_file.stem.split('.')
            if len(parts) >= 2:
                timestamp = parts[-1]
                file_path = '.'.join(parts[:-1]).replace('_', os.sep)
                backups.append((timestamp, file_path, backup_file))

        backups.sort(reverse=True)

        if not backups:
            return True, "ℹ️ 暂无备份文件。", True

        message = f"📋 **备份列表** (共 {len(backups)} 个)\n\n"

        for i, (timestamp, file_path, backup_file) in enumerate(backups[:15], 1):
            size_kb = backup_file.stat().st_size / 1024
            message += f"{i}. `{timestamp}`\n"
            message += f"   📁 {file_path}\n"
            message += f"   📏 {size_kb:.1f} KB\n\n"

        if len(backups) > 15:
            message += f"... 还有 {len(backups) - 15} 个备份\n\n"

        message += "💡 使用 `/rollback <时间戳>` 回滚到指定版本。"

        return True, message, True