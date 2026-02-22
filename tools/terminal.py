"""
虚拟终端工具 - 供大模型执行安全的系统命令
"""

import os
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Tuple
from src.plugin_system import BaseTool, ToolParamType
from src.common.logger import get_logger

logger = get_logger("self_iterative_plugin.tools.terminal")


class ExecuteTerminalTool(BaseTool):
    """
    终端执行工具 - 执行安全的系统命令
    
    安全特性:
    - 命令白名单控制
    - 危险命令黑名单
    - 超时机制
    - 工作目录限制
    """
    
    name = "execute_terminal"
    description = "执行安全的系统命令，如pip install、git操作等。有严格的命令白名单和黑名单限制。"
    available_for_llm = True
    
    parameters = [
        ("command", ToolParamType.STRING, "要执行的命令", True, None),
        ("timeout", ToolParamType.INTEGER, "命令超时时间（秒），默认60秒", False, 60),
        ("working_dir", ToolParamType.STRING, "工作目录（相对于MaiBot根目录），默认为MaiBot根目录", False, None),
    ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plugin_dir = Path(__file__).parent.parent
        self.mai_bot_root = self._find_maibot_root()
    
    def _find_maibot_root(self) -> Path:
        """查找MaiBot根目录"""
        current = self.plugin_dir
        while current.parent != current:
            if (current / "bot.py").exists() or (current / "main.py").exists():
                return current
            current = current.parent
        return self.plugin_dir.parent.parent
    
    def _is_command_allowed(self, command: str) -> Tuple[bool, str]:
        """检查命令是否允许执行"""
        # 获取允许的命令前缀
        allowed_commands = self.get_config("security.allowed_commands", [
            "pip", "python", "git", "ls", "cat", "echo", "mkdir", "touch",
            "cp", "mv", "find", "grep", "head", "tail", "wc", "diff"
        ])
        
        # 获取禁止的命令
        forbidden_commands = self.get_config("security.forbidden_commands", [
            "rm -rf /", "rm -rf /*", "dd if=/dev/zero", ":(){ :|:& };:",
            "> /dev/sda", "mkfs", "fdisk", "format", "del /f /s /q",
            "powershell -Command", "Invoke-Expression", "iex",
            "wget.*|.*sh", "curl.*|.*sh", "fetch.*|.*sh"
        ])
        
        # 检查禁止命令
        import re
        cmd_lower = command.lower().strip()
        for forbidden in forbidden_commands:
            try:
                if re.search(forbidden, cmd_lower, re.IGNORECASE):
                    return False, f"命令包含禁止的操作: {forbidden}"
            except re.error:
                if forbidden.lower() in cmd_lower:
                    return False, f"命令包含禁止的操作: {forbidden}"
        
        # 检查是否以允许的命令开头
        cmd_parts = cmd_lower.split()
        if not cmd_parts:
            return False, "空命令"
        
        base_cmd = cmd_parts[0]
        
        # 处理路径形式的命令（如 /usr/bin/python）
        base_cmd_name = os.path.basename(base_cmd)
        
        allowed = False
        for allowed_cmd in allowed_commands:
            if base_cmd == allowed_cmd.lower() or base_cmd_name == allowed_cmd.lower():
                allowed = True
                break
        
        if not allowed:
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
                if not working_dir.is_absolute():
                    working_dir = self.mai_bot_root / working_dir
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
                # 限制输出长度
                max_output = 2000
                if len(stdout_str) > max_output:
                    stdout_str = stdout_str[:max_output] + f"\n... (输出已截断，共 {len(stdout_str)} 字符)"
                result += f"📤 标准输出:\n{stdout_str}\n"
            
            if stderr_str:
                max_error = 1000
                if len(stderr_str) > max_error:
                    stderr_str = stderr_str[:max_error] + f"\n... (错误已截断，共 {len(stderr_str)} 字符)"
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
