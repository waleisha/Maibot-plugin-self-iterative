# MaiBot 自我迭代插件 v2.2 修复说明

## 主要修复内容

### 1. 修复 `'MessageRecv' object has no attribute 'user_id'` 错误

**问题原因**: MaiBot 的消息对象结构在不同版本中可能不同，直接使用 `self.message.user_id` 在某些版本中会报错。

**修复方案**: 在 `handlers/command_handler.py` 中添加了 `get_user_id_from_message()` 函数，支持多种方式获取用户ID：
- 方式1: 直接获取 `message.user_id` (旧版本)
- 方式2: 通过 `message.message_info.user_info.user_id` (新版本)
- 方式3: 通过 `message.message_base_info['user_id']` (某些版本)
- 方式4: 通过 `message.sender.user_id`

### 2. 简化 LLM 配置

**原问题**: LLM配置分散在多个配置节中（`llm.openai`, `llm.anthropic`, `llm.google`等），配置复杂。

**修复方案**: 简化为统一的配置块：

```toml
[llm]
enabled = false              # 是否启用独立LLM
base_url = "https://api.openai.com/v1"  # API基础URL
api_key = ""                 # API密钥
model = "gpt-4o"            # 模型名称
temperature = 0.3
max_tokens = 4096
```

**支持的模型**: 所有OpenAI兼容格式的API
- OpenAI (gpt-4o, gpt-4o-mini, gpt-3.5-turbo)
- Claude (通过OpenAI兼容接口)
- Gemini (通过OpenAI兼容接口)
- Moonshot (kimi-latest)
- DeepSeek (deepseek-coder)
- 其他OpenAI兼容的API

### 3. 添加强命令和弱命令支持

**强命令**: 使用 `/iterate` 等斜杠命令触发迭代流程

**弱命令**: 通过自然语言触发迭代流程
- "麦麦帮我优化代码"
- "帮我改一下XX文件"
- "重构一下message_router"
- "修复bug"
- "优化日志输出"

**配置**: 在 `config.toml` 中设置 `features.enable_weak_command = true` 启用弱命令

### 4. 修复 LLM 客户端

- 支持统一的OpenAI兼容格式
- 自动从环境变量读取API Key
- 更好的错误处理和降级机制

## 文件变更

### 新增文件
- `handlers/weak_command_handler.py` - 弱命令处理器

### 修改文件
- `plugin.py` - 简化LLM配置，添加弱命令支持
- `handlers/command_handler.py` - 修复user_id获取
- `handlers/__init__.py` - 导出WeakIterateHandler
- `core/llm_client.py` - 支持统一配置格式
- `config.toml` - 简化的配置模板

## 升级指南

1. 备份原配置文件
2. 替换插件文件
3. 更新 `config.toml`（参考新的配置模板）
4. 重启 MaiBot

## 配置示例

### 使用框架默认LLM（推荐）
```toml
[llm]
enabled = false
```

### 使用OpenAI
```toml
[llm]
enabled = true
base_url = "https://api.openai.com/v1"
api_key = "sk-..."
model = "gpt-4o"
```

### 使用Moonshot (Kimi)
```toml
[llm]
enabled = true
base_url = "https://api.moonshot.cn/v1"
api_key = "sk-..."
model = "kimi-latest"
```

### 使用DeepSeek
```toml
[llm]
enabled = true
base_url = "https://api.deepseek.com/v1"
api_key = "sk-..."
model = "deepseek-coder"
```

### 使用Claude (通过OpenAI兼容接口)
```toml
[llm]
enabled = true
base_url = "https://api.anthropic.com/v1"
api_key = "sk-ant-..."
model = "claude-3-5-sonnet-20241022"
```

## 注意事项

1. API Key 优先级: 配置文件 > 环境变量
2. 如果独立LLM配置错误，会自动降级到框架默认LLM
3. 弱命令可能与其他插件的命令冲突，可根据需要禁用
