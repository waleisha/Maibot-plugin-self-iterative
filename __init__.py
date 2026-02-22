"""
MaiBot 自我迭代插件

一个让 MaiBot 能够自我迭代、自我优化的框架插件。
支持代码读取、修改、校验、差异对比和部署，包含完整的安全审核机制。
"""

from .plugin import SelfIterativePlugin

__all__ = ["SelfIterativePlugin"]
