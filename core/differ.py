"""
差异生成器 - 生成Git风格的diff报告
"""

import difflib
from pathlib import Path
from typing import List, Tuple, Optional
from src.common.logger import get_logger

logger = get_logger("self_iterative_plugin.core.differ")


class DiffGenerator:
    """
    差异生成器 - 生成类似Git的增删改代码Diff
    
    功能:
    - 生成统一差异格式
    - 统计变更信息
    - 格式化输出
    """
    
    def __init__(self):
        self.stats = {
            'additions': 0,
            'deletions': 0,
            'changes': 0
        }
    
    def generate(self, original: str, modified: str, 
                 original_path: str = "a/file.py", 
                 modified_path: str = "b/file.py") -> str:
        """
        生成差异报告
        
        Args:
            original: 原始内容
            modified: 修改后内容
            original_path: 原始文件路径标识
            modified_path: 修改后文件路径标识
        
        Returns:
            Git风格的diff报告
        """
        # 重置统计
        self.stats = {'additions': 0, 'deletions': 0, 'changes': 0}
        
        # 分割为行
        original_lines = original.splitlines(keepends=True)
        modified_lines = modified.splitlines(keepends=True)
        
        # 确保每行都有换行符
        if original_lines and not original_lines[-1].endswith('\n'):
            original_lines[-1] += '\n'
        if modified_lines and not modified_lines[-1].endswith('\n'):
            modified_lines[-1] += '\n'
        
        # 生成统一差异
        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=original_path,
            tofile=modified_path,
            lineterm=''
        )
        
        diff_text = ''.join(diff)
        
        # 统计变更
        self._calculate_stats(diff_text)
        
        return diff_text
    
    def generate_from_files(self, original_path: Path, modified_path: Path) -> Optional[str]:
        """从文件生成差异报告"""
        try:
            with open(original_path, 'r', encoding='utf-8', errors='replace') as f:
                original = f.read()
            
            with open(modified_path, 'r', encoding='utf-8', errors='replace') as f:
                modified = f.read()
            
            return self.generate(
                original, modified,
                f"a/{original_path.name}",
                f"b/{modified_path.name}"
            )
        except Exception as e:
            logger.error(f"[DiffGenerator] 生成差异失败: {e}")
            return None
    
    def _calculate_stats(self, diff_text: str) -> None:
        """计算变更统计"""
        for line in diff_text.splitlines():
            if line.startswith('+') and not line.startswith('+++'):
                self.stats['additions'] += 1
            elif line.startswith('-') and not line.startswith('---'):
                self.stats['deletions'] += 1
        
        # 变更行数取增加和删除的较小值
        self.stats['changes'] = min(self.stats['additions'], self.stats['deletions'])
    
    def get_stats(self) -> dict:
        """获取变更统计"""
        return self.stats.copy()
    
    def format_summary(self) -> str:
        """格式化统计摘要"""
        return (
            f"变更统计: "
            f"+{self.stats['additions']} 行增加, "
            f"-{self.stats['deletions']} 行删除, "
            f"~{self.stats['changes']} 行修改"
        )
    
    def truncate_diff(self, diff_text: str, max_lines: int = 100) -> str:
        """截断差异报告"""
        lines = diff_text.splitlines()
        if len(lines) <= max_lines:
            return diff_text
        
        # 保留开头和结尾
        head_lines = max_lines // 2
        tail_lines = max_lines - head_lines
        
        head = lines[:head_lines]
        tail = lines[-tail_lines:]
        
        return '\n'.join(head) + f"\n... ({len(lines) - max_lines} 行省略) ...\n" + '\n'.join(tail)
    
    def colorize_diff(self, diff_text: str) -> str:
        """
        为差异文本添加颜色标记（用于终端显示）
        
        返回带有颜色标记的文本:
        - 红色: 删除的行
        - 绿色: 增加的行
        - 黄色: 文件信息
        """
        lines = []
        for line in diff_text.splitlines():
            if line.startswith('+'):
                lines.append(f"\033[92m{line}\033[0m")  # 绿色
            elif line.startswith('-'):
                lines.append(f"\033[91m{line}\033[0m")  # 红色
            elif line.startswith('@@'):
                lines.append(f"\033[96m{line}\033[0m")  # 青色
            elif line.startswith('---') or line.startswith('+++'):
                lines.append(f"\033[93m{line}\033[0m")  # 黄色
            else:
                lines.append(line)
        
        return '\n'.join(lines)


# 全局差异生成器实例
differ = DiffGenerator()
