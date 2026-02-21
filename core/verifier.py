"""
静态校验器 (SyntaxVerifier)
==========================

负责对新代码进行静态语法检查，确保代码可以正常解析。
使用Python的AST模块进行语法分析。

功能:
- Python代码语法检查
- 缩进检查
- 括号匹配检查
- 生成详细的错误信息
"""

import ast
import re
from typing import Tuple, List, Dict, Optional
from pathlib import Path


class SyntaxErrorInfo:
    """语法错误信息"""
    
    def __init__(self, line: int, column: int, message: str, severity: str = "error"):
        self.line = line
        self.column = column
        self.message = message
        self.severity = severity  # error, warning
    
    def __str__(self):
        return f"第{self.line}行, 第{self.column}列: {self.message}"
    
    def to_dict(self) -> Dict:
        return {
            "line": self.line,
            "column": self.column,
            "message": self.message,
            "severity": self.severity,
        }


class SyntaxVerifier:
    """
    语法校验器
    
    对Python代码进行静态语法检查。
    """
    
    def __init__(self):
        """初始化语法校验器"""
        self.errors: List[SyntaxErrorInfo] = []
        self.warnings: List[SyntaxErrorInfo] = []
    
    def verify(self, code: str, filename: str = "<unknown>") -> Tuple[bool, List[SyntaxErrorInfo], List[SyntaxErrorInfo]]:
        """
        验证代码语法
        
        Args:
            code: 要验证的代码
            filename: 文件名（用于错误信息）
            
        Returns:
            (是否通过, 错误列表, 警告列表)
        """
        self.errors = []
        self.warnings = []
        
        # 1. AST语法检查
        self._check_ast(code, filename)
        
        # 2. 基础代码风格检查
        self._check_style(code)
        
        # 3. 常见错误模式检查
        self._check_common_errors(code)
        
        return len(self.errors) == 0, self.errors, self.warnings
    
    def _check_ast(self, code: str, filename: str):
        """使用AST进行语法检查"""
        try:
            ast.parse(code, filename=filename)
        except SyntaxError as e:
            self.errors.append(SyntaxErrorInfo(
                line=e.lineno or 1,
                column=e.offset or 0,
                message=f"语法错误: {e.msg}",
                severity="error"
            ))
        except IndentationError as e:
            self.errors.append(SyntaxErrorInfo(
                line=e.lineno or 1,
                column=e.offset or 0,
                message=f"缩进错误: {e.msg}",
                severity="error"
            ))
        except TabError as e:
            self.errors.append(SyntaxErrorInfo(
                line=e.lineno or 1,
                column=e.offset or 0,
                message=f"Tab/空格混用错误: {e.msg}",
                severity="error"
            ))
    
    def _check_style(self, code: str):
        """检查代码风格问题"""
        lines = code.split('\n')
        
        for i, line in enumerate(lines, 1):
            # 检查行尾空格
            if line.rstrip() != line:
                self.warnings.append(SyntaxErrorInfo(
                    line=i,
                    column=len(line.rstrip()) + 1,
                    message="行尾存在多余空格",
                    severity="warning"
                ))
            
            # 检查混合缩进
            if '\t' in line and '    ' in line:
                self.warnings.append(SyntaxErrorInfo(
                    line=i,
                    column=1,
                    message="混合使用Tab和空格缩进",
                    severity="warning"
                ))
    
    def _check_common_errors(self, code: str):
        """检查常见错误模式"""
        # 检查未闭合的括号
        open_brackets = {'(': ')', '[': ']', '{': '}'}
        close_brackets = {')', ']', '}'}
        
        stack = []
        lines = code.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            # 跳过字符串和注释
            in_string = False
            string_char = None
            i = 0
            
            while i < len(line):
                char = line[i]
                
                # 处理字符串
                if char in ('"', "'") and (i == 0 or line[i-1] != '\\'):
                    if not in_string:
                        in_string = True
                        string_char = char
                    elif char == string_char:
                        in_string = False
                        string_char = None
                    i += 1
                    continue
                
                # 跳过注释
                if char == '#' and not in_string:
                    break
                
                # 检查括号
                if not in_string:
                    if char in open_brackets:
                        stack.append((char, line_num, i + 1))
                    elif char in close_brackets:
                        if stack:
                            last_open, _, _ = stack[-1]
                            if open_brackets[last_open] == char:
                                stack.pop()
                            else:
                                self.errors.append(SyntaxErrorInfo(
                                    line=line_num,
                                    column=i + 1,
                                    message=f"括号不匹配: 期望 '{open_brackets[last_open]}' 但找到 '{char}'",
                                    severity="error"
                                ))
                        else:
                            self.errors.append(SyntaxErrorInfo(
                                line=line_num,
                                column=i + 1,
                                message=f"多余的闭合括号: '{char}'",
                                severity="error"
                            ))
                
                i += 1
        
        # 检查未闭合的括号
        for char, line, col in stack:
            self.errors.append(SyntaxErrorInfo(
                line=line,
                column=col,
                message=f"未闭合的括号: '{char}'",
                severity="error"
            ))
    
    def verify_file(self, file_path: Path) -> Tuple[bool, List[SyntaxErrorInfo], List[SyntaxErrorInfo]]:
        """
        验证文件语法
        
        Args:
            file_path: 文件路径
            
        Returns:
            (是否通过, 错误列表, 警告列表)
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            return self.verify(code, str(file_path))
        except Exception as e:
            error = SyntaxErrorInfo(
                line=1,
                column=1,
                message=f"无法读取文件: {str(e)}",
                severity="error"
            )
            return False, [error], []
    
    def format_errors(self, errors: List[SyntaxErrorInfo], warnings: List[SyntaxErrorInfo]) -> str:
        """
        格式化错误信息
        
        Args:
            errors: 错误列表
            warnings: 警告列表
            
        Returns:
            格式化的错误信息字符串
        """
        result = []
        
        if errors:
            result.append(f"❌ 发现 {len(errors)} 个错误:")
            for error in errors:
                result.append(f"  • {error}")
        
        if warnings:
            result.append(f"⚠️ 发现 {len(warnings)} 个警告:")
            for warning in warnings:
                result.append(f"  • {warning}")
        
        if not errors and not warnings:
            result.append("✅ 代码检查通过，未发现语法错误")
        
        return '\n'.join(result)


# 便捷函数
def quick_verify(code: str, filename: str = "<unknown>") -> Tuple[bool, str]:
    """
    快速验证代码语法
    
    Args:
        code: 要验证的代码
        filename: 文件名
        
    Returns:
        (是否通过, 结果信息)
    """
    verifier = SyntaxVerifier()
    passed, errors, warnings = verifier.verify(code, filename)
    message = verifier.format_errors(errors, warnings)
    return passed, message
