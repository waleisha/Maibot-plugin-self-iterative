# 安装指南

## 快速安装

### 方法1: 直接克隆（推荐）

```bash
# 进入MaiBot的plugins目录
cd MaiBot/plugins

# 克隆插件仓库
git clone https://github.com/waleisha/Maibot-plugin-self-iterative.git maibot_plugin_self_iterative

# 重启MaiBot
cd ..
python bot.py
```

### 方法2: 手动下载

1. 下载插件压缩包
2. 解压到 `MaiBot/plugins/maibot_plugin_self_iterative/` 目录
3. 重启MaiBot

## 配置步骤

### 1. 设置管理员QQ号

编辑 `plugins/maibot_plugin_self_iterative/config.toml`：

```toml
[security]
admin_qqs = [123456789]  # 替换为你的QQ号
```

### 2. 配置允许修改的路径（可选）

默认配置允许修改 `src` 和 `plugins` 目录：

```toml
[security]
allowed_read_paths = ["src", "plugins", "maibot_plugin_self_iterative"]
allowed_write_paths = ["src", "plugins", "maibot_plugin_self_iterative"]
```

如果你想限制AI只能修改插件代码，可以改为：

```toml
allowed_write_paths = ["plugins"]
```

### 3. 配置禁止访问的文件（可选）

默认会禁止访问包含敏感信息的文件：

```toml
[security]
forbidden_patterns = [
    ".*\\.env.*",
    ".*token.*",
    ".*password.*",
    ".*secret.*",
    ".*credential.*",
    ".*api_key.*",
    ".*private.*"
]
```

## 验证安装

1. 启动MaiBot
2. 在控制台查看日志，确认插件已加载：
   ```
   [SelfIterativePlugin] 自我迭代框架插件已加载
   ```

3. 在聊天中发送命令测试：
   ```
   /status
   ```

如果看到状态信息，说明安装成功！

## 常见问题

### Q: 插件加载失败？

A: 检查以下几点：
1. 插件目录名称必须是 `maibot_plugin_self_iterative`
2. 确保 `_manifest.json` 文件存在
3. 查看控制台错误日志

### Q: 命令没有响应？

A: 检查以下几点：
1. 确认你的QQ号在 `admin_qqs` 列表中
2. 确认插件已启用 (`plugin.enabled = true`)
3. 查看日志确认命令是否被拦截

### Q: AI不知道有工具？

A: 检查以下几点：
1. 确认 `features.enable_tool_inject = true`
2. 确认 `SelfIterativeInjectHandler` 已注册（查看启动日志）
3. 某些模型可能不支持工具调用

### Q: 修改没有生效？

A: 检查以下几点：
1. 确认已执行 `/approve` 审核通过
2. 确认修改的文件路径正确
3. 部分修改可能需要重启MaiBot

## 卸载

```bash
# 删除插件目录
rm -rf MaiBot/plugins/maibot_plugin_self_iterative

# 重启MaiBot
```

## 获取帮助

- GitHub Issues: https://github.com/waleisha/Maibot-plugin-self-iterative/issues
- MaiBot官方文档: https://docs.mai-mai.org/
