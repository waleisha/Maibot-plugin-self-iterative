"""
缝合与部署器 - 负责文件的真实覆盖、备份和重启
"""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from src.common.logger import get_logger

logger = get_logger("self_iterative_plugin.core.patcher")


class Patcher:
    """
    缝合与部署器 - 真正的手术台
    
    功能:
    - 强制备份原文件
    - 文件替换
    - 进程刷新（重启）
    - 一键回滚
    """
    
    def __init__(self, mai_bot_root: Path, backup_dir: Path):
        self.mai_bot_root = mai_bot_root
        self.backup_dir = backup_dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # 记录本次操作备份的文件
        self.current_backups: Dict[str, Path] = {}
    
    def backup(self, target_path: Path) -> Tuple[bool, Optional[Path], str]:
        """
        备份文件
        
        Args:
            target_path: 要备份的目标文件路径
        
        Returns:
            (是否成功, 备份路径, 消息)
        """
        try:
            if not target_path.exists():
                return True, None, "原文件不存在，无需备份"
            
            # 生成备份文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            relative_path = target_path.relative_to(self.mai_bot_root)
            backup_name = f"{str(relative_path).replace(os.sep, '_')}.{timestamp}.bak"
            backup_path = self.backup_dir / backup_name
            
            # 确保备份目录存在
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 复制文件
            shutil.copy2(target_path, backup_path)
            
            # 记录备份
            self.current_backups[str(target_path)] = backup_path
            
            logger.info(f"[Patcher] 备份成功: {target_path} -> {backup_path}")
            return True, backup_path, f"已备份到: {backup_path}"
            
        except Exception as e:
            error_msg = f"备份失败: {str(e)}"
            logger.error(f"[Patcher] {error_msg}")
            return False, None, error_msg
    
    def apply(self, shadow_path: Path, target_path: Path) -> Tuple[bool, str]:
        """
        应用修改
        
        Args:
            shadow_path: 影子文件路径
            target_path: 目标文件路径
        
        Returns:
            (是否成功, 消息)
        """
        try:
            # 检查影子文件是否存在
            if not shadow_path.exists():
                return False, f"影子文件不存在: {shadow_path}"
            
            # 确保目标目录存在
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 先备份
            backup_success, backup_path, backup_msg = self.backup(target_path)
            if not backup_success:
                return False, f"备份失败，取消应用: {backup_msg}"
            
            # 复制影子文件到目标位置
            shutil.copy2(shadow_path, target_path)
            
            logger.info(f"[Patcher] 应用成功: {shadow_path} -> {target_path}")
            return True, f"修改已应用: {target_path}"
            
        except Exception as e:
            error_msg = f"应用修改失败: {str(e)}"
            logger.error(f"[Patcher] {error_msg}")
            return False, error_msg
    
    def rollback(self, backup_path: Path, target_path: Path) -> Tuple[bool, str]:
        """
        回滚到备份版本
        
        Args:
            backup_path: 备份文件路径
            target_path: 目标文件路径
        
        Returns:
            (是否成功, 消息)
        """
        try:
            if not backup_path.exists():
                return False, f"备份文件不存在: {backup_path}"
            
            # 确保目标目录存在
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 复制备份文件到目标位置
            shutil.copy2(backup_path, target_path)
            
            logger.info(f"[Patcher] 回滚成功: {backup_path} -> {target_path}")
            return True, f"已回滚到: {backup_path}"
            
        except Exception as e:
            error_msg = f"回滚失败: {str(e)}"
            logger.error(f"[Patcher] {error_msg}")
            return False, error_msg
    
    def list_backups(self, target_path: Optional[Path] = None) -> List[Tuple[str, Path]]:
        """
        列出备份文件
        
        Args:
            target_path: 可选，只列出指定文件的备份
        
        Returns:
            [(时间戳, 备份路径), ...]
        """
        backups = []
        
        if not self.backup_dir.exists():
            return backups
        
        for backup_file in self.backup_dir.glob("*.bak"):
            # 从文件名提取时间戳
            parts = backup_file.stem.split('.')
            if len(parts) >= 2:
                timestamp = parts[-1]
                
                # 如果指定了目标文件，检查是否匹配
                if target_path:
                    relative_str = str(target_path.relative_to(self.mai_bot_root)).replace(os.sep, '_')
                    if not backup_file.stem.startswith(relative_str):
                        continue
                
                backups.append((timestamp, backup_file))
        
        # 按时间戳降序排序
        return sorted(backups, reverse=True)
    
    def cleanup_old_backups(self, max_backups: int = 50) -> int:
        """
        清理旧备份
        
        Args:
            max_backups: 最大保留备份数
        
        Returns:
            清理的备份数量
        """
        try:
            all_backups = []
            for backup_file in self.backup_dir.glob("*.bak"):
                all_backups.append((backup_file.stat().st_mtime, backup_file))
            
            # 如果备份数量超过限制
            if len(all_backups) <= max_backups:
                return 0
            
            # 按修改时间排序
            all_backups.sort(key=lambda x: x[0])
            
            # 删除最旧的备份
            to_delete = len(all_backups) - max_backups
            deleted = 0
            
            for _, backup_file in all_backups[:to_delete]:
                try:
                    backup_file.unlink()
                    deleted += 1
                except Exception as e:
                    logger.warning(f"[Patcher] 删除旧备份失败: {backup_file} - {e}")
            
            logger.info(f"[Patcher] 清理了 {deleted} 个旧备份")
            return deleted
            
        except Exception as e:
            logger.error(f"[Patcher] 清理旧备份失败: {e}")
            return 0
    
    def get_backup_info(self, backup_path: Path) -> Dict:
        """获取备份信息"""
        try:
            stat = backup_path.stat()
            return {
                "path": str(backup_path),
                "name": backup_path.name,
                "size": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "exists": True
            }
        except Exception as e:
            return {
                "path": str(backup_path),
                "exists": False,
                "error": str(e)
            }


# 全局部署器实例（需要在初始化时传入参数）
patcher: Optional[Patcher] = None


def init_patcher(mai_bot_root: Path, backup_dir: Path) -> Patcher:
    """初始化全局部署器"""
    global patcher
    patcher = Patcher(mai_bot_root, backup_dir)
    return patcher
