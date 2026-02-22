"""
迭代状态管理器 - 单例模式管理全局迭代状态
"""

from typing import Dict, Any, Optional
from datetime import datetime
from src.common.logger import get_logger

logger = get_logger("self_iterative_plugin.core.state")


class IterationState:
    """
    迭代状态管理器 - 单例模式
    
    管理整个迭代流程的状态:
    - idle: 空闲状态
    - pending: 等待审核
    - approved: 已批准
    - rejected: 已拒绝
    - applied: 已应用
    - error: 错误状态
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.status = "idle"  # idle, pending, approved, rejected, applied, error
        self.iteration_id: Optional[str] = None
        self.target_path: Optional[str] = None
        self.shadow_path: Optional[str] = None
        self.backup_path: Optional[str] = None
        self.requester_id: Optional[str] = None
        self.modification_description: Optional[str] = None
        self.diff_report: Optional[str] = None
        self.pending_files: Dict[str, str] = {}  # target_path -> shadow_path
        self.created_at: Optional[datetime] = None
        self.error_message: Optional[str] = None
        self._initialized = True
        
        logger.info("[IterationState] 迭代状态管理器已初始化")
    
    def start_iteration(self, iteration_id: str, requester_id: str, target_path: str, 
                        description: str, diff_report: str = "") -> None:
        """开始一个新的迭代任务"""
        self.status = "pending"
        self.iteration_id = iteration_id
        self.requester_id = requester_id
        self.target_path = target_path
        self.modification_description = description
        self.diff_report = diff_report
        self.created_at = datetime.now()
        self.error_message = None
        self.pending_files = {}
        logger.info(f"[IterationState] 迭代任务开始: {iteration_id}")
    
    def add_pending_file(self, target_path: str, shadow_path: str) -> None:
        """添加待处理的文件"""
        self.pending_files[target_path] = shadow_path
        logger.debug(f"[IterationState] 添加待处理文件: {target_path} -> {shadow_path}")
    
    def approve(self) -> None:
        """批准迭代"""
        self.status = "approved"
        logger.info(f"[IterationState] 迭代已批准: {self.iteration_id}")
    
    def reject(self) -> None:
        """拒绝迭代"""
        self.status = "rejected"
        self.pending_files.clear()
        logger.info(f"[IterationState] 迭代已拒绝: {self.iteration_id}")
    
    def apply(self) -> None:
        """应用迭代"""
        self.status = "applied"
        logger.info(f"[IterationState] 迭代已应用: {self.iteration_id}")
    
    def set_error(self, error_msg: str) -> None:
        """设置错误状态"""
        self.status = "error"
        self.error_message = error_msg
        logger.error(f"[IterationState] 迭代错误: {error_msg}")
    
    def reset(self) -> None:
        """重置状态"""
        self.status = "idle"
        self.iteration_id = None
        self.target_path = None
        self.shadow_path = None
        self.backup_path = None
        self.requester_id = None
        self.modification_description = None
        self.diff_report = None
        self.pending_files.clear()
        self.created_at = None
        self.error_message = None
        logger.info("[IterationState] 状态已重置")
    
    def is_pending(self) -> bool:
        """检查是否有待审核的迭代"""
        return self.status == "pending"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "status": self.status,
            "iteration_id": self.iteration_id,
            "target_path": self.target_path,
            "requester_id": self.requester_id,
            "modification_description": self.modification_description,
            "pending_files_count": len(self.pending_files),
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "error_message": self.error_message
        }


# 全局状态实例
iteration_state = IterationState()
