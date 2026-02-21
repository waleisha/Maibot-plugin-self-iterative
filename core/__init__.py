"""
核心模块 - 自我迭代框架的业务逻辑
"""

from .workspace import ShadowWorkspaceManager
from .verifier import SyntaxVerifier
from .differ import DiffGenerator
from .patcher import Patcher

__all__ = [
    "ShadowWorkspaceManager",
    "SyntaxVerifier", 
    "DiffGenerator",
    "Patcher",
]
