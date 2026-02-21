# MaiBot自我迭代框架插件 - 安装指南

## 系统要求

- MaiBot >= 0.8.0
- Python >= 3.9
- 操作系统: Windows / Linux / macOS

## 安装步骤

### 方法一：直接复制（推荐）

1. **下载插件**
   ```bash
   # 克隆或下载插件代码
   git clone https://github.com/your-repo/maibot_plugin_self_iterative.git
   ```

2. **复制到插件目录**
   ```bash
   # Linux/macOS
   cp -r maibot_plugin_self_iterative /path/to/MaiBot/plugins/
   
   # Windows (PowerShell)
   Copy-Item -Recurse maibot_plugin_self_iterative C:\path\to\MaiBot\plugins\
   ```

3. **配置插件**
   ```bash
   # 编辑配置文件
   nano /path/to/MaiBot/plugins/maibot_plugin_self_iterative/config.toml
   ```

4. **设置管理员QQ号**
   ```toml
   [security]
   admin_qqs = [123456789]  # 替换为你的QQ号
   ```

5. **重启MaiBot**
   ```bash
   # 如果使用systemd
   sudo systemctl restart maibot
   
   # 或者直接运行
   python bot.py
   ```

### 方法二：使用MaiBot插件管理器

如果你的MaiBot版本支持插件管理器：

```bash
# 进入MaiBot目录
cd /path/to/MaiBot

# 使用插件管理器安装
python -m maibot plugin install maibot_plugin_self_iterative
```

## 配置详解

### 1. 安全设置 (config.toml)

```toml
[security]
# 超级管理员QQ号列表 - 只有这些用户可以审核修改
admin_qqs = [123456789, 987654321]

# 允许读取的目录白名单
# 注意：路径可以是绝对路径或相对于MaiBot根目录的路径
allowed_read_paths = [
    "src/plugins",
    "src/common", 
    "src/config",
    "plugins",
]

# 允许修改的目录白名单（更加严格的限制）
allowed_write_paths = [
    "plugins",
]

# 禁止访问的文件/目录模式（正则表达式列表）
forbidden_patterns = [
    ".*\\.env.*",        # .env文件
    ".*token.*",         # 包含token的文件
    ".*password.*",      # 包含password的文件
    ".*secret.*",        # 包含secret的文件
    ".*credential.*",    # 凭证文件
    ".*api_key.*",       # API密钥文件
]

# 允许执行的终端命令白名单
allowed_commands = [
    "pip",
    "python",
    "python3",
    "ls",
    "dir",
    "cat",
    "type",
    "echo",
    "git",
    "pytest",
]

# 禁止执行的命令黑名单（优先级高于白名单）
forbidden_commands = [
    "rm -rf /",
    "rm -rf /*",
    "dd",
    "mkfs",
    "format",
]
```

### 2. 迭代设置

```toml
[iteration]
# 影子工作区路径（相对于插件目录）
shadow_workspace_path = "storage/.shadow"

# 备份存储路径
backup_path = "storage/.backups"

# 最大备份数量（超过后自动清理旧备份）
max_backups = 50

# 是否启用自动语法检查
enable_syntax_check = true

# 是否启用差异报告
enable_diff_report = true

# 审核超时时间（秒）
approval_timeout = 300

# 重启前等待时间（秒）
restart_delay = 3
```

### 3. LLM设置

```toml
[llm]
# 用于代码生成的模型名称
model_name = "default"

# 代码生成温度（较低的温度使输出更确定）
temperature = 0.3

# 最大生成token数
max_tokens = 4096
```

## 验证安装

1. **检查插件加载**
   ```
   查看MaiBot启动日志，确认出现以下信息：
   [SelfIterativePlugin] 自我迭代框架插件已加载
   ```

2. **测试命令**
   ```
   /status
   ```
   应该返回当前迭代状态信息。

3. **测试工具调用**
   ```
   麦麦，读取一下 plugins/hello_world_plugin/plugin.py 文件
   ```

## 常见问题

### Q: 插件无法加载
**A:** 检查以下几点：
- MaiBot版本是否 >= 0.8.0
- 插件目录名称是否正确 (`maibot_plugin_self_iterative`)
- `_manifest.json` 文件是否存在且格式正确
- 查看MaiBot日志获取详细错误信息

### Q: 命令无响应
**A:** 
- 确认插件已启用 (`enabled = true`)
- 检查配置文件格式是否正确
- 查看日志是否有错误信息

### Q: 无法读取/写入文件
**A:**
- 检查 `allowed_read_paths` 和 `allowed_write_paths` 配置
- 确认文件路径在白名单内
- 检查文件是否存在且有读取权限

### Q: 审核命令无效
**A:**
- 确认你的QQ号在 `admin_qqs` 列表中
- 检查当前是否有等待审核的迭代请求 (`/status`)
- 确认命令拼写正确

### Q: 语法检查失败但代码看起来没问题
**A:**
- 检查代码缩进（空格 vs Tab）
- 检查括号是否匹配
- 检查特殊字符编码
- 可以在 `config.toml` 中临时禁用语法检查进行测试

## 卸载

1. **删除插件目录**
   ```bash
   rm -rf /path/to/MaiBot/plugins/maibot_plugin_self_iterative
   ```

2. **重启MaiBot**
   ```bash
   python bot.py
   ```

## 更新

1. **备份配置**
   ```bash
   cp /path/to/MaiBot/plugins/maibot_plugin_self_iterative/config.toml ~/config_backup.toml
   ```

2. **删除旧版本**
   ```bash
   rm -rf /path/to/MaiBot/plugins/maibot_plugin_self_iterative
   ```

3. **安装新版本**
   ```bash
   cp -r maibot_plugin_self_iterative /path/to/MaiBot/plugins/
   ```

4. **恢复配置**
   ```bash
   cp ~/config_backup.toml /path/to/MaiBot/plugins/maibot_plugin_self_iterative/config.toml
   ```

5. **重启MaiBot**

## 获取帮助

- 查看日志: `logs/maibot.log`
- 提交Issue: https://github.com/your-repo/issues
- 官方文档: https://docs.mai-mai.org/
