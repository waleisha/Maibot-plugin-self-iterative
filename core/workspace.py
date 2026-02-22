"""
影子工作区管理器 - 隔离大模型的危险操作
"""

import os
import shutil
from pathlib import Path
from typing import List, Tuple, Optional
from src.common.logger import get_logger

logger = get_logger("self_iterative_plugin.core.workspace")


class WorkspaceManager:
    """
    影子工作区管理器
    
    功能:
    - 管理影子工作区目录
    - 清理过期文件
    - 管理文件映射关系
    """
    
    def __init__(self, mai_bot_root: Path, shadow_dir: Path):
        self.mai_bot_root = mai_bot_root
        self.shadow_dir = shadow_dir
        self.shadow_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"[WorkspaceManager] 影子工作区: {self.shadow_dir}")
    
    def get_shadow_path(self, target_path: Path) -> Path:
        """获取目标文件对应的影子路径"""
        # 如果target_path是绝对路径，转换为相对路径
        if target_path.is_absolute():
            try:
                relative_path = target_path.relative_to(self.mai_bot_root)
            except ValueError:
                relative_path = target_path.name
        else:
            relative_path = target_path
        
        return self.shadow_dir / relative_path
    
    def create_shadow(self, target_path: Path, content: str) -> Tuple[bool, Path, str]:
        """
        创建影子文件
        
        Args:
            target_path: 目标文件路径
            content: 文件内容
        
        Returns:
            (是否成功, 影子路径, 消息)
        """
        try:
            shadow_path = self.get_shadow_path(target_path)
            shadow_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(shadow_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"[WorkspaceManager] 创建影子文件: {shadow_path}")
            return True, shadow_path, f"影子文件已创建: {shadow_path}"
            
        except Exception as e:
            error_msg = f"创建影子文件失败: {str(e)}"
            logger.error(f"[WorkspaceManager] {error_msg}")
            return False, Path(), error_msg
    
    def read_shadow(self, target_path: Path) -> Tuple[bool, str, str]:
        """
        读取影子文件内容
        
        Args:
            target_path: 目标文件路径
        
        Returns:
            (是否成功, 内容, 消息)
        """
        try:
            shadow_path = self.get_shadow_path(target_path)
            
            if not shadow_path.exists():
                return False, "", f"影子文件不存在: {shadow_path}"
            
            with open(shadow_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            return True, content, f"成功读取影子文件: {shadow_path}"
            
        except Exception as e:
            error_msg = f"读取影子文件失败: {str(e)}"
            logger.error(f"[WorkspaceManager] {error_msg}")
            return False, "", error_msg
    
    def delete_shadow(self, target_path: Path) -> Tuple[bool, str]:
        """
        删除影子文件
        
        Args:
            target_path: 目标文件路径
        
        Returns:
            (是否成功, 消息)
        """
        try:
            shadow_path = self.get_shadow_path(target_path)
            
            if not shadow_path.exists():
                return True, f"影子文件不存在，无需删除: {shadow_path}"
            
            shadow_path.unlink()
            logger.info(f"[WorkspaceManager] 删除影子文件: {shadow_path}")
            return True, f"影子文件已删除: {shadow_path}"
            
        except Exception as e:
            error_msg = f"删除影子文件失败: {str(e)}"
            logger.error(f"[WorkspaceManager] {error_msg}")
            return False, error_msg
    
    def clear_all(self) -> Tuple[bool, str]:
        """
        清空整个影子工作区
        
        Returns:
            (是否成功, 消息)
        """
        try:
            if self.shadow_dir.exists():
                shutil.rmtree(self.shadow_dir)
                self.shadow_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info("[WorkspaceManager] 影子工作区已清空")
            return True, "影子工作区已清空"
            
        except Exception as e:
            error_msg = f"清空影子工作区失败: {str(e)}"
            logger.error(f"[WorkspaceManager] {error_msg}")
            return False, error_msg
    
    def list_shadows(self) -> List[Path]:
        """列出所有影子文件"""
        shadows = []
        
        if not self.shadow_dir.exists():
            return shadows
        
        for root, dirs, files in os.walk(self.shadow_dir):
            for file in files:
                shadows.append(Path(root) / file)
        
        return shadows
    
    def cleanup_expired(self, max_age_hours: int = 24) -> int:
        """
        清理过期的影子文件
        
        Args:
            max_age_hours: 最大保留时间（小时）
        
        Returns:
            清理的文件数量
        """
        import time
        
        try:
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            
            deleted = 0
            for shadow_file in self.list_shadows():
                try:
                    file_stat = shadow_file.stat()
                    file_age = current_time - file_stat.st_mtime
                    
                    if file_age > max_age_seconds:
                        shadow_file.unlink()
                        deleted += 1
                        
                except Exception as e:
                    logger.warning(f"[WorkspaceManager] 清理文件失败: {shadow_file} - {e}")
            
            logger.info(f"[WorkspaceManager] 清理了 {deleted} 个过期影子文件")
            return deleted
            
        except Exception as e:
            logger.error(f"[WorkspaceManager] 清理过期文件失败: {e}")
            return 0
    
    def get_stats(self) -> dict:
        """获取工作区统计信息"""
        shadows = self.list_shadows()
        total_size = sum(f.stat().st_size for f in shadows if f.exists())
        
        return {
            "shadow_dir": str(self.shadow_dir),
            "file_count": len(shadows),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2)
        }


# 全局工作区管理器实例（需要在初始化时传入参数）
workspace: Optional[WorkspaceManager] = None


def init_workspace(mai_bot_root: Path, shadow_dir: Path) -> WorkspaceManager:
    """初始化全局工作区管理器"""
    global workspace
    workspace = WorkspaceManager(mai_bot_root, shadow_dir)
    return workspace
