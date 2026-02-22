"""
MaiBot 自我迭代插件 v2.2 (修复版)

一个让 MaiBot 能够自我迭代、自我优化的框架插件。
支持代码读取、修改、校验、差异对比和部署，包含完整的安全审核机制。

主要修复:
1. 修复 'MessageRecv' object has no attribute 'user_id' 错误
2. 简化 LLM 配置，统一为一个配置块
3. 添加强命令和弱命令支持
4. 支持OpenAI兼容格式的所有模型

版本: 2.2.0
"""

from .plugin import SelfIterativePlugin

__all__ = ["SelfIterativePlugin"]
