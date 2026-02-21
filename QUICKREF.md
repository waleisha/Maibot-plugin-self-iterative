# MaiBot自我迭代框架 - 快速参考

## 命令速查表

| 命令 | 功能 | 示例 |
|------|------|------|
| `/iterate [目标]` | 发起迭代 | `/iterate 优化日志输出` |
| `/approve` | 审核通过 | `/approve` |
| `/reject` | 打回修改 | `/reject` |
| `/diff` | 查看差异 | `/diff` |
| `/status` | 查看状态 | `/status` |
| `/rollback [时间戳]` | 回滚版本 | `/rollback 20240115_143022` |

## 迭代流程

```
1. 发起迭代 ──▶ 2. LLM分析 ──▶ 3. 读取源码
                                      │
                                      ▼
6. 应用修改 ◀── 5. 人工审核 ◀── 4. 写入影子区
```

## 安全机制

```
┌─────────────────────────────────────────┐
│  1. 目录白名单 - 控制可访问路径          │
│  2. 文件黑名单 - 禁止访问敏感文件        │
│  3. 命令白名单 - 只允许安全命令          │
│  4. 影子工作区 - 隔离危险操作            │
│  5. 人工审核 - 管理员确认后才应用        │
│  6. 自动备份 - 修改前自动备份原文件      │
└─────────────────────────────────────────┘
```

## 配置文件关键项

```toml
[security]
admin_qqs = [123456789]           # 管理员QQ号
allowed_read_paths = ["plugins"]   # 可读路径
allowed_write_paths = ["plugins"]  # 可写路径

[iteration]
max_backups = 50                   # 最大备份数
enable_syntax_check = true         # 启用语法检查
approval_timeout = 300             # 审核超时(秒)
```

## 常见问题速查

| 问题 | 解决方案 |
|------|----------|
| 命令无响应 | 检查插件是否启用，查看日志 |
| 无法读取文件 | 检查 `allowed_read_paths` 配置 |
| 审核命令无效 | 确认QQ号在 `admin_qqs` 中 |
| 语法检查失败 | 检查代码缩进和括号匹配 |
| 修改后出错 | 使用 `/rollback` 回滚 |

## 自然语言指令示例

```
麦麦，帮我优化一下 hello_world_plugin 的日志输出
麦麦，给 my_plugin 添加一个新命令 /test
麦麦，修复一下 message_handler.py 的空指针问题
麦麦，读取一下 plugins/my_plugin/plugin.py
麦麦，执行 pip list 查看已安装的包
```

## 文件结构

```
maibot_plugin_self_iterative/
├── plugin.py          # 主入口
├── config.toml        # 配置文件
├── _manifest.json     # 插件清单
├── core/              # 核心模块
│   ├── workspace.py   # 影子工作区
│   ├── verifier.py    # 语法校验
│   ├── differ.py      # 差异生成
│   └── patcher.py     # 部署器
└── storage/           # 存储
    ├── .shadow/       # 影子工作区
    └── .backups/      # 备份
```

## 工具说明

| 工具 | 用途 | 参数 |
|------|------|------|
| `read_file` | 读取源码 | `file_path`, `offset`, `limit` |
| `write_file` | 写入影子区 | `target_path`, `content` |
| `execute_terminal` | 执行命令 | `command`, `timeout` |

## 状态说明

| 状态 | 含义 |
|------|------|
| `idle` | 空闲，等待指令 |
| `pending` | 有待审核的修改 |
| `approved` | 修改已应用 |
| `rejected` | 修改已打回 |
| `error` | 发生错误 |

## 快速开始

1. **安装插件** → 复制到 `plugins/` 目录
2. **配置管理员** → 编辑 `config.toml`
3. **重启MaiBot** → 加载插件
4. **测试命令** → 发送 `/status`
5. **开始迭代** → 发送 `/iterate 优化xxx`

---

**更多帮助**: 查看 README.md 和 EXAMPLES.md
