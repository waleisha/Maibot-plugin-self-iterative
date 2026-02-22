"""
语法验证器 - 使用AST进行Python代码语法检查
"""

import ast
from pathlib import Path
from typing import Tuple, List
from src.common.logger import get_logger

logger = get_logger("self_iterative_plugin.core.verifier")


class SyntaxVerifier:
    """
    语法验证器 - 负责AST语法检查
    
    功能:
    - Python代码语法检查
    - 导入语句验证
    - 基本代码结构检查
    """
    
    def __init__(self):
        self.errors: List[str] = []
    
    def verify(self, content: str, file_path: str = "") -> Tuple[bool, List[str]]:
        """
        验证代码语法
        
        Args:
            content: 代码内容
            file_path: 文件路径（用于错误信息）
        
        Returns:
            (是否通过, 错误列表)
        """
        self.errors = []
        
        # 检查是否是Python文件
        if file_path and not file_path.endswith('.py'):
            return True, ["非Python文件，跳过语法检查"]
        
        try:
            # AST解析
            tree = ast.parse(content)
            
            # 检查导入语句
            self._check_imports(tree)
            
            # 检查危险操作
            self._check_dangerous_operations(tree)
            
            if self.errors:
                logger.warning(f"[SyntaxVerifier] 代码验证发现 {len(self.errors)} 个问题")
                return False, self.errors
            
            logger.info(f"[SyntaxVerifier] 代码验证通过")
            return True, ["语法检查通过"]
            
        except SyntaxError as e:
            error_msg = f"语法错误: 第{e.lineno}行, 第{e.offset}列 - {e.msg}"
            self.errors.append(error_msg)
            logger.error(f"[SyntaxVerifier] {error_msg}")
            return False, self.errors
        except Exception as e:
            error_msg = f"验证异常: {str(e)}"
            self.errors.append(error_msg)
            logger.error(f"[SyntaxVerifier] {error_msg}")
            return False, self.errors
    
    def _check_imports(self, tree: ast.AST) -> None:
        """检查导入语句"""
        dangerous_modules = [
            'os.system', 'subprocess', 'eval', 'exec', 'compile',
            '__import__', 'importlib', 'sys.modules'
        ]
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_name = alias.name
                        if any(dangerous in module_name for dangerous in dangerous_modules):
                            self.errors.append(f"警告: 检测到潜在危险导入 '{module_name}'")
                
                elif isinstance(node, ast.ImportFrom):
                    module_name = node.module or ""
                    if any(dangerous in module_name for dangerous in dangerous_modules):
                        self.errors.append(f"警告: 检测到潜在危险导入 '{module_name}'")
    
    def _check_dangerous_operations(self, tree: ast.AST) -> None:
        """检查危险操作"""
        for node in ast.walk(tree):
            # 检查eval调用
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ['eval', 'exec']:
                        self.errors.append(f"警告: 检测到危险函数调用 '{node.func.id}'")
            
            # 检查__import__
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id == '__import__':
                        self.errors.append("警告: 检测到 __import__ 调用")
    
    def verify_file(self, file_path: Path) -> Tuple[bool, List[str]]:
        """验证文件"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            return self.verify(content, str(file_path))
        except Exception as e:
            error_msg = f"读取文件失败: {str(e)}"
            logger.error(f"[SyntaxVerifier] {error_msg}")
            return False, [error_msg]


# 全局验证器实例
verifier = SyntaxVerifier()
