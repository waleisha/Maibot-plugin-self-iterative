"""
MaiBot 自我迭代插件 v2.1

一个让 MaiBot 能够自我迭代、自我优化的框架插件。
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
- LLM工具注入: 让AI知道自己有自我迭代的能力
- 独立LLM模型: 支持Claude、Gemini、Kimi等多种模型

作者: MaiBot开发者
版本: 2.1.0
"""

import os
from pathlib import Path
from typing import List, Tuple, Type

# MaiBot插件系统导入
from src.plugin_system import (
    BasePlugin,
    register_plugin,
    ComponentInfo,
    ConfigField,
)
from src.common.logger import get_logger

# 导入工具组件
from .tools import ReadFileTool, WriteFileTool, ExecuteTerminalTool, SelfIterateTool, LLMCodeGenerateTool

# 导入命令组件
from .handlers import (
    IterateCommand,
    ApproveCommand,
    RejectCommand,
    DiffCommand,
    StatusCommand,
    RollbackCommand,
    ListBackupsCommand,
    SelfIterativeInjectHandler,
    SelfIterativePostHandler,
)

# 导入核心模块
from .core.state import iteration_state
from .core.workspace import init_workspace
from .core.patcher import init_patcher
from .core.llm_client import get_llm_client, reset_llm_client

# 获取插件日志记录器
logger = get_logger("self_iterative_plugin")


@register_plugin
class SelfIterativePlugin(BasePlugin):
    """
    MaiBot 自我迭代框架插件
    
    让 MaiBot 能够自我迭代、自我优化的框架插件。
    支持代码读取、修改、校验、差异对比和部署。
    
    核心特性:
    1. 完整的工具集: read_file, write_file, execute_terminal, self_iterate
    2. 命令管理: /iterate, /approve, /reject, /diff, /status, /rollback, /backups
    3. LLM工具注入: 让AI知道自己有自我迭代的能力（PRE_LLM事件）
    4. 独立LLM模型: 支持Claude、Gemini、Kimi等多种模型
    5. 安全机制: 白名单、黑名单、AST语法检查、人工审核
    6. 灾备机制: 自动备份、一键回滚
    """
    
    # 插件基本信息
    plugin_name: str = "self_iterative_plugin"
    enable_plugin: bool = True
    dependencies: List[str] = []
    python_dependencies: List[str] = ["aiohttp"]  # 独立LLM调用需要
    config_file_name: str = "config.toml"
    
    # 配置节描述
    config_section_descriptions = {
        "plugin": "插件基本信息",
        "security": "安全设置（管理员、白名单、黑名单）",
        "iteration": "迭代设置（影子工作区、备份、超时）",
        "llm": "LLM模型配置（支持独立模型）",
        "features": "功能开关",
        "logging": "日志设置"
    }
    
    # 配置Schema定义
    config_schema: dict = {
        "plugin": {
            "config_version": ConfigField(
                type=str, 
                default="2.1.0", 
                description="配置文件版本"
            ),
            "enabled": ConfigField(
                type=bool, 
                default=True, 
                description="是否启用插件"
            ),
        },
        "security": {
            "admin_qqs": ConfigField(
                type=list, 
                default=[123456789], 
                description="超级管理员QQ号列表"
            ),
            "allowed_read_paths": ConfigField(
                type=list, 
                default=[
                    "src",
                    "plugins",
                    "maibot_plugin_self_iterative"
                ], 
                description="允许读取的路径白名单（相对于MaiBot根目录）"
            ),
            "allowed_write_paths": ConfigField(
                type=list, 
                default=[
                    "src",
                    "plugins",
                    "maibot_plugin_self_iterative"
                ], 
                description="允许修改的路径白名单（相对于MaiBot根目录）"
            ),
            "forbidden_patterns": ConfigField(
                type=list, 
                default=[
                    ".*\\.env.*",
                    ".*token.*",
                    ".*password.*",
                    ".*secret.*",
                    ".*credential.*",
                    ".*api_key.*",
                    ".*private.*",
                    ".*config.*"
                ], 
                description="禁止访问的文件模式（正则表达式）"
            ),
            "allowed_commands": ConfigField(
                type=list, 
                default=[
                    "pip", "python", "python3", "git",
                    "ls", "cat", "echo", "mkdir", "touch",
                    "cp", "mv", "find", "grep", "head", "tail",
                    "wc", "diff", "stat", "pwd", "cd"
                ], 
                description="允许的终端命令"
            ),
            "forbidden_commands": ConfigField(
                type=list, 
                default=[
                    "rm -rf /", "rm -rf /*", "dd if=/dev/zero",
                    ":(){ :|:& };:", "> /dev/sda", "mkfs", "fdisk",
                    "format", "del /f /s /q", "rd /s /q",
                    "powershell -Command", "Invoke-Expression", "iex",
                    "wget.*|.*sh", "curl.*|.*sh"
                ], 
                description="禁止的终端命令"
            ),
        },
        "iteration": {
            "shadow_workspace_path": ConfigField(
                type=str, 
                default="storage/.shadow", 
                description="影子工作区路径（相对于插件目录）"
            ),
            "backup_path": ConfigField(
                type=str, 
                default="storage/.backups", 
                description="备份存储路径（相对于插件目录）"
            ),
            "max_backups": ConfigField(
                type=int, 
                default=50, 
                description="最大备份数量"
            ),
            "enable_syntax_check": ConfigField(
                type=bool, 
                default=True, 
                description="是否启用语法检查"
            ),
            "enable_diff_report": ConfigField(
                type=bool, 
                default=True, 
                description="是否启用差异报告"
            ),
            "approval_timeout": ConfigField(
                type=int, 
                default=300, 
                description="审核超时时间（秒）"
            ),
            "restart_delay": ConfigField(
                type=int, 
                default=3, 
                description="重启前等待时间（秒）"
            ),
        },
        "llm": {
            "provider": ConfigField(
                type=str,
                default="default",
                description="LLM提供商: default(框架默认)/openai/anthropic/google/moonshot/deepseek",
                choices=["default", "openai", "anthropic", "google", "moonshot", "deepseek"]
            ),
            "temperature": ConfigField(
                type=float,
                default=0.3,
                description="生成温度(0-1)，越低越保守"
            ),
            "max_tokens": ConfigField(
                type=int,
                default=4096,
                description="最大生成token数"
            ),
        },
        "llm.openai": {
            "model": ConfigField(
                type=str,
                default="gpt-4o",
                description="OpenAI模型名称"
            ),
            "api_key": ConfigField(
                type=str,
                default="",
                description="OpenAI API Key（或设置环境变量OPENAI_API_KEY）"
            ),
            "base_url": ConfigField(
                type=str,
                default="https://api.openai.com/v1",
                description="API基础URL（可替换为代理地址）"
            ),
        },
        "llm.anthropic": {
            "model": ConfigField(
                type=str,
                default="claude-3-5-sonnet-20241022",
                description="Claude模型名称"
            ),
            "api_key": ConfigField(
                type=str,
                default="",
                description="Anthropic API Key（或设置环境变量ANTHROPIC_API_KEY）"
            ),
            "base_url": ConfigField(
                type=str,
                default="https://api.anthropic.com/v1",
                description="API基础URL"
            ),
        },
        "llm.google": {
            "model": ConfigField(
                type=str,
                default="gemini-2.0-flash-exp",
                description="Gemini模型名称"
            ),
            "api_key": ConfigField(
                type=str,
                default="",
                description="Google API Key（或设置环境变量GOOGLE_API_KEY）"
            ),
        },
        "llm.moonshot": {
            "model": ConfigField(
                type=str,
                default="kimi-latest",
                description="Kimi模型名称"
            ),
            "api_key": ConfigField(
                type=str,
                default="",
                description="Moonshot API Key（或设置环境变量MOONSHOT_API_KEY）"
            ),
            "base_url": ConfigField(
                type=str,
                default="https://api.moonshot.cn/v1",
                description="API基础URL"
            ),
        },
        "llm.deepseek": {
            "model": ConfigField(
                type=str,
                default="deepseek-coder",
                description="DeepSeek模型名称"
            ),
            "api_key": ConfigField(
                type=str,
                default="",
                description="DeepSeek API Key（或设置环境变量DEEPSEEK_API_KEY）"
            ),
            "base_url": ConfigField(
                type=str,
                default="https://api.deepseek.com/v1",
                description="API基础URL"
            ),
        },
        "features": {
            "enable_tool_inject": ConfigField(
                type=bool, 
                default=True, 
                description="是否启用LLM工具注入（核心功能）"
            ),
            "enable_auto_backup": ConfigField(
                type=bool, 
                default=True, 
                description="是否启用自动备份"
            ),
            "enable_rollback": ConfigField(
                type=bool, 
                default=True, 
                description="是否启用回滚功能"
            ),
        },
        "logging": {
            "level": ConfigField(
                type=str, 
                default="INFO", 
                description="日志级别"
            ),
            "log_tool_calls": ConfigField(
                type=bool, 
                default=True, 
                description="是否记录工具调用"
            ),
            "log_file_operations": ConfigField(
                type=bool, 
                default=True, 
                description="是否记录文件操作"
            ),
        }
    }
    
    def __init__(self, plugin_dir: str = None):
        super().__init__(plugin_dir)
        self.plugin_dir = Path(plugin_dir) if plugin_dir else Path(__file__).parent
        self.mai_bot_root = self._find_maibot_root()
        self.shadow_dir = self._get_shadow_dir()
        self.backup_dir = self._get_backup_dir()
        
        # 初始化核心模块
        self._init_core_modules()
        
        # 初始化LLM客户端
        self._init_llm_client()
    
    def _find_maibot_root(self) -> Path:
        """查找MaiBot根目录"""
        current = self.plugin_dir
        while current.parent != current:
            if (current / "bot.py").exists() or (current / "main.py").exists():
                return current
            current = current.parent
        return self.plugin_dir.parent.parent
    
    def _get_shadow_dir(self) -> Path:
        """获取影子工作区目录"""
        shadow_path = self.get_config("iteration.shadow_workspace_path", "storage/.shadow")
        if os.path.isabs(shadow_path):
            return Path(shadow_path)
        return self.plugin_dir / shadow_path
    
    def _get_backup_dir(self) -> Path:
        """获取备份目录"""
        backup_path = self.get_config("iteration.backup_path", "storage/.backups")
        if os.path.isabs(backup_path):
            return Path(backup_path)
        return self.plugin_dir / backup_path
    
    def _init_core_modules(self):
        """初始化核心模块"""
        try:
            # 初始化工作区管理器
            init_workspace(self.mai_bot_root, self.shadow_dir)
            logger.info(f"[SelfIterativePlugin] 工作区管理器已初始化: {self.shadow_dir}")
            
            # 初始化部署器
            init_patcher(self.mai_bot_root, self.backup_dir)
            logger.info(f"[SelfIterativePlugin] 部署器已初始化: {self.backup_dir}")
            
        except Exception as e:
            logger.error(f"[SelfIterativePlugin] 初始化核心模块失败: {e}")
    
    def _init_llm_client(self):
        """初始化LLM客户端"""
        try:
            # 获取配置字典
            config_dict = self._get_config_dict()
            client = get_llm_client(config_dict)
            logger.info("[SelfIterativePlugin] LLM客户端已初始化")
        except Exception as e:
            logger.error(f"[SelfIterativePlugin] 初始化LLM客户端失败: {e}")
    
    def _get_config_dict(self) -> dict:
        """获取配置字典"""
        return {
            "plugin": {"enabled": self.get_config("plugin.enabled", True)},
            "llm": {
                "provider": self.get_config("llm.provider", "default"),
                "temperature": self.get_config("llm.temperature", 0.3),
                "max_tokens": self.get_config("llm.max_tokens", 4096),
                "openai": {
                    "model": self.get_config("llm.openai.model", "gpt-4o"),
                    "api_key": self.get_config("llm.openai.api_key", ""),
                    "base_url": self.get_config("llm.openai.base_url", "https://api.openai.com/v1"),
                },
                "anthropic": {
                    "model": self.get_config("llm.anthropic.model", "claude-3-5-sonnet-20241022"),
                    "api_key": self.get_config("llm.anthropic.api_key", ""),
                    "base_url": self.get_config("llm.anthropic.base_url", "https://api.anthropic.com/v1"),
                },
                "google": {
                    "model": self.get_config("llm.google.model", "gemini-2.0-flash-exp"),
                    "api_key": self.get_config("llm.google.api_key", ""),
                },
                "moonshot": {
                    "model": self.get_config("llm.moonshot.model", "kimi-latest"),
                    "api_key": self.get_config("llm.moonshot.api_key", ""),
                    "base_url": self.get_config("llm.moonshot.base_url", "https://api.moonshot.cn/v1"),
                },
                "deepseek": {
                    "model": self.get_config("llm.deepseek.model", "deepseek-coder"),
                    "api_key": self.get_config("llm.deepseek.api_key", ""),
                    "base_url": self.get_config("llm.deepseek.base_url", "https://api.deepseek.com/v1"),
                },
            },
        }
    
    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        """
        返回插件组件列表
        
        Returns:
            List[Tuple[ComponentInfo, Type]]: 组件信息列表
        """
        components = []
        
        # 注册事件处理器（LLM工具注入）
        # 关键：使用 PRE_LLM 在LLM调用前注入
        components.append((
            SelfIterativeInjectHandler.get_handler_info(),
            SelfIterativeInjectHandler
        ))
        logger.info("[SelfIterativePlugin] 已注册LLM工具注入处理器 (PRE_LLM)")
        
        # 注册后置处理器
        components.append((
            SelfIterativePostHandler.get_handler_info(),
            SelfIterativePostHandler
        ))
        logger.info("[SelfIterativePlugin] 已注册LLM后置处理器 (POST_LLM)")
        
        # 注册工具组件
        components.extend([
            (ReadFileTool.get_tool_info(), ReadFileTool),
            (WriteFileTool.get_tool_info(), WriteFileTool),
            (ExecuteTerminalTool.get_tool_info(), ExecuteTerminalTool),
            (SelfIterateTool.get_tool_info(), SelfIterateTool),
            (LLMCodeGenerateTool.get_tool_info(), LLMCodeGenerateTool),
        ])
        logger.info("[SelfIterativePlugin] 已注册工具组件 (含LLM代码生成工具)")
        
        # 注册命令组件
        components.extend([
            (IterateCommand.get_command_info(), IterateCommand),
            (ApproveCommand.get_command_info(), ApproveCommand),
            (RejectCommand.get_command_info(), RejectCommand),
            (DiffCommand.get_command_info(), DiffCommand),
            (StatusCommand.get_command_info(), StatusCommand),
            (RollbackCommand.get_command_info(), RollbackCommand),
            (ListBackupsCommand.get_command_info(), ListBackupsCommand),
        ])
        logger.info("[SelfIterativePlugin] 已注册命令组件")
        
        return components
    
    async def on_load(self):
        """插件加载时调用"""
        logger.info("=" * 60)
        logger.info("[SelfIterativePlugin] 自我迭代框架插件已加载")
        logger.info("=" * 60)
        
        # 确保必要的目录存在
        self.shadow_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"[SelfIterativePlugin] MaiBot根目录: {self.mai_bot_root}")
        logger.info(f"[SelfIterativePlugin] 影子工作区: {self.shadow_dir}")
        logger.info(f"[SelfIterativePlugin] 备份目录: {self.backup_dir}")
        
        # 显示配置信息
        admin_qqs = self.get_config("security.admin_qqs", [])
        logger.info(f"[SelfIterativePlugin] 管理员QQ: {admin_qqs}")
        
        allowed_read = self.get_config("security.allowed_read_paths", [])
        logger.info(f"[SelfIterativePlugin] 允许读取的路径: {allowed_read}")
        
        allowed_write = self.get_config("security.allowed_write_paths", [])
        logger.info(f"[SelfIterativePlugin] 允许写入的路径: {allowed_write}")
        
        # 显示LLM配置
        llm_provider = self.get_config("llm.provider", "default")
        logger.info(f"[SelfIterativePlugin] LLM提供商: {llm_provider}")
        
        logger.info("=" * 60)
    
    async def on_unload(self):
        """插件卸载时调用"""
        logger.info("[SelfIterativePlugin] 自我迭代框架插件已卸载")
        reset_llm_client()
    
    async def on_enable(self):
        """插件启用时调用"""
        logger.info("[SelfIterativePlugin] 自我迭代框架插件已启用")
    
    async def on_disable(self):
        """插件禁用时调用"""
        logger.info("[SelfIterativePlugin] 自我迭代框架插件已禁用")
