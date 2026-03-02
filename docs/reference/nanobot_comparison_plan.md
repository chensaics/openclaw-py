# OpenClaw-Py vs nanobot 功能对比分析与实施计划

> 日期: 2026-03-01
>
> 对比项目:
> - **当前项目**: openclaw-py v0.1.0 (Phase 0-49 完成, ~375 .py / ~51k LOC)
> - **参考项目**: [HKUDS/nanobot](https://github.com/HKUDS/nanobot) v0.1.4.post3 (~4,000 行核心代码)
>
> 原则: 以 openclaw-py 为基准，选择性借鉴 nanobot 中实用且我们缺失的功能。

---

## 一、项目定位对比

| 维度 | openclaw-py | nanobot |
|------|-------------|---------|
| 定位 | 全功能多通道 AI 网关 + Agent 运行时 | 超轻量个人 AI 助手 |
| 代码规模 | ~51,000 LOC | ~4,000 行核心代码 |
| 架构复杂度 | 高 (Gateway + ACP + Plugin + Hooks) | 低 (精简单体) |
| 通道数 | 23 | 10 |
| 测试 | 1,791 (70 文件) | 未公开 |
| UI | Flet 桌面/移动端 | 纯 CLI |
| 部署 | systemd/launchd/schtasks | Docker + systemd |

两者定位不同: openclaw-py 追求功能完备性，nanobot 追求极致轻量。但 nanobot 在某些实用功能上的设计值得借鉴。

---

## 二、功能对比矩阵

### 2.1 我们已具备但 nanobot 没有的 (优势)

| 功能 | openclaw-py | nanobot | 说明 |
|------|-------------|---------|------|
| ACP (IDE 集成) | ✅ | ❌ | NDJSON stdio 桥接 VS Code 等 IDE |
| Canvas 实时预览 | ✅ | ❌ | WebSocket live-reload + A2UI |
| Browser 自动化 | ✅ | ❌ | Playwright 全套工具 |
| 安全体系 | ✅ 完善 | ✅ 基础 | exec 审批/sandbox/SSRF/审计 vs restrictToWorkspace |
| 插件系统 | ✅ | ❌ | entry points + extensions/ |
| Hooks 事件系统 | ✅ | ❌ | COMMAND/SESSION/AGENT/GATEWAY/MESSAGE |
| Node Host | ✅ | ❌ | 远程节点执行 |
| Flet UI | ✅ | ❌ | 桌面/移动端图形界面 |
| 13 个额外通道 | ✅ | ❌ | Signal/iMessage/IRC/Teams/Twitch/LINE 等 |
| LanceDB 向量搜索 | ✅ | ❌ | 嵌入式向量数据库 |
| Config Includes | ✅ | ❌ | `$include` 配置拆分 |
| 服务发现 | ✅ | ❌ | mDNS/Bonjour + Tailscale |
| 设备配对 | ✅ | ❌ | 安全设备认证 |
| 批量媒体上传 | ✅ | ❌ | 多文件并行上传 |

### 2.2 nanobot 有但我们缺失的 (可借鉴)

| 功能 | nanobot | openclaw-py | 优先级 | 借鉴价值 |
|------|---------|-------------|--------|----------|
| MCP 支持 | ✅ stdio + HTTP | ❌ | **P0** | 极高 — 业界标准协议 |
| Docker 部署 | ✅ Dockerfile + Compose | ❌ | **P0** | 高 — 标准化部署 |
| DingTalk 通道 | ✅ Stream Mode | ❌ | **P1** | 高 — 国内主流 IM |
| QQ 通道 | ✅ botpy SDK | ❌ | **P1** | 高 — 国内最大 IM |
| OAuth CLI 登录 | ✅ `nanobot provider login` | 代码存在但未暴露 | **P1** | 中 — 代码已有，需接线 |
| 技能市场 | ✅ ClawHub 搜索/安装 | 仅本地加载 | **P2** | 中 — 社区生态 |
| Agent 社交网络 | ✅ Moltbook/ClawdChat | ❌ | **P2** | 中 — 前沿概念 |
| Workspace 模板同步 | ✅ 自动同步 | 仅手动复制 | **P2** | 中 — 改善体验 |
| Progress Streaming | ✅ 结构化进度事件 | 通用流式 | **P3** | 低 — 锦上添花 |
| Groq Whisper 语音转录 | ✅ Telegram 语音自动转录 | 语音 UI 未完成 | **P3** | 低 — 场景有限 |

### 2.3 双方都有但实现方式不同的

| 功能 | nanobot 方式 | openclaw-py 方式 | 借鉴点 |
|------|-------------|-----------------|--------|
| Provider 注册 | ProviderSpec + Registry | ProviderRegistry + Builder | nanobot 的 2-step 添加更简洁 |
| Onboarding | `nanobot onboard` 一键 | setup wizard + 非交互 | nanobot 更简洁，可借鉴简化流程 |
| Heartbeat | HEARTBEAT.md 文件驱动 | HeartbeatRunner 程序驱动 | 两者等价，我们更灵活 |
| Cron | CLI add/list/remove | APScheduler + 高级隔离 | 我们更完善 |
| 思维模式 | 实验性 | ThinkingMode 四级 | 我们更完善 |
| 内存系统 | 基础 | SQLite FTS5 + LanceDB + QMD | 我们更完善 |

---

## 三、可借鉴功能详细分析

### 3.1 MCP (Model Context Protocol) 支持 — P0

**nanobot 实现方式:**
```json
{
  "tools": {
    "mcpServers": {
      "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"]
      },
      "my-remote-mcp": {
        "url": "https://example.com/mcp/",
        "headers": { "Authorization": "Bearer xxxxx" }
      }
    }
  }
}
```

**分析:**
- MCP 是 Anthropic 推出的开放协议，正在成为 AI 工具集成的业界标准
- nanobot 支持 stdio (本地进程) 和 HTTP (远程端点) 两种传输模式
- 支持 `toolTimeout` 配置慢服务器超时
- MCP 工具在启动时自动发现和注册，LLM 可与内置工具一起使用
- 配置格式与 Claude Desktop / Cursor 兼容

**openclaw-py 当前状态:**
- `AGENTS.default.md` 提到 mcporter (工具服务器运行时)，但不是 MCP 协议
- 无 MCP 客户端或服务器实现
- `ToolsConfig` (`src/pyclaw/config/schema.py`) 无 `mcpServers` 字段

**实施方案:**
1. 在 `src/pyclaw/config/schema.py` 的 `ToolsConfig` 中添加 `mcp_servers` 字段
2. 新建 `src/pyclaw/mcp/` 模块:
   - `client.py` — MCP 客户端协议实现 (JSON-RPC 2.0)
   - `stdio_transport.py` — 子进程 stdio 传输
   - `http_transport.py` — HTTP/SSE 传输
   - `registry.py` — MCP 工具发现和注册
   - `types.py` — MCP 协议类型定义
3. 在 Agent 工具注册表中集成 MCP 工具
4. 在 Gateway 启动时自动连接和发现 MCP 服务器
5. 添加 `pyclaw mcp status` CLI 命令

**依赖:** `mcp` PyPI 包 (Anthropic 官方 Python SDK)

**预估工作量:** ~800 LOC, 2-3 天

---

### 3.2 Docker 部署支持 — P0

**nanobot 实现方式:**
- `Dockerfile` — 单阶段或多阶段构建
- `docker-compose.yml` — CLI 和 Gateway 两个服务
- `.dockerignore` — 排除无关文件
- 数据持久化: `-v ~/.nanobot:/root/.nanobot`

**openclaw-py 当前状态:**
- 无任何 Docker 相关文件
- 部署依赖 systemd/launchd/schtasks (`src/pyclaw/daemon/`)
- 已有桌面/移动端构建脚本 (`scripts/build-desktop.sh`, `scripts/build-mobile.sh`)

**实施方案:**
1. 创建 `Dockerfile`:
   - 基于 `python:3.12-slim`
   - 多阶段构建 (builder + runtime)
   - 安装系统依赖 (playwright 浏览器可选)
   - `pip install -e .` 或 wheel 安装
   - 默认入口: `pyclaw gateway`
2. 创建 `docker-compose.yml`:
   - `pyclaw-gateway` 服务 (长驻)
   - `pyclaw-cli` 服务 (一次性命令)
   - 挂载 `~/.pyclaw` 卷
   - 端口映射: 18789 (gateway), 18790 (canvas)
3. 创建 `.dockerignore`
4. 在 README.md 中添加 Docker 部署说明

**依赖:** 无额外 Python 依赖

**预估工作量:** ~150 LOC (配置文件), 0.5 天

---

### 3.3 DingTalk (钉钉) 通道 — P1

**nanobot 实现方式:**
- 使用钉钉开放平台 Stream Mode (WebSocket 长连接，无需公网 IP)
- 配置: `clientId` (AppKey) + `clientSecret` (AppSecret)
- 支持 `allowFrom` 用户白名单

**openclaw-py 当前状态:**
- 23 个通道中无 DingTalk
- 已有完善的通道抽象层 (`src/pyclaw/channels/`)
- 已有 Feishu (飞书) 通道，架构类似

**实施方案:**
1. 新建 `src/pyclaw/channels/dingtalk/`:
   - `channel.py` — DingTalkChannel 实现
   - `__init__.py`
2. 使用钉钉 Stream SDK (`dingtalk-stream`) 建立 WebSocket 连接
3. 实现消息收发:
   - 接收: Stream 回调处理用户消息
   - 发送: OpenAPI 发送消息 (单聊/群聊)
4. 配置 schema: 在 `ChannelsConfig` 中添加 `dingtalk` 字段
5. 支持功能: 文本消息、Markdown、文件/图片

**依赖:** `dingtalk-stream` (可选依赖)

**预估工作量:** ~300 LOC, 1 天

---

### 3.4 QQ 通道 — P1

**nanobot 实现方式:**
- 使用 botpy SDK (QQ 官方机器人 SDK) + WebSocket
- 配置: `appId` + `secret`
- 当前仅支持私聊消息
- 需在 QQ 开放平台注册开发者

**openclaw-py 当前状态:**
- 23 个通道中无 QQ
- 通道抽象层完备，添加新通道流程成熟

**实施方案:**
1. 新建 `src/pyclaw/channels/qq/`:
   - `channel.py` — QQChannel 实现
   - `__init__.py`
2. 使用 `qq-botpy` SDK 建立 WebSocket 连接
3. 实现消息收发:
   - 接收: 注册 `on_message_create` / `on_direct_message_create`
   - 发送: 调用消息 API
4. 配置 schema: 在 `ChannelsConfig` 中添加 `qq` 字段
5. 先实现私聊，后续扩展群聊

**依赖:** `qq-botpy` (可选依赖)

**预估工作量:** ~250 LOC, 1 天

---

### 3.5 OAuth CLI 登录流暴露 — P1

**nanobot 实现方式:**
```bash
nanobot provider login openai-codex
```
- 支持 OAuth 和 Device Code 两种流程
- OpenAI Codex 使用 OAuth, GitHub Copilot 使用 Device Code
- 登录后凭证自动保存到配置

**openclaw-py 当前状态:**
- OAuth 基础设施完备:
  - `src/pyclaw/agents/providers/oauth_providers.py` — MiniMaxOAuthFlow, QwenOAuthFlow, GitHub Copilot Device Code
  - `src/pyclaw/agents/providers/auth_providers.py` — 认证规格定义
  - `src/pyclaw/agents/auth_profiles/types.py` — OAuthCredential
- CLI 命令 `pyclaw auth login` 仅支持 API Key
- OAuth 流从未在 CLI 中被调用

**实施方案:**
1. 修改 `src/pyclaw/cli/commands/auth_cmd.py`:
   - `auth_login()` 增加 `--method` 参数 (api-key / oauth / device-code)
   - 根据 provider 自动检测认证方式
   - 调用对应的 OAuth/Device Code 流
2. 新增 `pyclaw auth login --provider openai-codex` 支持
3. 增加 `pyclaw auth login --provider github-copilot` 支持
4. 登录成功后自动保存到 auth-profiles.json

**依赖:** 无 — 代码已存在

**预估工作量:** ~150 LOC, 0.5 天

---

### 3.6 技能市场 (远程搜索/安装) — P2

**nanobot 实现方式:**
- ClawHub 集成: 搜索和安装公共 Agent 技能
- 通过 Skill 指令触发: 让 Agent 读取远程 skill.md 并自行安装
- 技能发现和安装完全由 Agent 自主完成

**openclaw-py 当前状态:**
- 技能系统完备: `SKILL.md` 发现和注入
- 技能加载来源: workspace `.skills/`, `.cursor/skills/`, `.agents/skills/`, 内置 skills
- ClawHub 在 SECURITY.md 中被引用为独立项目
- 无远程搜索/安装命令

**实施方案:**
1. 新建 `src/pyclaw/agents/skills/marketplace.py`:
   - `search_skills(query)` — 搜索远程技能仓库
   - `install_skill(name)` — 下载并安装到 workspace
   - `list_installed()` — 列出已安装技能
   - `uninstall_skill(name)` — 卸载技能
2. 远程仓库: GitHub API 访问 clawhub 仓库，或自定义 registry
3. CLI 命令:
   - `pyclaw skills search <query>`
   - `pyclaw skills install <name>`
   - `pyclaw skills list`
   - `pyclaw skills remove <name>`
4. 安全: 技能安装前展示权限声明，需用户确认

**依赖:** 无额外依赖 (使用已有 httpx)

**预估工作量:** ~400 LOC, 1.5 天

---

### 3.7 Agent 社交网络 — P2

**nanobot 实现方式:**
- Agent 可加入 Moltbook、ClawdChat 等 Agent 社交平台
- 通过消息指令触发: 发送一条消息即可自动注册加入
- Agent 在平台上可与其他 Agent 交互

**openclaw-py 当前状态:**
- 无任何 Agent 社交网络功能
- 已有完善的通道系统，技术上可扩展

**实施方案:**
1. 新建 `src/pyclaw/social/`:
   - `registry.py` — 社交平台注册表
   - `moltbook.py` — Moltbook 平台适配
   - `clawdchat.py` — ClawdChat 平台适配
2. 通过 Skill 方式集成 (符合 nanobot 的做法):
   - 创建 `skills/social/` 技能包
   - 技能读取远程 skill.md 完成注册
3. 在 Agent 工具中添加 `social_join` / `social_status` 工具

**依赖:** 无额外依赖

**预估工作量:** ~300 LOC, 1 天

---

### 3.8 Workspace 模板同步命令 — P2

**nanobot 实现方式:**
- `nanobot onboard` 自动创建 workspace 并同步模板
- 自动同步: AGENTS.md, HEARTBEAT.md 等

**openclaw-py 当前状态:**
- 模板文件完备: `src/pyclaw/agents/templates/` 下有 AGENTS.md, SOUL.md, HEARTBEAT.md 等
- 需手动复制到 `~/.pyclaw/workspace/`
- Doctor 检查 workspace 但不执行复制

**实施方案:**
1. 新建 `src/pyclaw/agents/workspace_sync.py`:
   - `sync_templates(force=False)` — 比较并同步模板
   - `diff_templates()` — 展示本地与模板差异
   - 策略: 仅创建缺失文件，不覆盖已修改文件 (除非 `force`)
2. CLI 命令:
   - `pyclaw workspace sync` — 同步模板
   - `pyclaw workspace diff` — 查看差异
   - `pyclaw workspace reset` — 重置为默认模板
3. 在 `pyclaw setup` 流程中自动调用 sync

**依赖:** 无额外依赖

**预估工作量:** ~200 LOC, 0.5 天

---

### 3.9 Progress Streaming — P3

**nanobot 实现方式:**
- 长时间操作发送结构化进度事件
- 客户端可展示进度条或状态更新

**openclaw-py 当前状态:**
- 通用 LLM 流式输出 (`src/pyclaw/agents/stream.py`)
- Block streaming (`src/pyclaw/auto_reply/block_streaming.py`)
- 无结构化的操作进度事件

**实施方案:**
1. 定义进度事件类型:
   ```python
   class ProgressEvent:
       task_id: str
       status: Literal["started", "progress", "completed", "failed"]
       progress: float  # 0.0 - 1.0
       message: str
   ```
2. 在 Gateway 事件系统中添加 `EVENT_PROGRESS`
3. 在工具执行、技能安装等长操作中发送进度事件
4. Flet UI 中展示进度条

**依赖:** 无额外依赖

**预估工作量:** ~200 LOC, 0.5 天

---

### 3.10 语音转录完善 — P3

**nanobot 实现方式:**
- 配置 Groq provider 后，Telegram 语音消息自动通过 Whisper 转录
- 转录结果作为文本消息传入 Agent

**openclaw-py 当前状态:**
- 语音 UI 模块 (`src/pyclaw/ui/voice.py`): TTS 和 STT 骨架
- 媒体理解: 已有 OpenAI Whisper 和 Google 音频转录
- Telegram 通道: 无自动语音转录
- Flet 语音面板: 转录按钮未实现文件选择

**实施方案:**
1. 在 Telegram 通道中添加语音消息处理:
   - 检测 voice/audio 消息
   - 下载音频文件
   - 调用 Whisper API 转录
   - 将转录文本作为消息内容传入 Agent
2. 支持 Groq Whisper (免费) 和 OpenAI Whisper
3. 完善 Flet 语音 UI 的转录功能

**依赖:** 无额外依赖 (已有 openai SDK)

**预估工作量:** ~200 LOC, 0.5 天

---

## 四、实施计划

### Phase 50: MCP 支持 + Docker 部署 (P0)

**目标:** 补齐两个最重要的缺失功能

| 任务 | 文件/模块 | 工作量 |
|------|-----------|--------|
| MCP 类型定义 | `src/pyclaw/mcp/types.py` | 100 LOC |
| MCP stdio 传输 | `src/pyclaw/mcp/stdio_transport.py` | 150 LOC |
| MCP HTTP 传输 | `src/pyclaw/mcp/http_transport.py` | 150 LOC |
| MCP 客户端 | `src/pyclaw/mcp/client.py` | 200 LOC |
| MCP 工具注册 | `src/pyclaw/mcp/registry.py` | 100 LOC |
| MCP 配置 schema | `src/pyclaw/config/schema.py` 修改 | 30 LOC |
| MCP CLI 命令 | `src/pyclaw/cli/commands/mcp_cmd.py` | 80 LOC |
| MCP 测试 | `tests/test_mcp.py` | 200 LOC |
| Dockerfile | `Dockerfile` | 40 LOC |
| docker-compose.yml | `docker-compose.yml` | 30 LOC |
| .dockerignore | `.dockerignore` | 15 LOC |

**配置格式 (兼容 nanobot / Claude Desktop):**
```json
{
  "tools": {
    "mcpServers": {
      "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
      },
      "remote-api": {
        "url": "https://api.example.com/mcp/",
        "headers": { "Authorization": "Bearer xxx" },
        "toolTimeout": 60
      }
    }
  }
}
```

**验收标准:**
- `pyclaw mcp status` 显示已连接的 MCP 服务器和可用工具
- Agent 可调用 MCP 工具
- `docker compose up -d pyclaw-gateway` 成功启动
- `docker compose run --rm pyclaw-cli agent -m "Hello"` 正常对话

**预估总工作量:** 3 天

---

### Phase 51: DingTalk + QQ 通道 + OAuth CLI (P1)

**目标:** 补齐国内主流 IM 通道，完善认证流程

| 任务 | 文件/模块 | 工作量 |
|------|-----------|--------|
| DingTalk 通道 | `src/pyclaw/channels/dingtalk/channel.py` | 250 LOC |
| DingTalk 配置 | `src/pyclaw/config/schema.py` 修改 | 20 LOC |
| QQ 通道 | `src/pyclaw/channels/qq/channel.py` | 200 LOC |
| QQ 配置 | `src/pyclaw/config/schema.py` 修改 | 20 LOC |
| OAuth CLI 接线 | `src/pyclaw/cli/commands/auth_cmd.py` 修改 | 150 LOC |
| DingTalk 测试 | `tests/test_dingtalk_channel.py` | 100 LOC |
| QQ 测试 | `tests/test_qq_channel.py` | 100 LOC |
| OAuth 测试 | `tests/test_auth_oauth_cli.py` | 80 LOC |

**DingTalk 配置格式:**
```json
{
  "channels": {
    "dingtalk": {
      "enabled": true,
      "clientId": "YOUR_APP_KEY",
      "clientSecret": "YOUR_APP_SECRET",
      "allowFrom": []
    }
  }
}
```

**QQ 配置格式:**
```json
{
  "channels": {
    "qq": {
      "enabled": true,
      "appId": "YOUR_APP_ID",
      "secret": "YOUR_APP_SECRET",
      "allowFrom": []
    }
  }
}
```

**验收标准:**
- 钉钉机器人收发消息正常
- QQ 机器人收发私聊消息正常
- `pyclaw auth login --provider github-copilot` 完成 Device Code 登录
- `pyclaw auth login --provider openai-codex` 完成 OAuth 登录

**可选依赖更新 (`pyproject.toml`):**
```toml
[project.optional-dependencies]
dingtalk = ["dingtalk-stream>=1.0"]
qq = ["qq-botpy>=1.0"]
```

**预估总工作量:** 2.5 天

---

### Phase 52: 技能市场 + Workspace 同步 + Agent 社交 (P2)

**目标:** 增强生态和开发体验

| 任务 | 文件/模块 | 工作量 |
|------|-----------|--------|
| 技能市场核心 | `src/pyclaw/agents/skills/marketplace.py` | 300 LOC |
| 技能安全审查 | `src/pyclaw/agents/skills/security.py` | 100 LOC |
| 技能 CLI | `src/pyclaw/cli/commands/skills_cmd.py` | 120 LOC |
| Workspace 同步 | `src/pyclaw/agents/workspace_sync.py` | 200 LOC |
| Workspace CLI | CLI 集成 | 50 LOC |
| Agent 社交技能 | `src/pyclaw/agents/templates/skills/social/` | 150 LOC |
| 测试 | `tests/test_skills_marketplace.py`, `tests/test_workspace_sync.py` | 200 LOC |

**验收标准:**
- `pyclaw skills search weather` 搜索远程技能
- `pyclaw skills install weather` 安装技能到 workspace
- `pyclaw workspace sync` 同步缺失模板
- Agent 可通过技能指令加入社交平台

**预估总工作量:** 2 天

---

### Phase 53: Progress Streaming + 语音完善 (P3)

**目标:** 体验优化

| 任务 | 文件/模块 | 工作量 |
|------|-----------|--------|
| 进度事件类型 | `src/pyclaw/agents/progress.py` | 80 LOC |
| Gateway 进度广播 | `src/pyclaw/gateway/events.py` 修改 | 50 LOC |
| 工具进度集成 | 工具模块修改 | 80 LOC |
| Flet 进度 UI | `src/pyclaw/ui/` 修改 | 60 LOC |
| Telegram 语音转录 | `src/pyclaw/channels/telegram/` 修改 | 100 LOC |
| Flet 语音完善 | `src/pyclaw/ui/voice.py` 修改 | 80 LOC |
| 测试 | `tests/test_progress.py`, `tests/test_voice_transcribe.py` | 120 LOC |

**验收标准:**
- 长时间工具操作在 UI 中显示进度条
- Telegram 语音消息自动转录为文本
- Flet 语音面板可选择文件转录

**预估总工作量:** 1.5 天

---

## 五、实施顺序与依赖关系

```
Phase 50 (P0): MCP + Docker                              ← 已完成 ✅
    ↓
Phase 51 (P1): DingTalk + QQ + OAuth CLI + 技能市场       ← 已完成 ✅
    ↓
Phase 52 (P2): Agent 社交网络
    ↓
Phase 53 (P3): Progress Streaming + 语音完善
```

Phase 50-51 已全部实施。Phase 52-53 为后续可选增强。

---

## 六、实施完成情况 (2026-03-01)

| 指标 | 计划前 | 计划目标 | 当前状态 |
|------|--------|----------|----------|
| MCP 支持 | ❌ | ✅ stdio + HTTP | **✅ 已完成** — 5 文件 (types/client/registry/stdio/http) |
| Docker 部署 | ❌ | ✅ Dockerfile + Compose | **✅ 已完成** — Dockerfile + docker-compose.yml + .dockerignore |
| 通道数 | 23 | 25 (+DingTalk, +QQ) | **✅ 已完成** — 25 通道 |
| OAuth CLI | 代码存在未暴露 | ✅ 完整 CLI 流 | **✅ 已完成** — `--method auto/api-key/device-code/oauth` |
| 技能市场 | 仅本地 | ✅ 远程搜索/安装 | **✅ 已完成** — `pyclaw skills search/install/list/remove` |
| Workspace 同步 | 手动 | ✅ 自动 | **✅ 已完成** — `pyclaw workspace sync/diff` |
| Agent 社交网络 | ❌ | ✅ 技能驱动 | 待实施 (P2) |
| Progress Streaming | 通用 | ✅ 结构化事件 | 待实施 (P3) |
| 语音转录 | 骨架 | ✅ 完整 | 待实施 (P3) |
| 新增代码量 | — | ~3,500 LOC | **~2,800 LOC** (Phase 50-51) |
| 新增测试 | — | — | **57 个测试** (4 个测试文件) |
| .py 文件总数 | ~375 | — | **398** |
| 源码总量 | ~51,000 LOC | — | **~56,500 LOC** |
| 测试总数 | 1,791 | — | **1,848** |

通过有选择性地借鉴 nanobot 的实用功能，openclaw-py 已补齐 MCP 生态集成、容器化部署、国内 IM 通道 (DingTalk + QQ)、OAuth CLI 登录、技能市场、Workspace 模板同步等关键短板。后续 Phase 52-53 (Agent 社交、Progress Streaming、语音转录) 可按需实施。
