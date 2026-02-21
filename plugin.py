"""
MaiBot自我迭代框架插件
======================

一个让MaiBot能够自我迭代、自我优化的框架插件。
支持代码读取、修改、校验、差异对比和部署，包含完整的安全审核机制。

主要功能:
- 代码读取工具: 安全读取白名单内的源代码
- 代码写入工具: 将修改写入影子工作区
- 终端执行工具: 执行安全的系统命令
- AST语法校验: 自动检查代码语法错误
- 差异生成器: 生成Git风格的diff报告
- 人工审核机制: 管理员确认后才应用修改
- 自动备份系统: 修改前自动备份原文件
- 一键回滚功能: 支持快速回滚到历史版本

作者: MaiBot开发者
版本: 1.0.0
"""

import os
import sys
import ast
import shutil
import difflib
import asyncio
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Type, Any, Optional, Dict

# MaiBot插件系统导入
from src.plugin_system import (
    BasePlugin,
    register_plugin,
    BaseAction,
    BaseCommand,
    BaseTool,
    ComponentInfo,
    ActionActivationType,
    ConfigField,
    BaseEventHandler,
    EventType,
    MaiMessages,
    ToolParamType,
    ReplyContentType,
)
from src.config.config import global_config
from src.common.logger import get_logger

# 获取插件日志记录器
logger = get_logger("self_iterative_plugin")

# ============================================================================
# 全局状态管理
# ============================================================================

class IterationState:
    """迭代状态管理器 - 单例模式"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.reset()
        return cls._instance
    
    def reset(self):
        """重置状态"""
        self.status = "idle"  # idle, pending, approved, rejected, error
        self.pending_files: Dict[str, str] = {}  # 等待审核的文件 {target_path: shadow_path}
        self.diff_report: str = ""  # 差异报告
        self.requester: Optional[str] = None  # 请求者ID
        self.request_time: Optional[datetime] = None  # 请求时间
        self.error_message: Optional[str] = None  # 错误信息
        self.iteration_id: Optional[str] = None  # 本次迭代ID

# 全局状态实例
iteration_state = IterationState()

# ============================================================================
# 工具组件 (Tools)
# ============================================================================

class ReadFileTool(BaseTool):
    """
    源码读取工具 - 让大模型能够读取MaiBot框架或插件的源代码
    
    安全特性:
    - 严格的目录白名单控制
    - 禁止读取敏感文件(.env, token, password等)
    - 支持相对路径和绝对路径
    """
    
    name = "read_file"
    description = "读取指定路径的源代码文件内容，支持Python、JSON、TOML、Markdown等文本文件"
    available_for_llm = True
    
    parameters = [
        ("file_path", ToolParamType.STRING, "要读取的文件路径，可以是相对路径或绝对路径", True, None),
        ("offset", ToolParamType.INTEGER, "起始行号（从1开始），用于读取大文件的部分内容", False, 1),
        ("limit", ToolParamType.INTEGER, "最大读取行数，默认读取1000行", False, 1000),
    ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plugin_dir = Path(__file__).parent
        self.mai_bot_root = self._find_maibot_root()
    
    def _find_maibot_root(self) -> Path:
        """查找MaiBot根目录"""
        current = self.plugin_dir
        # 向上查找直到找到包含bot.py的目录
        while current.parent != current:
            if (current / "bot.py").exists():
                return current
            current = current.parent
        # 如果找不到，返回插件目录的父目录
        return self.plugin_dir.parent.parent
    
    def _get_allowed_paths(self) -> List[Path]:
        """获取允许的读取路径列表"""
        allowed = self.get_config("security.allowed_read_paths", ["src/plugins", "plugins"])
        paths = []
        for path_str in allowed:
            if os.path.isabs(path_str):
                paths.append(Path(path_str))
            else:
                paths.append(self.mai_bot_root / path_str)
        return paths
    
    def _is_path_allowed(self, file_path: Path) -> Tuple[bool, str]:
        """检查路径是否在白名单内"""
        # 解析为绝对路径
        if not file_path.is_absolute():
            file_path = self.mai_bot_root / file_path
        file_path = file_path.resolve()
        
        # 检查是否在白名单内
        allowed_paths = self._get_allowed_paths()
        in_whitelist = any(self._is_subpath(file_path, allowed) for allowed in allowed_paths)
        if not in_whitelist:
            return False, f"路径不在允许的白名单内: {file_path}"
        
        # 检查是否匹配禁止模式
        forbidden_patterns = self.get_config("security.forbidden_patterns", [])
        path_str = str(file_path).lower()
        for pattern in forbidden_patterns:
            import re
            if re.search(pattern, path_str, re.IGNORECASE):
                return False, f"路径匹配禁止访问的模式: {pattern}"
        
        # 检查文件是否存在
        if not file_path.exists():
            return False, f"文件不存在: {file_path}"
        
        if not file_path.is_file():
            return False, f"路径不是文件: {file_path}"
        
        return True, ""
    
    def _is_subpath(self, path: Path, parent: Path) -> bool:
        """检查path是否是parent的子路径"""
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            return False
    
    async def execute(self, function_args: Dict[str, Any]) -> Dict[str, Any]:
        """执行文件读取"""
        file_path_str = function_args.get("file_path", "")
        offset = function_args.get("offset", 1)
        limit = function_args.get("limit", 1000)
        
        try:
            file_path = Path(file_path_str)
            
            # 安全检查
            is_allowed, error_msg = self._is_path_allowed(file_path)
            if not is_allowed:
                logger.warning(f"[ReadFileTool] 拒绝读取文件: {error_msg}")
                return {
                    "name": self.name,
                    "content": f"❌ 读取失败: {error_msg}",
                    "success": False
                }
            
            # 解析为绝对路径
            if not file_path.is_absolute():
                file_path = self.mai_bot_root / file_path
            file_path = file_path.resolve()
            
            # 读取文件内容
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            except UnicodeDecodeError:
                return {
                    "name": self.name,
                    "content": f"❌ 文件不是有效的UTF-8文本文件: {file_path}",
                    "success": False
                }
            
            # 计算实际行范围
            total_lines = len(lines)
            start_idx = max(0, offset - 1)
            end_idx = min(total_lines, start_idx + limit)
            
            # 提取指定范围的行
            selected_lines = lines[start_idx:end_idx]
            content = ''.join(selected_lines)
            
            # 格式化输出
            result = f"📄 文件: {file_path}\n"
            result += f"📊 总行数: {total_lines}, 显示行: {start_idx + 1}-{end_idx}\n"
            result += "=" * 50 + "\n"
            result += content
            
            if end_idx < total_lines:
                result += f"\n... (还有 {total_lines - end_idx} 行未显示)"
            
            logger.info(f"[ReadFileTool] 成功读取文件: {file_path} ({total_lines}行)")
            
            return {
                "name": self.name,
                "content": result,
                "success": True,
                "file_path": str(file_path),
                "total_lines": total_lines,
                "displayed_lines": end_idx - start_idx
            }
            
        except Exception as e:
            error_msg = f"读取文件时发生错误: {str(e)}"
            logger.error(f"[ReadFileTool] {error_msg}")
            return {
                "name": self.name,
                "content": f"❌ {error_msg}",
                "success": False
            }


class WriteFileTool(BaseTool):
    """
    源码写入工具 - 将大模型修改后的代码写入影子工作区
    
    安全特性:
    - 绝不直接覆盖原文件
    - 所有写入都重定向到影子工作区
    - 写入后自动进行AST语法检查
    """
    
    name = "write_file"
    description = "将修改后的代码写入影子工作区，等待人工审核。支持Python、JSON、TOML等文本文件"
    available_for_llm = True
    
    parameters = [
        ("target_path", ToolParamType.STRING, "目标文件路径（相对于MaiBot根目录）", True, None),
        ("content", ToolParamType.STRING, "要写入的文件内容", True, None),
        ("append", ToolParamType.BOOLEAN, "是否追加模式，默认为False（覆盖）", False, False),
    ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plugin_dir = Path(__file__).parent
        self.mai_bot_root = self._find_maibot_root()
        self.shadow_dir = self._get_shadow_dir()
    
    def _find_maibot_root(self) -> Path:
        """查找MaiBot根目录"""
        current = self.plugin_dir
        while current.parent != current:
            if (current / "bot.py").exists():
                return current
            current = current.parent
        return self.plugin_dir.parent.parent
    
    def _get_shadow_dir(self) -> Path:
        """获取影子工作区目录"""
        shadow_path = self.get_config("iteration.shadow_workspace_path", "storage/.shadow")
        if os.path.isabs(shadow_path):
            return Path(shadow_path)
        return self.plugin_dir / shadow_path
    
    def _get_allowed_write_paths(self) -> List[Path]:
        """获取允许的写入路径列表"""
        allowed = self.get_config("security.allowed_write_paths", ["plugins"])
        paths = []
        for path_str in allowed:
            if os.path.isabs(path_str):
                paths.append(Path(path_str))
            else:
                paths.append(self.mai_bot_root / path_str)
        return paths
    
    def _is_write_allowed(self, target_path: Path) -> Tuple[bool, str]:
        """检查目标路径是否允许写入"""
        # 解析为绝对路径
        abs_target = self.mai_bot_root / target_path
        abs_target = abs_target.resolve()
        
        # 检查是否在写入白名单内
        allowed_paths = self._get_allowed_write_paths()
        in_whitelist = any(self._is_subpath(abs_target, allowed) for allowed in allowed_paths)
        if not in_whitelist:
            return False, f"目标路径不在允许的白名单内: {target_path}"
        
        # 检查禁止模式
        forbidden_patterns = self.get_config("security.forbidden_patterns", [])
        path_str = str(abs_target).lower()
        for pattern in forbidden_patterns:
            import re
            if re.search(pattern, path_str, re.IGNORECASE):
                return False, f"路径匹配禁止访问的模式: {pattern}"
        
        return True, ""
    
    def _is_subpath(self, path: Path, parent: Path) -> bool:
        """检查path是否是parent的子路径"""
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            return False
    
    def _syntax_check(self, content: str) -> Tuple[bool, str]:
        """对Python代码进行AST语法检查"""
        enable_check = self.get_config("iteration.enable_syntax_check", True)
        if not enable_check:
            return True, "语法检查已禁用"
        
        try:
            ast.parse(content)
            return True, "语法检查通过"
        except SyntaxError as e:
            return False, f"语法错误: 第{e.lineno}行, {e.msg}"
        except Exception as e:
            return False, f"语法检查异常: {str(e)}"
    
    async def execute(self, function_args: Dict[str, Any]) -> Dict[str, Any]:
        """执行文件写入"""
        target_path_str = function_args.get("target_path", "")
        content = function_args.get("content", "")
        append = function_args.get("append", False)
        
        try:
            target_path = Path(target_path_str)
            
            # 安全检查
            is_allowed, error_msg = self._is_write_allowed(target_path)
            if not is_allowed:
                logger.warning(f"[WriteFileTool] 拒绝写入文件: {error_msg}")
                return {
                    "name": self.name,
                    "content": f"❌ 写入失败: {error_msg}",
                    "success": False
                }
            
            # 如果是Python文件，进行语法检查
            if target_path.suffix == '.py':
                syntax_ok, syntax_msg = self._syntax_check(content)
                if not syntax_ok:
                    return {
                        "name": self.name,
                        "content": f"❌ 语法检查失败: {syntax_msg}\n请修复语法错误后重新写入。",
                        "success": False
                    }
            
            # 构建影子文件路径
            shadow_path = self.shadow_dir / target_path
            shadow_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入影子工作区
            mode = 'a' if append else 'w'
            with open(shadow_path, mode, encoding='utf-8') as f:
                f.write(content)
            
            # 记录到待审核列表
            global iteration_state
            iteration_state.pending_files[str(target_path)] = str(shadow_path)
            
            logger.info(f"[WriteFileTool] 成功写入影子文件: {shadow_path}")
            
            return {
                "name": self.name,
                "content": f"✅ 文件已写入影子工作区\n📄 目标路径: {target_path}\n📝 影子路径: {shadow_path}\n📏 内容长度: {len(content)} 字符",
                "success": True,
                "target_path": str(target_path),
                "shadow_path": str(shadow_path)
            }
            
        except Exception as e:
            error_msg = f"写入文件时发生错误: {str(e)}"
            logger.error(f"[WriteFileTool] {error_msg}")
            return {
                "name": self.name,
                "content": f"❌ {error_msg}",
                "success": False
            }


class ExecuteTerminalTool(BaseTool):
    """
    虚拟终端工具 - 执行安全的系统命令
    
    安全特性:
    - 严格的命令白名单
    - 禁止执行危险命令
    - 超时控制
    """
    
    name = "execute_terminal"
    description = "执行安全的终端命令，如pip install、git操作等。危险命令会被拦截"
    available_for_llm = True
    
    parameters = [
        ("command", ToolParamType.STRING, "要执行的命令", True, None),
        ("timeout", ToolParamType.INTEGER, "命令超时时间（秒），默认60秒", False, 60),
        ("working_dir", ToolParamType.STRING, "工作目录，默认为MaiBot根目录", False, None),
    ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plugin_dir = Path(__file__).parent
        self.mai_bot_root = self._find_maibot_root()
    
    def _find_maibot_root(self) -> Path:
        """查找MaiBot根目录"""
        current = self.plugin_dir
        while current.parent != current:
            if (current / "bot.py").exists():
                return current
            current = current.parent
        return self.plugin_dir.parent.parent
    
    def _is_command_allowed(self, command: str) -> Tuple[bool, str]:
        """检查命令是否允许执行"""
        # 获取允许的命令列表
        allowed_commands = self.get_config("security.allowed_commands", ["pip", "python", "git"])
        forbidden_commands = self.get_config("security.forbidden_commands", [])
        
        # 解析命令（去除参数）
        cmd_parts = command.strip().split()
        if not cmd_parts:
            return False, "命令不能为空"
        
        base_cmd = cmd_parts[0].lower()
        
        # 检查是否在禁止列表中
        for forbidden in forbidden_commands:
            if forbidden.lower() in command.lower():
                return False, f"命令包含禁止的操作: {forbidden}"
        
        # 检查是否在白名单中
        if base_cmd not in [cmd.lower() for cmd in allowed_commands]:
            return False, f"命令 '{base_cmd}' 不在允许的白名单中"
        
        return True, ""
    
    async def execute(self, function_args: Dict[str, Any]) -> Dict[str, Any]:
        """执行终端命令"""
        command = function_args.get("command", "")
        timeout = function_args.get("timeout", 60)
        working_dir_str = function_args.get("working_dir", None)
        
        try:
            # 安全检查
            is_allowed, error_msg = self._is_command_allowed(command)
            if not is_allowed:
                logger.warning(f"[ExecuteTerminalTool] 拒绝执行命令: {error_msg}")
                return {
                    "name": self.name,
                    "content": f"❌ 命令被拒绝: {error_msg}",
                    "success": False
                }
            
            # 确定工作目录
            working_dir = self.mai_bot_root
            if working_dir_str:
                working_dir = Path(working_dir_str)
                if not working_dir.exists():
                    return {
                        "name": self.name,
                        "content": f"❌ 工作目录不存在: {working_dir}",
                        "success": False
                    }
            
            logger.info(f"[ExecuteTerminalTool] 执行命令: {command}")
            
            # 执行命令
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return {
                    "name": self.name,
                    "content": f"⏱️ 命令执行超时（{timeout}秒）",
                    "success": False
                }
            
            # 解析输出
            stdout_str = stdout.decode('utf-8', errors='replace') if stdout else ""
            stderr_str = stderr.decode('utf-8', errors='replace') if stderr else ""
            
            # 构建结果
            result = f"📟 命令: {command}\n"
            result += f"📂 工作目录: {working_dir}\n"
            result += f"🔢 返回码: {process.returncode}\n"
            result += "=" * 50 + "\n"
            
            if stdout_str:
                result += f"📤 标准输出:\n{stdout_str}\n"
            
            if stderr_str:
                result += f"📥 标准错误:\n{stderr_str}\n"
            
            success = process.returncode == 0
            
            logger.info(f"[ExecuteTerminalTool] 命令执行完成，返回码: {process.returncode}")
            
            return {
                "name": self.name,
                "content": result,
                "success": success,
                "return_code": process.returncode,
                "stdout": stdout_str,
                "stderr": stderr_str
            }
            
        except Exception as e:
            error_msg = f"执行命令时发生错误: {str(e)}"
            logger.error(f"[ExecuteTerminalTool] {error_msg}")
            return {
                "name": self.name,
                "content": f"❌ {error_msg}",
                "success": False
            }


# ============================================================================
# 命令组件 (Commands)
# ============================================================================

class IterateCommand(BaseCommand):
    """
    触发自我迭代命令
    
    用法: /iterate [目标文件或描述]
    示例: /iterate 优化message_router.py的日志输出
    """
    
    command_name = "iterate"
    command_description = "触发自我迭代流程，让MaiBot分析并优化指定代码"
    command_pattern = r"^/iterate(?P<target>\s+.+)?$"
    
    async def execute(self) -> Tuple[bool, str, bool]:
        """执行迭代命令"""
        global iteration_state
        
        # 获取目标参数
        target = self.matched_groups.get("target", "").strip() if self.matched_groups else ""
        
        # 检查当前状态
        if iteration_state.status == "pending":
            return True, "⏳ 当前有迭代请求正在等待审核，请先处理当前请求。\n使用 /diff 查看差异，/approve 确认应用，/reject 打回修改。", True
        
        # 重置状态
        iteration_state.reset()
        iteration_state.status = "pending"
        iteration_state.requester = str(self.message.user_id) if self.message else "unknown"
        iteration_state.request_time = datetime.now()
        iteration_state.iteration_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 构建提示信息
        message = "🚀 **自我迭代流程已启动**\n\n"
        message += f"🆔 迭代ID: {iteration_state.iteration_id}\n"
        message += f"👤 请求者: {iteration_state.requester}\n"
        message += f"🕐 时间: {iteration_state.request_time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        if target:
            message += f"🎯 目标: {target}\n\n"
        
        message += "📋 **可用工具:**\n"
        message += "• `read_file` - 读取源代码文件\n"
        message += "• `write_file` - 将修改写入影子工作区\n"
        message += "• `execute_terminal` - 执行安全命令\n\n"
        
        message += "⚠️ **安全提醒:**\n"
        message += "• 所有修改都会先写入影子工作区\n"
        message += "• 需要管理员审核后才能应用\n"
        message += "• 修改前会自动备份原文件\n\n"
        
        message += "💡 **提示:** 你可以直接告诉我你想优化什么，我会使用工具来完成迭代。"
        
        logger.info(f"[IterateCommand] 迭代流程启动: {iteration_state.iteration_id}")
        
        return True, message, True


class ApproveCommand(BaseCommand):
    """
    审核通过命令 - 应用影子工作区的修改
    
    用法: /approve 或 /允许 或 /确认 或 /同意
    """
    
    command_name = "approve"
    command_description = "审核通过并应用影子工作区的修改"
    command_pattern = r"^/(approve|允许|确认|同意)$"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plugin_dir = Path(__file__).parent
        self.mai_bot_root = self._find_maibot_root()
        self.backup_dir = self._get_backup_dir()
    
    def _find_maibot_root(self) -> Path:
        """查找MaiBot根目录"""
        current = self.plugin_dir
        while current.parent != current:
            if (current / "bot.py").exists():
                return current
            current = current.parent
        return self.plugin_dir.parent.parent
    
    def _get_backup_dir(self) -> Path:
        """获取备份目录"""
        backup_path = self.get_config("iteration.backup_path", "storage/.backups")
        if os.path.isabs(backup_path):
            return Path(backup_path)
        return self.plugin_dir / backup_path
    
    def _is_admin(self, user_id: str) -> bool:
        """检查用户是否是管理员"""
        admin_qqs = self.get_config("security.admin_qqs", [])
        return int(user_id) in admin_qqs if admin_qqs else True
    
    def _generate_diff(self, original_path: Path, new_content: str) -> str:
        """生成差异报告"""
        try:
            if original_path.exists():
                with open(original_path, 'r', encoding='utf-8') as f:
                    original_lines = f.readlines()
            else:
                original_lines = []
            
            new_lines = new_content.splitlines(keepends=True)
            if new_lines and not new_lines[-1].endswith('\n'):
                new_lines[-1] += '\n'
            
            diff = difflib.unified_diff(
                original_lines,
                new_lines,
                fromfile=str(original_path),
                tofile=str(original_path) + " (modified)",
                lineterm=''
            )
            
            return ''.join(diff)
        except Exception as e:
            return f"生成差异失败: {str(e)}"
    
    async def execute(self) -> Tuple[bool, str, bool]:
        """执行审核通过操作"""
        global iteration_state
        
        # 检查权限
        user_id = str(self.message.user_id) if self.message else "unknown"
        if not self._is_admin(user_id):
            return True, "❌ 你没有权限执行此操作，请联系管理员。", True
        
        # 检查状态
        if iteration_state.status != "pending":
            return True, "ℹ️ 当前没有等待审核的迭代请求。", True
        
        if not iteration_state.pending_files:
            return True, "ℹ️ 影子工作区中没有待应用的文件。", True
        
        try:
            applied_files = []
            backup_files = []
            
            for target_path_str, shadow_path_str in iteration_state.pending_files.items():
                target_path = self.mai_bot_root / target_path_str
                shadow_path = Path(shadow_path_str)
                
                # 读取影子文件内容
                with open(shadow_path, 'r', encoding='utf-8') as f:
                    new_content = f.read()
                
                # 备份原文件
                if target_path.exists():
                    backup_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_filename = f"{target_path.name}.{backup_timestamp}.bak"
                    backup_path = self.backup_dir / backup_filename
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    shutil.copy2(target_path, backup_path)
                    backup_files.append(str(backup_path))
                
                # 确保目标目录存在
                target_path.parent.mkdir(parents=True, exist_ok=True)
                
                # 写入目标文件
                with open(target_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                applied_files.append(target_path_str)
                logger.info(f"[ApproveCommand] 已应用修改: {target_path}")
            
            # 清理影子文件
            for shadow_path_str in iteration_state.pending_files.values():
                try:
                    Path(shadow_path_str).unlink()
                except:
                    pass
            
            # 更新状态
            iteration_state.status = "approved"
            
            # 构建结果消息
            message = "✅ **修改已应用**\n\n"
            message += f"🆔 迭代ID: {iteration_state.iteration_id}\n"
            message += f"👤 审核者: {user_id}\n"
            message += f"🕐 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            message += "📁 **已应用的文件:**\n"
            for f in applied_files:
                message += f"• {f}\n"
            
            if backup_files:
                message += "\n💾 **备份文件:**\n"
                for f in backup_files:
                    message += f"• {f}\n"
            
            message += "\n⚠️ **注意:** 部分修改可能需要重启MaiBot才能生效。"
            message += "\n💡 使用 `/rollback` 可以回滚到之前的版本。"
            
            logger.info(f"[ApproveCommand] 迭代 {iteration_state.iteration_id} 已审核通过")
            
            return True, message, True
            
        except Exception as e:
            iteration_state.status = "error"
            iteration_state.error_message = str(e)
            error_msg = f"❌ 应用修改时发生错误: {str(e)}"
            logger.error(f"[ApproveCommand] {error_msg}")
            return True, error_msg, True


class RejectCommand(BaseCommand):
    """
    打回修改命令 - 拒绝并清理影子工作区
    
    用法: /reject 或 /拒绝 或 /打回 或 /不同意
    """
    
    command_name = "reject"
    command_description = "打回修改请求，清理影子工作区"
    command_pattern = r"^/(reject|拒绝|打回|不同意)$"
    
    def _is_admin(self, user_id: str) -> bool:
        """检查用户是否是管理员"""
        admin_qqs = self.get_config("security.admin_qqs", [])
        return int(user_id) in admin_qqs if admin_qqs else True
    
    async def execute(self) -> Tuple[bool, str, bool]:
        """执行打回操作"""
        global iteration_state
        
        # 检查权限
        user_id = str(self.message.user_id) if self.message else "unknown"
        if not self._is_admin(user_id):
            return True, "❌ 你没有权限执行此操作，请联系管理员。", True
        
        # 检查状态
        if iteration_state.status != "pending":
            return True, "ℹ️ 当前没有等待审核的迭代请求。", True
        
        try:
            # 清理影子文件
            deleted_files = []
            for shadow_path_str in iteration_state.pending_files.values():
                try:
                    Path(shadow_path_str).unlink()
                    deleted_files.append(shadow_path_str)
                except Exception as e:
                    logger.warning(f"[RejectCommand] 清理影子文件失败: {e}")
            
            # 更新状态
            iteration_id = iteration_state.iteration_id
            iteration_state.status = "rejected"
            
            message = "🚫 **修改已打回**\n\n"
            message += f"🆔 迭代ID: {iteration_id}\n"
            message += f"👤 操作者: {user_id}\n"
            message += f"🕐 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            if deleted_files:
                message += "🗑️ **已清理的影子文件:**\n"
                for f in deleted_files:
                    message += f"• {f}\n"
            
            message += "\n💡 你可以重新发起迭代请求。"
            
            logger.info(f"[RejectCommand] 迭代 {iteration_id} 已打回")
            
            return True, message, True
            
        except Exception as e:
            error_msg = f"❌ 打回修改时发生错误: {str(e)}"
            logger.error(f"[RejectCommand] {error_msg}")
            return True, error_msg, True


class DiffCommand(BaseCommand):
    """
    查看差异命令 - 显示影子工作区与原文件的差异
    
    用法: /diff
    """
    
    command_name = "diff"
    command_description = "查看当前修改的差异报告"
    command_pattern = r"^/diff$"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plugin_dir = Path(__file__).parent
        self.mai_bot_root = self._find_maibot_root()
    
    def _find_maibot_root(self) -> Path:
        """查找MaiBot根目录"""
        current = self.plugin_dir
        while current.parent != current:
            if (current / "bot.py").exists():
                return current
            current = current.parent
        return self.plugin_dir.parent.parent
    
    def _generate_diff(self, original_path: Path, shadow_path: Path) -> str:
        """生成差异报告"""
        try:
            if original_path.exists():
                with open(original_path, 'r', encoding='utf-8') as f:
                    original_lines = f.readlines()
            else:
                original_lines = []
            
            with open(shadow_path, 'r', encoding='utf-8') as f:
                new_lines = f.readlines()
            
            diff = difflib.unified_diff(
                original_lines,
                new_lines,
                fromfile=f"a/{original_path.relative_to(self.mai_bot_root)}",
                tofile=f"b/{original_path.relative_to(self.mai_bot_root)}",
                lineterm=''
            )
            
            return ''.join(diff)
        except Exception as e:
            return f"生成差异失败: {str(e)}"
    
    async def execute(self) -> Tuple[bool, str, bool]:
        """执行差异查看"""
        global iteration_state
        
        # 检查状态
        if iteration_state.status != "pending":
            return True, "ℹ️ 当前没有等待审核的修改。", True
        
        if not iteration_state.pending_files:
            return True, "ℹ️ 影子工作区中没有待审核的文件。", True
        
        try:
            message = "📊 **差异报告**\n\n"
            message += f"🆔 迭代ID: {iteration_state.iteration_id}\n"
            message += f"📁 待审核文件数: {len(iteration_state.pending_files)}\n\n"
            
            for target_path_str, shadow_path_str in iteration_state.pending_files.items():
                target_path = self.mai_bot_root / target_path_str
                shadow_path = Path(shadow_path_str)
                
                diff = self._generate_diff(target_path, shadow_path)
                
                message += f"📄 **{target_path_str}**\n"
                message += "```diff\n"
                
                # 截断过长的diff
                if len(diff) > 1500:
                    message += diff[:1500] + "\n... (内容已截断)"
                else:
                    message += diff if diff else "(新文件)"
                
                message += "\n```\n\n"
            
            message += "💡 使用 `/approve` 应用修改，或使用 `/reject` 打回。"
            
            return True, message, True
            
        except Exception as e:
            error_msg = f"❌ 生成差异报告时发生错误: {str(e)}"
            logger.error(f"[DiffCommand] {error_msg}")
            return True, error_msg, True


class StatusCommand(BaseCommand):
    """
    查看状态命令 - 显示当前迭代状态
    
    用法: /status
    """
    
    command_name = "status"
    command_description = "查看迭代状态"
    command_pattern = r"^/status$"
    
    async def execute(self) -> Tuple[bool, str, bool]:
        """执行状态查看"""
        global iteration_state
        
        message = "📋 **迭代状态**\n\n"
        message += f"🔄 当前状态: **{iteration_state.status.upper()}**\n"
        
        if iteration_state.iteration_id:
            message += f"🆔 迭代ID: {iteration_state.iteration_id}\n"
        
        if iteration_state.requester:
            message += f"👤 请求者: {iteration_state.requester}\n"
        
        if iteration_state.request_time:
            message += f"🕐 请求时间: {iteration_state.request_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        if iteration_state.pending_files:
            message += f"\n📁 待审核文件 ({len(iteration_state.pending_files)}个):\n"
            for target_path in iteration_state.pending_files.keys():
                message += f"• {target_path}\n"
        
        if iteration_state.error_message:
            message += f"\n❌ 错误信息: {iteration_state.error_message}\n"
        
        message += "\n💡 **可用命令:**\n"
        message += "• `/iterate [目标]` - 发起新的迭代\n"
        message += "• `/diff` - 查看差异\n"
        message += "• `/approve` - 审核通过\n"
        message += "• `/reject` - 打回修改\n"
        message += "• `/rollback [时间戳]` - 回滚版本"
        
        return True, message, True


class RollbackCommand(BaseCommand):
    """
    回滚命令 - 恢复到指定备份版本
    
    用法: /rollback [时间戳]
    示例: /rollback 20240115_143022
    """
    
    command_name = "rollback"
    command_description = "回滚到指定备份版本"
    command_pattern = r"^/rollback(?P<timestamp>\s+\S+)?$"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plugin_dir = Path(__file__).parent
        self.mai_bot_root = self._find_maibot_root()
        self.backup_dir = self._get_backup_dir()
    
    def _find_maibot_root(self) -> Path:
        """查找MaiBot根目录"""
        current = self.plugin_dir
        while current.parent != current:
            if (current / "bot.py").exists():
                return current
            current = current.parent
        return self.plugin_dir.parent.parent
    
    def _get_backup_dir(self) -> Path:
        """获取备份目录"""
        backup_path = self.get_config("iteration.backup_path", "storage/.backups")
        if os.path.isabs(backup_path):
            return Path(backup_path)
        return self.plugin_dir / backup_path
    
    def _is_admin(self, user_id: str) -> bool:
        """检查用户是否是管理员"""
        admin_qqs = self.get_config("security.admin_qqs", [])
        return int(user_id) in admin_qqs if admin_qqs else True
    
    def _list_backups(self) -> List[Tuple[str, Path]]:
        """列出所有备份文件"""
        backups = []
        if self.backup_dir.exists():
            for backup_file in self.backup_dir.glob("*.bak"):
                # 从文件名提取时间戳
                parts = backup_file.stem.split('.')
                if len(parts) >= 2:
                    timestamp = parts[-1]
                    backups.append((timestamp, backup_file))
        return sorted(backups, reverse=True)
    
    async def execute(self) -> Tuple[bool, str, bool]:
        """执行回滚操作"""
        # 检查权限
        user_id = str(self.message.user_id) if self.message else "unknown"
        if not self._is_admin(user_id):
            return True, "❌ 你没有权限执行此操作，请联系管理员。", True
        
        timestamp = self.matched_groups.get("timestamp", "").strip() if self.matched_groups else ""
        
        backups = self._list_backups()
        
        if not timestamp:
            # 显示备份列表
            message = "📋 **可用备份列表**\n\n"
            
            if not backups:
                message += "ℹ️ 暂无备份文件。\n"
            else:
                message += f"共找到 {len(backups)} 个备份:\n\n"
                for i, (ts, backup_path) in enumerate(backups[:10], 1):
                    message += f"{i}. `{ts}` - {backup_path.name}\n"
                
                if len(backups) > 10:
                    message += f"\n... 还有 {len(backups) - 10} 个备份"
                
                message += "\n💡 使用 `/rollback <时间戳>` 回滚到指定版本。"
            
            return True, message, True
        
        # 查找指定时间戳的备份
        matching_backups = [(ts, bp) for ts, bp in backups if timestamp in ts]
        
        if not matching_backups:
            return True, f"❌ 未找到匹配 '{timestamp}' 的备份文件。\n使用 `/rollback` 查看可用备份列表。", True
        
        if len(matching_backups) > 1:
            message = f"⚠️ 找到多个匹配 '{timestamp}' 的备份:\n\n"
            for ts, bp in matching_backups:
                message += f"• `{ts}` - {bp.name}\n"
            message += "\n请提供更精确的时间戳。"
            return True, message, True
        
        # 执行回滚
        ts, backup_path = matching_backups[0]
        
        try:
            # 从备份文件名推断原始文件路径
            # 格式: filename.YYYYMMDD_HHMMSS.bak
            original_name = '.'.join(backup_path.stem.split('.')[:-1])
            
            # 尝试在常见位置查找原始文件
            possible_paths = [
                self.mai_bot_root / "plugins" / original_name,
                self.mai_bot_root / "src" / "plugins" / original_name,
            ]
            
            original_path = None
            for pp in possible_paths:
                if pp.exists():
                    original_path = pp
                    break
            
            if not original_path:
                # 如果找不到，询问用户
                return True, f"⚠️ 无法自动确定原始文件位置。\n备份: {backup_path}\n请手动恢复。", True
            
            # 备份当前文件
            current_backup_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            current_backup_name = f"{original_path.name}.{current_backup_ts}.pre_rollback.bak"
            current_backup_path = self.backup_dir / current_backup_name
            
            if original_path.exists():
                shutil.copy2(original_path, current_backup_path)
            
            # 执行回滚
            shutil.copy2(backup_path, original_path)
            
            message = "✅ **回滚成功**\n\n"
            message += f"📄 目标文件: {original_path}\n"
            message += f"💾 回滚来源: {backup_path.name}\n"
            message += f"📦 当前备份: {current_backup_name}\n"
            message += f"👤 操作者: {user_id}\n"
            message += f"🕐 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            message += "⚠️ 部分修改可能需要重启MaiBot才能生效。"
            
            logger.info(f"[RollbackCommand] 成功回滚: {original_path} <- {backup_path}")
            
            return True, message, True
            
        except Exception as e:
            error_msg = f"❌ 回滚时发生错误: {str(e)}"
            logger.error(f"[RollbackCommand] {error_msg}")
            return True, error_msg, True


# ============================================================================
# 插件注册
# ============================================================================

@register_plugin
class SelfIterativePlugin(BasePlugin):
    """
    MaiBot自我迭代框架插件
    
    让MaiBot能够自我迭代、自我优化的框架插件。
    支持代码读取、修改、校验、差异对比和部署。
    """
    
    # 插件基本信息
    plugin_name: str = "self_iterative_plugin"
    enable_plugin: bool = True
    dependencies: List[str] = []
    python_dependencies: List[str] = []
    config_file_name: str = "config.toml"
    
    # 配置节描述
    config_section_descriptions = {
        "plugin": "插件基本信息",
        "security": "安全设置（管理员、白名单、黑名单）",
        "iteration": "迭代设置（影子工作区、备份、超时）",
        "llm": "LLM设置（模型、温度、token限制）",
        "logging": "日志设置（级别、详细程度）"
    }
    
    # 配置Schema定义
    config_schema: dict = {
        "plugin": {
            "config_version": ConfigField(type=str, default="1.0.0", description="配置文件版本"),
            "enabled": ConfigField(type=bool, default=True, description="是否启用插件"),
        },
        "security": {
            "admin_qqs": ConfigField(type=list, default=[123456789], description="超级管理员QQ号列表"),
            "allowed_read_paths": ConfigField(type=list, default=["src/plugins", "plugins"], description="允许读取的路径白名单"),
            "allowed_write_paths": ConfigField(type=list, default=["plugins"], description="允许修改的路径白名单"),
            "forbidden_patterns": ConfigField(type=list, default=[".*\\.env.*", ".*token.*"], description="禁止访问的文件模式"),
            "allowed_commands": ConfigField(type=list, default=["pip", "python", "git"], description="允许的终端命令"),
            "forbidden_commands": ConfigField(type=list, default=["rm -rf /"], description="禁止的终端命令"),
        },
        "iteration": {
            "shadow_workspace_path": ConfigField(type=str, default="storage/.shadow", description="影子工作区路径"),
            "backup_path": ConfigField(type=str, default="storage/.backups", description="备份存储路径"),
            "max_backups": ConfigField(type=int, default=50, description="最大备份数量"),
            "enable_syntax_check": ConfigField(type=bool, default=True, description="是否启用语法检查"),
            "enable_diff_report": ConfigField(type=bool, default=True, description="是否启用差异报告"),
            "approval_timeout": ConfigField(type=int, default=300, description="审核超时时间（秒）"),
            "restart_delay": ConfigField(type=int, default=3, description="重启前等待时间（秒）"),
        },
        "llm": {
            "model_name": ConfigField(type=str, default="default", description="用于代码生成的模型名称"),
            "temperature": ConfigField(type=float, default=0.3, description="代码生成温度"),
            "max_tokens": ConfigField(type=int, default=4096, description="最大生成token数"),
        },
        "logging": {
            "level": ConfigField(type=str, default="INFO", description="日志级别"),
            "log_tool_calls": ConfigField(type=bool, default=True, description="是否记录工具调用"),
            "log_file_operations": ConfigField(type=bool, default=True, description="是否记录文件操作"),
        },
    }
    
    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        """返回插件组件列表"""
        return [
            # 工具组件
            (ReadFileTool.get_tool_info(), ReadFileTool),
            (WriteFileTool.get_tool_info(), WriteFileTool),
            (ExecuteTerminalTool.get_tool_info(), ExecuteTerminalTool),
            # 命令组件
            (IterateCommand.get_command_info(), IterateCommand),
            (ApproveCommand.get_command_info(), ApproveCommand),
            (RejectCommand.get_command_info(), RejectCommand),
            (DiffCommand.get_command_info(), DiffCommand),
            (StatusCommand.get_command_info(), StatusCommand),
            (RollbackCommand.get_command_info(), RollbackCommand),
        ]
    
    async def on_load(self):
        """插件加载时调用"""
        logger.info("[SelfIterativePlugin] 自我迭代框架插件已加载")
        
        # 确保必要的目录存在
        plugin_dir = Path(__file__).parent
        shadow_dir = plugin_dir / "storage" / ".shadow"
        backup_dir = plugin_dir / "storage" / ".backups"
        
        shadow_dir.mkdir(parents=True, exist_ok=True)
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"[SelfIterativePlugin] 影子工作区: {shadow_dir}")
        logger.info(f"[SelfIterativePlugin] 备份目录: {backup_dir}")
    
    async def on_unload(self):
        """插件卸载时调用"""
        logger.info("[SelfIterativePlugin] 自我迭代框架插件已卸载")
