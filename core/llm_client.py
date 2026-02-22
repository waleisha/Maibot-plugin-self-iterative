"""
LLM客户端 - 支持独立的自我迭代模型 (v2.2 修复版)

支持多种模型:
- 默认使用MaiBot框架本身的模型
- 可选独立配置: 支持OpenAI兼容格式的所有模型(Claude、Gemini、Kimi、DeepSeek等)

配置方式:
[llm]
enabled = true  # 启用独立LLM
base_url = "https://api.openai.com/v1"  # API基础URL
api_key = "your-api-key"  # API密钥
model = "gpt-4o"  # 模型名称
temperature = 0.3
max_tokens = 4096
"""

import os
import json
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from src.common.logger import get_logger

logger = get_logger("self_iterative_plugin.core.llm_client")


@dataclass
class LLMConfig:
    """LLM配置"""
    enabled: bool  # 是否启用独立LLM
    model: str
    api_key: str
    base_url: str
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: int = 60


class SelfIterativeLLMClient:
    """
    自我迭代专用LLM客户端 (v2.2 修复版)
    
    功能:
    - 支持OpenAI兼容格式的所有模型
    - 自动降级到框架默认模型
    - 代码优化专用prompt
    """
    
    def __init__(self, plugin_config: Dict[str, Any]):
        self.config = plugin_config
        self.llm_config = self._load_llm_config()
        self.use_framework_llm = not self.llm_config.enabled
        
        if not self.use_framework_llm:
            logger.info(f"[LLMClient] 使用独立模型: {self.llm_config.model}")
            logger.info(f"[LLMClient] API地址: {self.llm_config.base_url}")
        else:
            logger.info("[LLMClient] 使用框架默认模型")
    
    def _load_llm_config(self) -> LLMConfig:
        """加载LLM配置 - 支持新的统一配置格式"""
        llm_section = self.config.get("llm", {})
        
        enabled = llm_section.get("enabled", False)
        
        if not enabled:
            return LLMConfig(
                enabled=False,
                model="default",
                api_key="",
                base_url="",
                temperature=llm_section.get("temperature", 0.3),
                max_tokens=llm_section.get("max_tokens", 4096)
            )
        
        # 从环境变量获取API Key（如果配置为空）
        api_key = llm_section.get("api_key", "")
        if not api_key:
            # 尝试从常见环境变量获取
            for env_var in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", 
                           "MOONSHOT_API_KEY", "DEEPSEEK_API_KEY", "LLM_API_KEY"]:
                api_key = os.environ.get(env_var, "")
                if api_key:
                    logger.info(f"[LLMClient] 从环境变量 {env_var} 获取API Key")
                    break
        
        return LLMConfig(
            enabled=True,
            model=llm_section.get("model", "gpt-4o"),
            api_key=api_key,
            base_url=llm_section.get("base_url", "https://api.openai.com/v1"),
            temperature=llm_section.get("temperature", 0.3),
            max_tokens=llm_section.get("max_tokens", 4096),
            timeout=llm_section.get("timeout", 60)
        )
    
    async def generate_code(self, prompt: str, system_prompt: Optional[str] = None) -> Tuple[bool, str]:
        """
        生成代码
        
        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
        
        Returns:
            (是否成功, 生成的代码)
        """
        if self.use_framework_llm:
            return await self._generate_with_framework(prompt, system_prompt)
        
        # 使用独立模型 - 统一使用OpenAI兼容格式
        return await self._generate_openai_compatible(prompt, system_prompt)
    
    async def _generate_with_framework(self, prompt: str, system_prompt: Optional[str] = None) -> Tuple[bool, str]:
        """使用MaiBot框架的LLM生成"""
        try:
            from src.plugin_system import llm_api
            
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            
            # 获取可用模型
            models = llm_api.get_available_models()
            if not models:
                return False, "没有可用的LLM模型"
            
            # 优先使用 tool_use 或 planner 模型
            target_model = None
            for model_name in ["tool_use", "planner", "replyer"]:
                if model_name in models:
                    target_model = models[model_name]
                    break
            
            if not target_model:
                target_model = list(models.values())[0]
            
            success, content, _, _ = await llm_api.generate_with_model(
                full_prompt,
                target_model,
                temperature=self.llm_config.temperature
            )
            
            if success:
                return True, content
            else:
                return False, f"LLM生成失败: {content}"
                
        except Exception as e:
            logger.error(f"[LLMClient] 框架模型调用失败: {e}")
            return False, f"框架模型调用失败: {str(e)}"
    
    async def _generate_openai_compatible(self, prompt: str, system_prompt: Optional[str] = None) -> Tuple[bool, str]:
        """
        使用OpenAI兼容API生成
        
        支持所有OpenAI兼容格式的API:
        - OpenAI (https://api.openai.com/v1)
        - Claude via OpenAI compatibility (https://api.anthropic.com/v1)
        - Gemini via OpenAI compatibility (https://generativelanguage.googleapis.com/v1beta/openai)
        - Moonshot (https://api.moonshot.cn/v1)
        - DeepSeek (https://api.deepseek.com/v1)
        - 以及其他兼容OpenAI格式的API
        """
        import aiohttp
        
        base_url = self.llm_config.base_url.rstrip('/')
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.llm_config.model,
            "messages": messages,
            "temperature": self.llm_config.temperature,
            "max_tokens": self.llm_config.max_tokens
        }
        
        headers = {
            "Authorization": f"Bearer {self.llm_config.api_key}",
            "Content-Type": "application/json"
        }
        
        # 特殊处理Anthropic API
        if "anthropic" in base_url:
            headers = {
                "x-api-key": self.llm_config.api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01"
            }
            payload = {
                "model": self.llm_config.model,
                "max_tokens": self.llm_config.max_tokens,
                "temperature": self.llm_config.temperature,
                "messages": [{"role": "user", "content": prompt}]
            }
            if system_prompt:
                payload["system"] = system_prompt
        
        try:
            async with aiohttp.ClientSession() as session:
                # 确定API端点
                if "anthropic" in base_url:
                    endpoint = f"{base_url}/messages"
                else:
                    endpoint = f"{base_url}/chat/completions"
                
                async with session.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.llm_config.timeout)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"[LLMClient] API错误: {response.status} - {error_text}")
                        return False, f"API错误: {response.status} - {error_text}"
                    
                    data = await response.json()
                    
                    # 解析响应（处理不同格式）
                    if "choices" in data:
                        # OpenAI格式
                        content = data["choices"][0]["message"]["content"]
                    elif "content" in data:
                        # Anthropic格式
                        content = data["content"][0]["text"]
                    else:
                        return False, f"无法解析API响应: {data}"
                    
                    return True, content
                    
        except asyncio.TimeoutError:
            logger.error("[LLMClient] 请求超时")
            return False, "请求超时"
        except Exception as e:
            logger.error(f"[LLMClient] 请求异常: {e}")
            return False, f"请求异常: {str(e)}"
    
    async def analyze_code(self, file_path: str, code: str, task_description: str) -> Tuple[bool, str]:
        """
        分析代码并生成修改建议
        
        Args:
            file_path: 文件路径
            code: 代码内容
            task_description: 任务描述
        
        Returns:
            (是否成功, 修改后的代码)
        """
        system_prompt = """你是一个专业的Python代码优化专家。你的任务是分析用户提供的代码，并根据要求生成优化后的版本。

要求:
1. 保持代码的功能不变
2. 优化代码结构和可读性
3. 添加必要的注释
4. 修复潜在的bug
5. 遵循PEP8规范

请直接返回完整的优化后代码，不要包含任何解释。"""

        prompt = f"""请优化以下代码文件：

文件路径: {file_path}

任务描述: {task_description}

当前代码:
```python
{code}
```

请生成优化后的完整代码。"""

        return await self.generate_code(prompt, system_prompt)
    
    async def generate_diff_description(self, original: str, modified: str) -> str:
        """生成修改描述"""
        system_prompt = "你是一个代码审查助手。请简要描述代码的修改内容。"
        
        prompt = f"""请简要描述以下代码修改：

原代码:
```python
{original[:1000]}
```

修改后:
```python
{modified[:1000]}
```

请用1-2句话描述主要修改内容。"""

        success, description = await self.generate_code(prompt, system_prompt)
        if success:
            return description.strip()
        return "代码优化"


# 全局客户端实例
_llm_client: Optional[SelfIterativeLLMClient] = None


def get_llm_client(plugin_config: Dict[str, Any]) -> Optional[SelfIterativeLLMClient]:
    """获取LLM客户端实例（单例）"""
    global _llm_client
    if _llm_client is None:
        try:
            _llm_client = SelfIterativeLLMClient(plugin_config)
        except Exception as e:
            logger.error(f"[LLMClient] 初始化失败: {e}")
            return None
    return _llm_client


def reset_llm_client():
    """重置LLM客户端实例"""
    global _llm_client
    _llm_client = None
