"""
差异生成器 (DiffGenerator)
==========================

负责生成Git风格的差异报告，对比影子工作区的新代码和原代码。

功能:
- 生成Unified Diff格式的差异报告
- 支持行号显示
- 统计增删改信息
- 生成可视化差异
"""

import difflib
from typing import List, Tuple, Optional
from pathlib import Path
from dataclasses import dataclass


@dataclass
class DiffStats:
    """差异统计信息"""
    additions: int = 0  # 新增行数
    deletions: int = 0  # 删除行数
    modifications: int = 0  # 修改行数
    unchanged: int = 0  # 未变更行数
    
    @property
    def total_changes(self) -> int:
        """总变更数"""
        return self.additions + self.deletions + self.modifications
    
    def __str__(self) -> str:
        return (
            f"新增: +{self.additions} | "
            f"删除: -{self.deletions} | "
            f"修改: ~{self.modifications} | "
            f"总计: {self.total_changes}"
        )


class DiffGenerator:
    """
    差异生成器
    
    生成Git风格的diff报告。
    """
    
    def __init__(self, context_lines: int = 3):
        """
        初始化差异生成器
        
        Args:
            context_lines: 上下文行数（diff显示的未变更行数）
        """
        self.context_lines = context_lines
    
    def generate_diff(
        self,
        original_lines: List[str],
        new_lines: List[str],
        original_name: str = "a/file",
        new_name: str = "b/file"
    ) -> str:
        """
        生成差异报告
        
        Args:
            original_lines: 原始代码行列表
            new_lines: 新代码行列表
            original_name: 原始文件名
            new_name: 新文件名
            
        Returns:
            Unified Diff格式的差异报告
        """
        # 确保每行以换行符结尾
        original_lines = self._normalize_lines(original_lines)
        new_lines = self._normalize_lines(new_lines)
        
        # 生成diff
        diff = difflib.unified_diff(
            original_lines,
            new_lines,
            fromfile=original_name,
            tofile=new_name,
            lineterm='',
            n=self.context_lines
        )
        
        return '\n'.join(diff)
    
    def generate_diff_from_strings(
        self,
        original: str,
        new: str,
        original_name: str = "a/file",
        new_name: str = "b/file"
    ) -> str:
        """
        从字符串生成差异报告
        
        Args:
            original: 原始代码字符串
            new: 新代码字符串
            original_name: 原始文件名
            new_name: 新文件名
            
        Returns:
            Unified Diff格式的差异报告
        """
        original_lines = original.splitlines(keepends=True)
        new_lines = new.splitlines(keepends=True)
        
        return self.generate_diff(original_lines, new_lines, original_name, new_name)
    
    def generate_diff_from_files(
        self,
        original_path: Path,
        new_path: Path
    ) -> Optional[str]:
        """
        从文件生成差异报告
        
        Args:
            original_path: 原始文件路径
            new_path: 新文件路径
            
        Returns:
            差异报告，如果文件不存在则返回None
        """
        try:
            if original_path.exists():
                with open(original_path, 'r', encoding='utf-8') as f:
                    original = f.read()
            else:
                original = ""
            
            if new_path.exists():
                with open(new_path, 'r', encoding='utf-8') as f:
                    new = f.read()
            else:
                return None
            
            return self.generate_diff_from_strings(
                original,
                new,
                f"a/{original_path.name}",
                f"b/{original_path.name}"
            )
            
        except Exception as e:
            return f"生成差异失败: {str(e)}"
    
    def calculate_stats(
        self,
        original_lines: List[str],
        new_lines: List[str]
    ) -> DiffStats:
        """
        计算差异统计信息
        
        Args:
            original_lines: 原始代码行列表
            new_lines: 新代码行列表
            
        Returns:
            差异统计信息
        """
        stats = DiffStats()
        
        # 使用SequenceMatcher分析差异
        sm = difflib.SequenceMatcher(None, original_lines, new_lines)
        
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == 'equal':
                stats.unchanged += (i2 - i1)
            elif tag == 'delete':
                stats.deletions += (i2 - i1)
            elif tag == 'insert':
                stats.additions += (j2 - j1)
            elif tag == 'replace':
                # 修改 = 删除 + 新增
                stats.modifications += max(i2 - i1, j2 - j1)
        
        return stats
    
    def calculate_stats_from_strings(self, original: str, new: str) -> DiffStats:
        """
        从字符串计算差异统计信息
        
        Args:
            original: 原始代码字符串
            new: 新代码字符串
            
        Returns:
            差异统计信息
        """
        original_lines = original.splitlines(keepends=True)
        new_lines = new.splitlines(keepends=True)
        return self.calculate_stats(original_lines, new_lines)
    
    def generate_colored_diff(
        self,
        original_lines: List[str],
        new_lines: List[str],
        original_name: str = "a/file",
        new_name: str = "b/file"
    ) -> str:
        """
        生成带颜色标记的差异报告（Markdown格式）
        
        Args:
            original_lines: 原始代码行列表
            new_lines: 新代码行列表
            original_name: 原始文件名
            new_name: 新文件名
            
        Returns:
            Markdown格式的差异报告
        """
        diff = self.generate_diff(original_lines, new_lines, original_name, new_name)
        
        if not diff:
            return "✅ 文件内容相同，无差异"
        
        lines = diff.split('\n')
        result = []
        
        for line in lines:
            if line.startswith('---'):
                result.append(f"**{line}**")
            elif line.startswith('+++'):
                result.append(f"**{line}**")
            elif line.startswith('@@'):
                result.append(f"`{line}`")
            elif line.startswith('+'):
                result.append(f"✅ {line}")  # 新增
            elif line.startswith('-'):
                result.append(f"❌ {line}")  # 删除
            else:
                result.append(line)
        
        return '\n'.join(result)
    
    def generate_summary(
        self,
        original_lines: List[str],
        new_lines: List[str]
    ) -> str:
        """
        生成差异摘要
        
        Args:
            original_lines: 原始代码行列表
            new_lines: 新代码行列表
            
        Returns:
            差异摘要字符串
        """
        stats = self.calculate_stats(original_lines, new_lines)
        
        summary = f"📊 差异摘要\n"
        summary += f"━━━━━━━━━━━━━━━━━━━━\n"
        summary += f"📄 原始行数: {len(original_lines)}\n"
        summary += f"📝 新行数: {len(new_lines)}\n"
        summary += f"━━━━━━━━━━━━━━━━━━━━\n"
        summary += f"✅ 新增: +{stats.additions} 行\n"
        summary += f"❌ 删除: -{stats.deletions} 行\n"
        summary += f"🔄 修改: ~{stats.modifications} 行\n"
        summary += f"📊 总计变更: {stats.total_changes} 行\n"
        summary += f"━━━━━━━━━━━━━━━━━━━━"
        
        return summary
    
    def _normalize_lines(self, lines: List[str]) -> List[str]:
        """
        规范化行列表，确保每行以换行符结尾
        
        Args:
            lines: 原始行列表
            
        Returns:
            规范化后的行列表
        """
        result = []
        for line in lines:
            if not line.endswith('\n'):
                line += '\n'
            result.append(line)
        return result
    
    def is_identical(self, original: str, new: str) -> bool:
        """
        检查两段代码是否完全相同
        
        Args:
            original: 原始代码
            new: 新代码
            
        Returns:
            是否相同
        """
        return original == new


# 便捷函数
def quick_diff(
    original: str,
    new: str,
    original_name: str = "原始文件",
    new_name: str = "修改后文件"
) -> Tuple[str, DiffStats]:
    """
    快速生成差异报告
    
    Args:
        original: 原始代码
        new: 新代码
        original_name: 原始文件名
        new_name: 新文件名
        
    Returns:
        (差异报告, 统计信息)
    """
    generator = DiffGenerator()
    diff = generator.generate_diff_from_strings(original, new, original_name, new_name)
    stats = generator.calculate_stats_from_strings(original, new)
    return diff, stats
