# 配置说明

pyclaw 通过一个 JSON5 配置文件管理所有设置。本文档介绍配置文件路径、格式、常见任务和热重载机制。

---

## 配置文件

配置文件位于 `~/.pyclaw/pyclaw.json`，使用 **JSON5** 格式（支持注释和尾逗号）。

如果文件不存在，pyclaw 使用安全的默认值运行。通常需要配置的场景：

- 连接消息通道（Telegram、Discord 等）
- 设置 LLM 模型与 Provider
- 配置 MCP 工具服务器
- 调整会话、安全与自动化策略

> 不确定从哪开始？运行 `pyclaw setup --wizard` 进入交互式设置向导。

## 最小示例

```json5
// ~/.pyclaw/pyclaw.json
{
  // 模型提供商
  models: {
    providers: {
      anthropic: { apiKey: "sk-ant-..." },
    },
  },
  // Agent 默认设置
  agents: {
    defaults: {
      model: "claude-sonnet-4-20250514",
      provider: "anthropic",
    },
  },
}
```

## 编辑配置

有四种方式：

```bash
# 1. 交互式向导
pyclaw setup --wizard

# 2. CLI 单项读写
pyclaw config get agents.defaults.model
pyclaw config set agents.defaults.model "gpt-4o"

# 3. 直接编辑文件
vim ~/.pyclaw/pyclaw.json

# 4. Gateway RPC（程序化更新）
# 通过 WebSocket 调用 config.get / config.set / config.patch
```

## 常见任务

### 配置通道

每个通道在 `channels` 下有独立的配置节：

```json5
{
  channels: {
    telegram: {
      enabled: true,
      token: "123456:ABC-DEF",
      allowFrom: ["your_user_id"],
    },
    discord: {
      enabled: true,
      token: "your-bot-token",
      allowFrom: ["your_discord_id"],
    },
    dingtalk: {
      enabled: true,
      clientId: "your_app_key",
      clientSecret: "your_app_secret",
    },
  },
}
```

通道通用的 DM 策略字段：

| 字段 | 可选值 | 说明 |
|------|--------|------|
| `dmPolicy` | `pairing` / `allowlist` / `open` / `disabled` | DM 访问策略 |
| `allowFrom` | 字符串数组 | 允许的发送者 ID |
| `groupPolicy` | `mention` / `open` / `disabled` | 群组消息策略 |

### 设置模型与 Provider

```json5
{
  models: {
    providers: {
      openai: { apiKey: "sk-..." },
      anthropic: { apiKey: "sk-ant-..." },
      ollama: {}, // 本地运行，无需 API Key
    },
  },
  agents: {
    defaults: {
      model: "claude-sonnet-4-20250514",
      provider: "anthropic",
    },
  },
}
```

支持的 Provider 及其默认 base URL：

| Provider | 默认 Base URL |
|----------|---------------|
| `openai` | OpenAI 官方 |
| `anthropic` | Anthropic 官方 |
| `ollama` | `http://localhost:11434/v1` |
| `deepseek` | `https://api.deepseek.com/v1` |
| `qwen` | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `moonshot` | `https://api.moonshot.cn/v1` |
| `groq` | `https://api.groq.com/openai/v1` |
| `openrouter` | `https://openrouter.ai/api/v1` |

自定义 Provider 只需设置 `baseUrl` 和 `apiKey`：

```json5
{
  models: {
    providers: {
      "my-provider": {
        baseUrl: "https://api.example.com/v1",
        apiKey: "your-key",
      },
    },
  },
}
```

### 会话管理

```json5
{
  session: {
    dmScope: "per-channel-peer", // per-sender | per-channel-peer | global
    reset: {
      mode: "daily",
      atHour: 4,
      idleMinutes: 120,
    },
  },
}
```

### MCP 工具服务器

配置格式兼容 Claude Desktop 和 Cursor：

```json5
{
  tools: {
    mcpServers: {
      // stdio 模式 — 本地进程
      filesystem: {
        command: "npx",
        args: ["-y", "@modelcontextprotocol/server-filesystem", "/path"],
      },
      // HTTP 模式 — 远程端点
      "remote-api": {
        url: "https://example.com/mcp/",
        headers: { Authorization: "Bearer xxx" },
      },
    },
  },
}
```

MCP 工具启动时自动发现，可通过 `pyclaw mcp status` 检查。

### 定时任务

支持三种调度类型：`cron`（标准 cron 表达式）、`every`（固定间隔）和 `once`（一次性执行）。

```json5
{
  cron: {
    enabled: true,
    jobs: [
      {
        id: "morning-report",
        scheduleType: "cron",
        schedule: "0 8 * * *",
        message: "生成今日工作摘要",
        agentId: "main",
        channel: "telegram",       // 可选：执行结果发送到指定通道
        deliver: true,             // 是否发送通知
      },
      {
        id: "health-check",
        scheduleType: "every",
        everySeconds: 3600,        // 每小时执行
        message: "检查系统健康状态",
      },
      {
        id: "one-time-task",
        scheduleType: "once",
        at: "2026-03-15T10:00:00", // 指定执行时间
        message: "发送季度报告",
      },
    ],
  },
}
```

定时任务的执行历史可通过 `cron.history` RPC 或 UI 的 Cron 管理页面查看。

### 数据备份

```json5
{
  backup: {
    // 备份通过 CLI 或 Gateway RPC 触发
    // pyclaw backup export --output ~/backup.zip
    // pyclaw backup import ~/backup.zip
  },
}
```

备份内容包括：配置文件、会话记录、每日摘要和记忆数据库。

### 安全设置

```json5
{
  tools: {
    exec: {
      enabled: true,
      allowlist: ["git", "npm", "python"],
      denylist: ["rm -rf /"],
      timeoutMs: 30000,
    },
    restrictToWorkspace: true,
  },
}
```

## 环境变量

pyclaw 按以下优先级读取环境变量：

1. 进程环境变量
2. 工作目录下的 `.env` 文件
3. `~/.pyclaw/.env`（全局回退）

### 核心变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OPENAI_API_KEY` | OpenAI API Key | — |
| `ANTHROPIC_API_KEY` | Anthropic API Key | — |
| `GOOGLE_API_KEY` | Google AI API Key | — |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | — |
| `PYCLAW_AUTH_TOKEN` | Gateway 认证 Token | — |
| `PYCLAW_GATEWAY_PORT` | Gateway 端口 | `18789` |
| `PYCLAW_STATE_DIR` | 状态目录 | `~/.pyclaw` |
| `PYCLAW_CONFIG_PATH` | 配置文件路径 | `~/.pyclaw/pyclaw.json` |

### 配置中引用环境变量

在配置值中使用 `${VAR_NAME}` 引用环境变量：

```json5
{
  models: {
    providers: {
      openai: { apiKey: "${OPENAI_API_KEY}" },
    },
  },
}
```

## 配置热重载

Gateway 会监控配置文件变化并自动应用更新。大部分设置无需重启即可生效。

### 无需重启的设置

| 分类 | 涉及字段 |
|------|----------|
| 通道 | `channels.*` |
| Agent 与模型 | `agents.*`、`models.*` |
| 自动化 | `hooks.*`、`cron.*` |
| 会话 | `session.*` |
| 工具 | `tools.*` |
| 技能 | `skills.*` |
| 插件 | `plugins.*` |

### 需要重启的设置

| 分类 | 涉及字段 |
|------|----------|
| Gateway 网络 | `gateway.port`、`gateway.bind`、`gateway.tls` |
| Gateway 模式 | `gateway.mode` |

## 状态目录结构

```
~/.pyclaw/
├── pyclaw.json          # 主配置（JSON5）
├── auth-profiles.json   # API Key 与 OAuth 凭证
├── credentials/         # Web Provider 凭证文件
├── sessions/            # Agent 会话记录（JSONL）
├── memory/              # 记忆存储（SQLite + LanceDB）
├── summaries/           # 每日摘要（Markdown）
├── cron/                # 定时任务配置与执行日志
├── plans/               # 任务计划存储
├── backups/             # 数据备份存档
└── workspace/           # 工作区文件（AGENTS.md 等模板）
```

## 配置校验与诊断

配置错误时 Gateway 会拒绝启动。使用以下命令排查：

```bash
# 运行诊断
pyclaw doctor

# 查看当前配置
pyclaw config list

# 检查单个字段
pyclaw config get gateway.port
```

## 顶层配置节一览

| 配置节 | 用途 |
|--------|------|
| `models` | LLM Provider 与模型定义 |
| `agents` | Agent 默认设置（模型、Provider、身份、沙箱） |
| `bindings` | 多 Agent 路由绑定规则 |
| `channels` | 消息通道（Telegram、Discord 等） |
| `session` | 会话管理（范围、重置、发送策略） |
| `tools` | 工具配置（exec、MCP、浏览器、记忆搜索） |
| `gateway` | Gateway 网络设置（端口、绑定、认证） |
| `cron` | 定时任务 |
| `hooks` | Webhook 钩子 |
| `memory` | 记忆系统 |
| `logging` | 日志级别与输出 |
| `skills` | 技能加载与过滤 |
| `plugins` | 插件加载 |
| `ui` | UI 外观设置（主题色、语言、Gateway 地址） |
| `backup` | 数据备份与恢复 |
| `auth` | 密码与 Token 认证 |
| `update` | 更新渠道与自动更新 |
| `messages` | 消息格式（Markdown、流式） |
| `browser` | 浏览器自动化 |

---

*相关文档: [快速开始](quickstart.md) · [架构设计](architecture.md) · [API 参考](api-reference.md)*
