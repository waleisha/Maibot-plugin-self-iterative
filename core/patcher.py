"""
缝合与部署器 (Patcher)
=====================

负责将影子工作区的修改应用到真实路径。
这是真正执行危险操作的地方，需要格外小心。

功能:
- 备份原文件
- 应用修改（文件替换）
- 部署后验证
- 回滚支持
- 重启管理
"""

import os
import shutil
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Callable
from dataclasses import dataclass


@dataclass
class PatchResult:
    """补丁应用结果"""
    success: bool
    message: str
    backup_path: Optional[Path] = None
    error: Optional[str] = None


@dataclass
class BatchPatchResult:
    """批量补丁应用结果"""
    success: bool
    total_files: int
    success_count: int
    failed_count: int
    results: List[Tuple[str, PatchResult]]
    message: str


class Patcher:
    """
    缝合与部署器
    
    负责将影子工作区的修改安全地应用到真实路径。
    """
    
    def __init__(
        self,
        backup_dir: Path,
        max_backups: int = 50,
        backup_callback: Optional[Callable[[Path, Path], None]] = None
    ):
        """
        初始化Patcher
        
        Args:
            backup_dir: 备份存储目录
            max_backups: 最大备份数量
            backup_callback: 备份完成后的回调函数
        """
        self.backup_dir = Path(backup_dir)
        self.max_backups = max_backups
        self.backup_callback = backup_callback
        
        # 确保备份目录存在
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def _generate_backup_path(self, target_path: Path) -> Path:
        """
        生成备份文件路径
        
        Args:
            target_path: 目标文件路径
            
        Returns:
            备份文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{target_path.name}.{timestamp}.bak"
        return self.backup_dir / backup_name
    
    def _cleanup_old_backups(self):
        """清理旧备份文件"""
        if not self.backup_dir.exists():
            return
        
        # 获取所有备份文件
        backups = []
        for backup_file in self.backup_dir.glob("*.bak"):
            try:
                stat = backup_file.stat()
                backups.append((stat.st_mtime, backup_file))
            except:
                pass
        
        # 按修改时间排序
        backups.sort()
        
        # 删除超出限制的备份
        if len(backups) > self.max_backups:
            for _, old_backup in backups[:len(backups) - self.max_backups]:
                try:
                    old_backup.unlink()
                except:
                    pass
    
    def backup_file(self, target_path: Path) -> Tuple[bool, Optional[Path], str]:
        """
        备份文件
        
        Args:
            target_path: 要备份的文件路径
            
        Returns:
            (是否成功, 备份路径, 消息)
        """
        try:
            if not target_path.exists():
                return True, None, "原文件不存在，无需备份"
            
            # 生成备份路径
            backup_path = self._generate_backup_path(target_path)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 复制文件
            shutil.copy2(target_path, backup_path)
            
            # 清理旧备份
            self._cleanup_old_backups()
            
            # 调用回调
            if self.backup_callback:
                self.backup_callback(target_path, backup_path)
            
            return True, backup_path, f"备份成功: {backup_path}"
            
        except Exception as e:
            return False, None, f"备份失败: {str(e)}"
    
    def apply_patch(
        self,
        target_path: Path,
        shadow_path: Path,
        create_backup: bool = True
    ) -> PatchResult:
        """
        应用单个补丁
        
        Args:
            target_path: 目标文件路径
            shadow_path: 影子文件路径
            create_backup: 是否创建备份
            
        Returns:
            补丁应用结果
        """
        try:
            # 1. 验证影子文件存在
            if not shadow_path.exists():
                return PatchResult(
                    success=False,
                    message="影子文件不存在",
                    error=f"Shadow file not found: {shadow_path}"
                )
            
            # 2. 备份原文件
            backup_path = None
            if create_backup:
                success, backup_path, msg = self.backup_file(target_path)
                if not success:
                    return PatchResult(
                        success=False,
                        message=f"备份失败: {msg}",
                        error=msg
                    )
            
            # 3. 确保目标目录存在
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 4. 复制影子文件到目标位置
            shutil.copy2(shadow_path, target_path)
            
            # 5. 验证文件写入成功
            if not target_path.exists():
                return PatchResult(
                    success=False,
                    message="文件写入验证失败",
                    backup_path=backup_path,
                    error="Target file not found after copy"
                )
            
            # 6. 计算文件哈希验证完整性
            with open(shadow_path, 'rb') as f:
                shadow_hash = hashlib.md5(f.read()).hexdigest()
            
            with open(target_path, 'rb') as f:
                target_hash = hashlib.md5(f.read()).hexdigest()
            
            if shadow_hash != target_hash:
                return PatchResult(
                    success=False,
                    message="文件完整性验证失败",
                    backup_path=backup_path,
                    error="File hash mismatch"
                )
            
            return PatchResult(
                success=True,
                message=f"补丁应用成功: {target_path}",
                backup_path=backup_path
            )
            
        except Exception as e:
            return PatchResult(
                success=False,
                message=f"应用补丁时发生错误: {str(e)}",
                error=str(e)
            )
    
    def apply_batch_patches(
        self,
        patches: List[Tuple[Path, Path]],
        create_backup: bool = True,
        stop_on_error: bool = False
    ) -> BatchPatchResult:
        """
        批量应用补丁
        
        Args:
            patches: 补丁列表，每项为 (target_path, shadow_path)
            create_backup: 是否创建备份
            stop_on_error: 遇到错误时是否停止
            
        Returns:
            批量补丁应用结果
        """
        results = []
        success_count = 0
        failed_count = 0
        
        for target_path, shadow_path in patches:
            result = self.apply_patch(target_path, shadow_path, create_backup)
            results.append((str(target_path), result))
            
            if result.success:
                success_count += 1
            else:
                failed_count += 1
                if stop_on_error:
                    break
        
        total = len(patches)
        success = failed_count == 0
        
        message = f"批量补丁应用完成: 成功 {success_count}/{total}, 失败 {failed_count}/{total}"
        
        return BatchPatchResult(
            success=success,
            total_files=total,
            success_count=success_count,
            failed_count=failed_count,
            results=results,
            message=message
        )
    
    def rollback(self, target_path: Path, backup_path: Path) -> PatchResult:
        """
        回滚到备份版本
        
        Args:
            target_path: 目标文件路径
            backup_path: 备份文件路径
            
        Returns:
            回滚结果
        """
        try:
            # 验证备份文件存在
            if not backup_path.exists():
                return PatchResult(
                    success=False,
                    message=f"备份文件不存在: {backup_path}",
                    error="Backup file not found"
                )
            
            # 备份当前文件（回滚前备份）
            current_backup_path = None
            if target_path.exists():
                success, current_backup_path, _ = self.backup_file(target_path)
            
            # 恢复备份
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_path, target_path)
            
            return PatchResult(
                success=True,
                message=f"回滚成功: {target_path} <- {backup_path}",
                backup_path=current_backup_path
            )
            
        except Exception as e:
            return PatchResult(
                success=False,
                message=f"回滚失败: {str(e)}",
                error=str(e)
            )
    
    def list_backups(self, target_path: Optional[Path] = None) -> List[Path]:
        """
        列出备份文件
        
        Args:
            target_path: 如果指定，只列出该文件的备份
            
        Returns:
            备份文件路径列表
        """
        if not self.backup_dir.exists():
            return []
        
        backups = []
        for backup_file in self.backup_dir.glob("*.bak"):
            if target_path is None or backup_file.name.startswith(target_path.name):
                backups.append(backup_file)
        
        # 按修改时间排序（最新的在前）
        backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        
        return backups
    
    def get_backup_info(self, backup_path: Path) -> Optional[Dict]:
        """
        获取备份文件信息
        
        Args:
            backup_path: 备份文件路径
            
        Returns:
            备份信息字典，如果文件不存在则返回None
        """
        try:
            if not backup_path.exists():
                return None
            
            stat = backup_path.stat()
            
            # 从文件名解析原始文件名和时间戳
            # 格式: filename.YYYYMMDD_HHMMSS.bak
            parts = backup_path.stem.split('.')
            if len(parts) >= 2:
                original_name = '.'.join(parts[:-1])
                timestamp = parts[-1]
            else:
                original_name = backup_path.stem
                timestamp = "unknown"
            
            return {
                "path": str(backup_path),
                "original_name": original_name,
                "timestamp": timestamp,
                "size_bytes": stat.st_size,
                "size_kb": round(stat.st_size / 1024, 2),
                "created": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            }
            
        except Exception:
            return None
    
    def delete_backup(self, backup_path: Path) -> bool:
        """
        删除备份文件
        
        Args:
            backup_path: 备份文件路径
            
        Returns:
            是否成功删除
        """
        try:
            if backup_path.exists():
                backup_path.unlink()
                return True
            return False
        except:
            return False
    
    def verify_file_integrity(self, file_path: Path, expected_hash: Optional[str] = None) -> bool:
        """
        验证文件完整性
        
        Args:
            file_path: 文件路径
            expected_hash: 预期的MD5哈希值
            
        Returns:
            是否通过验证
        """
        try:
            if not file_path.exists():
                return False
            
            with open(file_path, 'rb') as f:
                actual_hash = hashlib.md5(f.read()).hexdigest()
            
            if expected_hash is None:
                return True
            
            return actual_hash == expected_hash
            
        except:
            return False
