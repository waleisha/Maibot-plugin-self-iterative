"""
影子工作区管理器 (ShadowWorkspaceManager)
======================================

负责管理影子工作区的生命周期，隔离大模型的危险操作。
所有代码修改都先写入影子工作区，经过审核后再应用到真实路径。

功能:
- 创建和管理影子工作区目录
- 路径映射（目标路径 <-> 影子路径）
- 清理过期文件
- 空间管理
"""

import os
import shutil
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple


class ShadowWorkspaceManager:
    """
    影子工作区管理器
    
    提供安全的代码修改隔离环境。
    """
    
    def __init__(self, base_path: Path, max_age_days: int = 7):
        """
        初始化影子工作区管理器
        
        Args:
            base_path: 影子工作区基础路径
            max_age_days: 文件最大保留天数，超过后自动清理
        """
        self.base_path = Path(base_path)
        self.max_age_days = max_age_days
        self._path_map: Dict[str, str] = {}  # target_path -> shadow_path
        
        # 确保目录存在
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def _generate_shadow_path(self, target_path: str) -> Path:
        """
        为目标路径生成对应的影子路径
        
        使用哈希确保唯一性，同时保持可读性。
        
        Args:
            target_path: 目标文件路径
            
        Returns:
            影子文件路径
        """
        # 生成路径哈希（用于避免文件名冲突）
        path_hash = hashlib.md5(target_path.encode()).hexdigest()[:8]
        
        # 构建影子路径
        target = Path(target_path)
        shadow_name = f"{target.stem}_{path_hash}{target.suffix}"
        shadow_path = self.base_path / shadow_name
        
        return shadow_path
    
    def map_path(self, target_path: str) -> Path:
        """
        获取目标路径对应的影子路径
        
        Args:
            target_path: 目标文件路径
            
        Returns:
            影子文件路径
        """
        if target_path not in self._path_map:
            shadow_path = self._generate_shadow_path(target_path)
            self._path_map[target_path] = str(shadow_path)
        
        return Path(self._path_map[target_path])
    
    def get_target_path(self, shadow_path: str) -> Optional[str]:
        """
        从影子路径反查目标路径
        
        Args:
            shadow_path: 影子文件路径
            
        Returns:
            目标文件路径，如果未找到则返回None
        """
        for target, shadow in self._path_map.items():
            if shadow == shadow_path:
                return target
        return None
    
    def write_file(self, target_path: str, content: str) -> Path:
        """
        将内容写入影子工作区
        
        Args:
            target_path: 目标文件路径（用于映射）
            content: 文件内容
            
        Returns:
            影子文件路径
        """
        shadow_path = self.map_path(target_path)
        
        # 确保父目录存在
        shadow_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 写入文件
        with open(shadow_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return shadow_path
    
    def read_file(self, target_path: str) -> Optional[str]:
        """
        从影子工作区读取文件内容
        
        Args:
            target_path: 目标文件路径
            
        Returns:
            文件内容，如果文件不存在则返回None
        """
        shadow_path = self.map_path(target_path)
        
        if not shadow_path.exists():
            return None
        
        with open(shadow_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def file_exists(self, target_path: str) -> bool:
        """
        检查影子工作区中是否存在对应文件
        
        Args:
            target_path: 目标文件路径
            
        Returns:
            是否存在
        """
        shadow_path = self.map_path(target_path)
        return shadow_path.exists()
    
    def delete_file(self, target_path: str) -> bool:
        """
        删除影子工作区中的对应文件
        
        Args:
            target_path: 目标文件路径
            
        Returns:
            是否成功删除
        """
        shadow_path = self.map_path(target_path)
        
        if shadow_path.exists():
            shadow_path.unlink()
            
            # 从映射中移除
            if target_path in self._path_map:
                del self._path_map[target_path]
            
            return True
        
        return False
    
    def list_files(self) -> List[Tuple[str, Path]]:
        """
        列出影子工作区中的所有文件
        
        Returns:
            列表，每项为 (target_path, shadow_path)
        """
        files = []
        for target_path, shadow_path in self._path_map.items():
            if Path(shadow_path).exists():
                files.append((target_path, Path(shadow_path)))
        return files
    
    def clear_all(self) -> int:
        """
        清空影子工作区
        
        Returns:
            删除的文件数量
        """
        count = 0
        
        # 删除所有映射的文件
        for shadow_path in self._path_map.values():
            path = Path(shadow_path)
            if path.exists():
                path.unlink()
                count += 1
        
        # 清空映射
        self._path_map.clear()
        
        # 清理空目录
        self._cleanup_empty_dirs()
        
        return count
    
    def cleanup_expired(self) -> int:
        """
        清理过期的影子文件
        
        Returns:
            删除的文件数量
        """
        count = 0
        cutoff_time = datetime.now() - timedelta(days=self.max_age_days)
        
        for target_path, shadow_path in list(self._path_map.items()):
            path = Path(shadow_path)
            if path.exists():
                # 获取文件修改时间
                mtime = datetime.fromtimestamp(path.stat().st_mtime)
                
                if mtime < cutoff_time:
                    path.unlink()
                    del self._path_map[target_path]
                    count += 1
        
        # 清理空目录
        self._cleanup_empty_dirs()
        
        return count
    
    def _cleanup_empty_dirs(self):
        """清理空目录"""
        for root, dirs, files in os.walk(str(self.base_path), topdown=False):
            for dir_name in dirs:
                dir_path = Path(root) / dir_name
                try:
                    if dir_path.exists() and not any(dir_path.iterdir()):
                        dir_path.rmdir()
                except:
                    pass
    
    def get_stats(self) -> Dict:
        """
        获取影子工作区统计信息
        
        Returns:
            统计信息字典
        """
        total_files = 0
        total_size = 0
        oldest_file = None
        newest_file = None
        
        for shadow_path in self._path_map.values():
            path = Path(shadow_path)
            if path.exists():
                total_files += 1
                stat = path.stat()
                total_size += stat.st_size
                mtime = datetime.fromtimestamp(stat.st_mtime)
                
                if oldest_file is None or mtime < oldest_file[1]:
                    oldest_file = (str(path), mtime)
                
                if newest_file is None or mtime > newest_file[1]:
                    newest_file = (str(path), mtime)
        
        return {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "oldest_file": oldest_file,
            "newest_file": newest_file,
            "base_path": str(self.base_path),
        }
