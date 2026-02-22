# MaiBot 自我迭代插件 v2.1

一个让 MaiBot 能够自我迭代、自我优化的框架插件。支持代码读取、修改、校验、差异对比和部署，包含完整的安全审核机制。

**v2.1 新特性**: 支持独立的自我迭代LLM模型（Claude、Gemini、Kimi、DeepSeek等）！

## 功能特性

### 核心功能

- **代码读取工具** (`read_file`) - 安全读取白名单内的源代码
- **代码写入工具** (`write_file`) - 将修改写入影子工作区
- **终端执行工具** (`execute_terminal`) - 执行安全的系统命令
- **自我迭代工具** (`self_iterate`) - 一键完成完整的迭代流程

### 安全特性

- **目录白名单** - 严格控制可读取/修改的路径
- **文件黑名单** - 禁止访问敏感文件(.env, token, password等)
- **AST语法校验** - 自动检查代码语法错误
- **人工审核机制** - 管理员确认后才应用修改
- **自动备份系统** - 修改前自动备份原文件
- **一键回滚功能** - 支持快速回滚到历史版本

### LLM工具注入（核心特性）

这是本插件的核心特性！插件会在 LLM 调用前（PRE_LLM事件），将自我迭代工具的信息注入到 Prompt 中，让 AI 知道自己有自我修改代码的能力。

### 独立LLM模型支持（v2.1新特性）

插件支持配置独立的LLM模型用于代码生成，不依赖MaiBot框架本身的模型：

- **Claude** (Anthropic) - 代码能力最强，推荐！
- **Gemini** (Google) - 速度快，免费额度高
- **Kimi** (Moonshot) - 中文支持好，长文本能力强
- **DeepSeek** - 专为代码优化设计
- **OpenAI GPT** - 通用能力强

如果不配置，默认使用MaiBot框架本身的模型。

## 安装方法

### 1. 克隆仓库

```bash
cd MaiBot/plugins
git clone https://github.com/waleisha/Maibot-plugin-self-iterative.git maibot_plugin_self_iterative
```

### 2. 安装依赖

```bash
cd maibot_plugin_self_iterative
pip install aiohttp

# 如果使用Google Gemini，还需要:
pip install google-generativeai
```

### 3. 配置插件

编辑 `config.toml` 文件：

```toml
[security]
admin_qqs = [你的QQ号]

[llm]
# 选择LLM提供商
provider = "anthropic"  # 可选: default, openai, anthropic, google, moonshot, deepseek

[llm.anthropic]
model = "claude-3-5-sonnet-20241022"
api_key = "your-api-key-here"
```

### 4. 重启MaiBot

```bash
python bot.py
```

## 使用方法

### 命令列表

| 命令 | 说明 | 示例 |
|------|------|------|
| `/iterate` | 启动自我迭代流程 | `/iterate 优化日志输出` |
| `/approve` | 审核通过并应用修改 | `/approve` |
| `/reject` | 打回修改 | `/reject` |
| `/diff` | 查看代码差异 | `/diff src/plugins/plugin.py` |
| `/status` | 查看当前迭代状态 | `/status` |
| `/rollback` | 回滚到指定版本 | `/rollback 20240115_143022` |
| `/backups` | 查看备份列表 | `/backups` |

### 使用示例

#### 1. 让AI优化自己的代码

用户：
```
麦麦，优化一下你的 message_router.py，让日志输出更清晰
```

AI会：
1. 调用 `read_file` 读取 `src/plugins/message_router.py`
2. 使用配置的LLM模型分析代码并生成优化版本
3. 调用 `self_iterate` 提交修改
4. 通知用户修改已提交，等待审核

#### 2. 修复Bug

用户：
```
麦麦，修复一下 src/utils/helper.py 第50行的那个bug
```

AI会：
1. 调用 `read_file` 读取相关代码
2. 使用独立LLM模型分析问题并生成修复版本
3. 调用 `write_file` 写入影子工作区
4. 通知用户修改已提交

#### 3. 手动触发迭代

用户：
```
/iterate 添加一个新的消息处理功能
```

这会启动迭代流程，AI会开始分析和修改代码。

### 审核流程

当AI提交修改后，会进入等待审核状态：

1. **查看差异**: `/diff` - 查看修改前后的代码差异
2. **审核通过**: `/approve` - 应用修改到原文件
3. **打回修改**: `/reject` - 拒绝并清理影子文件

## 项目结构

```
maibot_plugin_self_iterative/
├── plugin.py              # 主插件类
├── config.toml            # 配置文件
├── _manifest.json         # 插件清单
├── README.md              # 说明文档
├── INSTALL.md             # 安装指南
├── EXAMPLES.md            # 使用示例
├── QUICKREF.md            # 快速参考
│
├── tools/                 # 工具组件
│   ├── __init__.py
│   ├── reader.py          # 源码读取器
│   ├── writer.py          # 源码写入器
│   ├── terminal.py        # 虚拟终端
│   └── iterator.py        # 自我迭代工具
│
├── core/                  # 核心模块
│   ├── __init__.py
│   ├── state.py           # 迭代状态管理
│   ├── verifier.py        # 语法验证器
│   ├── differ.py          # 差异生成器
│   ├── patcher.py         # 部署器
│   ├── workspace.py       # 工作区管理器
│   └── llm_client.py      # 独立LLM客户端（v2.1新特性）
│
└── handlers/              # 处理器
    ├── __init__.py
    ├── inject_handler.py  # LLM注入处理器（PRE_LLM事件）
    └── command_handler.py # 命令处理器
```

## 配置说明

### LLM模型配置 `[llm]`

```toml
[llm]
# LLM提供商选择
provider = "anthropic"  # 可选: default, openai, anthropic, google, moonshot, deepseek

# 温度参数（0-1，越低越保守）
temperature = 0.3

# 最大token数
max_tokens = 4096
```

#### Claude (Anthropic) 配置

```toml
[llm.anthropic]
model = "claude-3-5-sonnet-20241022"
api_key = "sk-ant-..."
base_url = "https://api.anthropic.com/v1"
```

**推荐！** Claude 3.5 Sonnet 是目前代码能力最强的模型。

#### Gemini (Google) 配置

```toml
[llm.google]
model = "gemini-2.0-flash-exp"
api_key = "..."
```

**优点**: 速度快，免费额度高。

#### Kimi (Moonshot) 配置

```toml
[llm.moonshot]
model = "kimi-latest"
api_key = "..."
base_url = "https://api.moonshot.cn/v1"
```

**优点**: 中文支持好，长文本能力强。

#### DeepSeek 配置

```toml
[llm.deepseek]
model = "deepseek-coder"
api_key = "..."
base_url = "https://api.deepseek.com/v1"
```

**优点**: 专为代码优化设计，价格便宜。

### 安全设置 `[security]`

```toml
[security]
# 管理员QQ号
admin_qqs = [123456789]

# 允许读取的路径（相对于MaiBot根目录）
allowed_read_paths = ["src", "plugins", "maibot_plugin_self_iterative"]

# 允许修改的路径（相对于MaiBot根目录）
allowed_write_paths = ["src", "plugins", "maibot_plugin_self_iterative"]

# 禁止访问的文件模式
forbidden_patterns = [".*\\.env.*", ".*token.*", ".*password.*"]
```

### 迭代设置 `[iteration]`

```toml
[iteration]
# 影子工作区路径
shadow_workspace_path = "storage/.shadow"

# 备份路径
backup_path = "storage/.backups"

# 最大备份数量
max_backups = 50

# 启用语法检查
enable_syntax_check = true

# 启用差异报告
enable_diff_report = true
```

## 工作原理

### 1. LLM工具注入（PRE_LLM事件）

插件注册了一个 `SelfIterativeInjectHandler` 事件处理器，使用 `EventType.PRE_LLM` 在 LLM 调用**前**将工具信息注入到 Prompt 中：

```python
class SelfIterativeInjectHandler(BaseEventHandler):
    event_type = EventType.PRE_LLM  # 关键：在LLM调用前注入
    weight = 100  # 高权重，确保优先执行
    
    async def execute(self, message):
        inject_content = """
        【系统能力通知 - 自我迭代工具】
        
        你拥有自我迭代和自我优化的能力！
        可用工具: read_file, write_file, execute_terminal, self_iterate
        ...
        """
        message.modify_llm_prompt(new_prompt)
```

### 2. 独立LLM模型调用

如果配置了独立模型，插件会使用 `SelfIterativeLLMClient` 调用外部API：

```python
# 使用 Claude 分析代码
client = SelfIterativeLLMClient(config)
success, new_code = await client.analyze_code(
    file_path="src/plugins/example.py",
    code=original_code,
    task_description="优化日志输出"
)
```

### 3. 迭代流程

```
用户请求修改
    ↓
AI调用 read_file 读取代码
    ↓
使用独立LLM模型分析并生成修改
    ↓
AI调用 self_iterate 提交修改
    ↓
生成Diff报告，进入等待审核状态
    ↓
管理员查看差异 (/diff)
    ↓
管理员审核通过 (/approve) 或打回 (/reject)
    ↓
如果通过：备份原文件 → 应用修改 → 清理影子文件
```

## 注意事项

1. **安全第一**: 请确保只将可信用户添加到管理员列表
2. **API Key安全**: 不要将API Key提交到Git仓库，建议使用环境变量
3. **备份重要**: 修改前会自动备份，但建议定期手动备份重要文件
4. **语法检查**: 插件会自动检查Python代码语法，但仍需人工审核逻辑正确性
5. **重启生效**: 部分修改可能需要重启MaiBot才能完全生效

## 更新日志

### v2.1.0 (2025-02-22)

- 修复LLM注入问题（改为PRE_LLM事件）
- 修复命令拦截问题
- 添加独立LLM模型支持（Claude、Gemini、Kimi、DeepSeek）
- 优化代码结构

### v2.0.0 (2025-02-21)

- 重构为标准的MaiBot插件结构
- 添加LLM工具注入功能
- 添加 `self_iterate` 一键迭代工具
- 支持修改MaiBot核心代码（src目录）
- 支持修改插件代码（plugins目录）

### v1.0.0

- 初始版本
- 基本的代码读取、写入功能
- 终端执行工具
- 差异生成和审核流程

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！

## 联系方式

- GitHub: https://github.com/waleisha/Maibot-plugin-self-iterative
- MaiBot官方: https://github.com/Mai-with-u/MaiBot
