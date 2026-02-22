"""
处理器模块 - 包含命令处理器和事件处理器
"""

from .command_handler import (
    IterateCommand,
    ApproveCommand,
    RejectCommand,
    DiffCommand,
    StatusCommand,
    RollbackCommand,
    ListBackupsCommand,
)

from .inject_handler import (
    SelfIterativeInjectHandler,
    SelfIterativePostHandler,
)

from .weak_command_handler import (
    WeakIterateHandler,
)

__all__ = [
    # 命令处理器
    "IterateCommand",
    "ApproveCommand",
    "RejectCommand",
    "DiffCommand",
    "StatusCommand",
    "RollbackCommand",
    "ListBackupsCommand",
    # 事件处理器
    "SelfIterativeInjectHandler",
    "SelfIterativePostHandler",
    # 弱命令处理器
    "WeakIterateHandler",
]
