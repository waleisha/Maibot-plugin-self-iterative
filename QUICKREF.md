# 快速参考

## 命令速查表

| 命令 | 功能 | 权限 |
|------|------|------|
| `/iterate [描述]` | 启动自我迭代流程 | 管理员 |
| `/approve` | 审核通过并应用修改 | 管理员 |
| `/reject` | 打回修改 | 管理员 |
| `/diff [文件]` | 查看代码差异 | 管理员 |
| `/status` | 查看迭代状态 | 管理员 |
| `/rollback [时间戳]` | 回滚到指定版本 | 管理员 |
| `/backups` | 查看备份列表 | 管理员 |

## 自然语言触发

直接对AI说：

```
"优化一下你的XX功能"
"修复XX文件的bug"
"添加XX功能"
"重构XX模块"
"查看一下XX文件的代码"
```

## 工具列表

| 工具 | 功能 |
|------|------|
| `read_file` | 读取源代码文件 |
| `write_file` | 写入代码到影子工作区 |
| `execute_terminal` | 执行安全的系统命令 |
| `self_iterate` | 一键完成完整迭代流程 |

## 配置关键项

```toml
[security]
admin_qqs = [123456789]  # 管理员QQ号

[features]
enable_tool_inject = true  # 启用LLM工具注入（核心功能）
```

## 目录结构

```
maibot_plugin_self_iterative/
├── plugin.py          # 主插件
├── config.toml        # 配置文件
├── _manifest.json     # 插件清单
├── tools/             # 工具组件
├── core/              # 核心模块
└── handlers/          # 处理器
```

## 工作流程

```
用户请求 → AI读取代码 → AI生成修改 → 提交影子区 → 生成Diff → 等待审核 → 应用/打回
```

## 安全机制

- 白名单控制读取/修改路径
- 黑名单过滤敏感文件
- AST语法检查
- 人工审核
- 自动备份
- 一键回滚
