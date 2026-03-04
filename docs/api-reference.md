# API 参考文档

OpenClaw-Py 对外暴露两套 API：**WebSocket RPC** 和 **OpenAI 兼容 HTTP**。

---

## 1. Gateway WebSocket API

### 连接

```
ws://localhost:18789/ws
```

使用 JSON 帧协议 (v3)。每一帧包含以下结构：

#### 请求帧 (Client → Server)

```json
{
  "type": "req",
  "id": "unique-request-id",
  "method": "method.name",
  "params": { ... }
}
```

#### 响应帧 (Server → Client)

```json
{
  "type": "res",
  "id": "same-request-id",
  "ok": true,
  "payload": { ... }
}
```

错误响应：

```json
{
  "type": "res",
  "id": "same-request-id",
  "ok": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "Session not found"
  }
}
```

#### 事件帧 (Server → Client，推送)

```json
{
  "type": "event",
  "event": "chat.delta",
  "seq": 42,
  "payload": { ... }
}
```

### 认证

连接后第一个请求必须是 `connect`，携带认证参数：

```json
{
  "type": "req",
  "id": "1",
  "method": "connect",
  "params": {
    "minProtocol": 1,
    "maxProtocol": 3,
    "clientName": "my-app",
    "auth": { "token": "your-auth-token" }
  }
}
```

### RPC 方法列表

#### 连接与健康

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `connect` | `minProtocol`, `maxProtocol`, `clientName`, `auth.token` | `{ protocol, server }` | 认证并建立连接 |
| `health` | (无) | `{ status, uptime, connections }` | 健康检查 |

#### 聊天

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `chat.send` | `message`, `agentId?`, `sessionId?`, `model?`, `provider?`, `systemPrompt?`, `attachments?`, `abortPrevious?`, `temperature?` | `{ completed }` | 发送消息 (触发 agent 回复)。自动进行参数校验、内容净化、时间上下文注入 |
| `chat.abort` | `sessionId`, `agentId?` | `{ aborted }` | 中止当前生成 |
| `chat.history` | `sessionId`, `agentId?` | `{ messages }` | 获取会话消息历史 |
| `chat.resend` | `sessionId?`, `agentId?`, `provider?`, `model?` | `{ completed }` | 重新发送最后一条用户消息 (regenerate) |
| `chat.edit` | `message`, `sessionId?`, `agentId?`, `provider?`, `model?` | `{ completed }` | 编辑最后一条用户消息并重新运行 |

聊天过程中服务器推送以下事件：

| 事件 | payload | 说明 |
|------|---------|------|
| `chat.delta` | `{ sessionId, delta, role }` | 增量文本 |
| `chat.tool_call` | `{ sessionId, tool, args }` | 工具调用 |
| `chat.tool_result` | `{ sessionId, tool, result }` | 工具结果 |
| `chat.done` | `{ sessionId, usage }` | 回复完成 |
| `chat.error` | `{ sessionId, error }` | 错误 |

#### 会话

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `sessions.list` | (无) | `{ sessions: [{ agentId, file, path, size }] }` | 列出会话 |
| `sessions.preview` | `path`, `limit?` | `{ messages }` | 预览会话消息 |
| `sessions.delete` | `path` | `{ deleted }` | 删除会话 |
| `sessions.reset` | `path` | `{ reset }` | 重置会话（清空内容保留文件） |

#### Agent 管理

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `agents.list` | (无) | `[{ id, name, model }]` | 列出 Agent |
| `agents.bindings` | (无) | `[{ pattern, agentId }]` | 查看路由绑定 |

#### 通道

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `channels.list` | (无) | `[{ id, type, status }]` | 列出通道 |
| `channels.status` | `channel_id` 或 `channelId` | `{ channel_id, name, running, status, metrics? }` | 通道状态 |

#### 模型

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `models.list` | (无) | `[{ id, provider, ... }]` | 列出可用模型 |
| `models.probe` | `model`, `provider?` | `{ available, latency }` | 探测模型可用性 |

#### 配置

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `config.get` | `key?` | `{ value }` | 获取配置 |
| `config.set` | `key`, `value` | `{ ok }` | 设置配置 |
| `config.patch` | `patch` (JSON object) | `{ ok }` | 批量更新配置 |

#### 浏览器

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `browser.status` | `profile?` | `{ started, profile, tabCount, ... }` | 查看浏览器状态 |
| `browser.start` | `profile?` | `{ started, sessionId }` | 启动 Playwright 浏览器 |
| `browser.stop` | `profile?` | `{ started: false }` | 停止浏览器 |
| `browser.tabs` | `profile?` | `{ tabs: [...] }` | 列出所有 tab |
| `browser.open` | `url`, `profile?` | `{ opened, tabId, url, title }` | 新 tab 打开 URL |
| `browser.navigate` | `url`, `profile?` | `{ navigated, url, title }` | 在当前 tab 导航 |
| `browser.click` | `ref`, `profile?` | `{ clicked, ref }` | 点击元素 (CSS 选择器) |
| `browser.type` | `ref`, `text`, `profile?` | `{ typed, ref }` | 向元素填入文本 |
| `browser.screenshot` | `profile?`, `fullPage?` | `{ screenshotB64, mimeType, sizeBytes }` | 真实 Playwright 截图 |
| `browser.snapshot` | `profile?` | `{ htmlLength, htmlPreview }` | DOM 快照 |
| `browser.evaluate` | `fn`, `profile?` | `{ result }` | 在页面执行 JS |
| `browser.profiles` | (无) | `{ profiles }` | 列出浏览器 Profile |
| `browser.createProfile` | `name` | `{ created, profile }` | 创建 Profile |
| `browser.deleteProfile` | `name` | `{ deleted }` | 删除 Profile |
| `browser.focus` | `tabId`, `profile?` | `{ focused }` | 切换活跃 tab |
| `browser.close` | `tabId`, `profile?` | `{ closed }` | 关闭 tab |

#### 定时任务

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `cron.list` | (无) | `[{ id, cron, ... }]` | 列出定时任务 |
| `cron.add` | `cron`, `message`, `agentId?` | `{ id }` | 添加任务 |
| `cron.remove` | `id` | `{ ok }` | 删除任务 |
| `cron.history` | `jobId?`, `limit?` | `{ records, count }` | 执行历史 |

#### 工具

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `tools.list` | (无) | `[{ name, description }]` | 列出可用工具 |
| `tools.exec_approve` | `requestId`, `approved` | `{ ok }` | 审批命令执行请求 |

#### 计划管理

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `plan.list` | (无) | `{ plans, count }` | 列出计划 |
| `plan.get` | `planId` | `{ id, status, steps, ... }` | 获取计划详情 |
| `plan.resume` | `planId` | `{ resumed, plan? }` | 恢复暂停的计划 |
| `plan.delete` | `planId` | `{ deleted }` | 删除计划 |

#### 备份

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `backup.export` | (无) | `{ path, files }` | 导出备份 |
| `backup.status` | (无) | `{ backups: [{ path, size }], count }` | 备份列表与状态 |

#### 设备配对

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `device.initiate` | `deviceName` | `{ code }` | 发起配对 |
| `device.complete` | `code`, `response` | `{ paired }` | 完成配对 |

#### 日志

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `logs.tail` | `limit?`, `json?`, `localTime?` | `{ lines, count, path }` | 读取最近日志行 |
| `system.logs` | `lines?`, `level?` | `{ logs, count }` | 按级别过滤日志 |

#### 系统

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `system.info` | (无) | `{ platform, python, uptime }` | 系统信息 |
| `system.event` | `text`, `mode?` | `{ ok, eventType, mode }` | 发送系统事件 |
| `system.heartbeat.last` | (无) | `{ enabled, lastHeartbeatAt }` | 查询最近心跳 |
| `system.presence` | (无) | `{ entries }` | 查询组件在线状态 |

#### 扩展

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `usage.get` | `days?` | `{ totalTokens, estimatedCost, ... }` | 使用量与费用统计 |
| `doctor.run` | (无) | `{ checks, summary }` | 运行诊断检查 |
| `skills.list` | (无) | `{ skills, count }` | 列出可用 Skills |
| `tts.voices` | (无) | `{ voices }` | TTS 语音列表 |
| `update.check` | (无) | `{ currentVersion, updateAvailable }` | 检查更新 |
| `web.status` | (无) | `{ connected, uptime }` | 网页状态 |

> **注意**: 以下方法当前返回 `NOT_IMPLEMENTED` 错误:
> `tts.speak`, `wizard.start`, `wizard.step`, `push.send`, `voicewake.status`

---

## 2. OpenAI 兼容 HTTP API

### POST /v1/chat/completions

完全兼容 OpenAI Chat Completions API，支持流式和非流式。

#### 请求

```bash
curl -X POST http://localhost:18790/v1/chat/completions \
  -H "Authorization: Bearer $PYCLAW_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Hello!"}
    ],
    "stream": true
  }'
```

#### 非流式响应

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "created": 1709000000,
  "model": "gpt-4o",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "Hello! How can I help?"
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 20,
    "completion_tokens": 10,
    "total_tokens": 30
  }
}
```

#### 流式响应 (SSE)

```
data: {"id":"chatcmpl-...","object":"chat.completion.chunk","choices":[{"delta":{"content":"Hello"},"index":0}]}

data: {"id":"chatcmpl-...","object":"chat.completion.chunk","choices":[{"delta":{"content":"!"},"index":0}]}

data: [DONE]
```

### GET /v1/models

列出所有可用模型。

#### 响应

```json
{
  "object": "list",
  "data": [
    {
      "id": "gpt-4o",
      "object": "model",
      "owned_by": "openai",
      "created": 1709000000
    },
    {
      "id": "claude-sonnet-4-20250514",
      "object": "model",
      "owned_by": "anthropic",
      "created": 1709000000
    }
  ]
}
```

### POST /v1/responses

兼容 OpenAI Responses API，支持流式 SSE。

---

## 3. MCP (Model Context Protocol)

OpenClaw-Py 作为 MCP **客户端**，连接外部 MCP 服务器。

### 配置

在 `~/.pyclaw/pyclaw.json` 中添加 MCP 服务器：

```json
{
  "tools": {
    "mcpServers": {
      "server-name": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"]
      }
    }
  }
}
```

### 传输方式

| 方式 | 配置 | 适用场景 |
|------|------|----------|
| **stdio** | `command` + `args` | 本地进程 |
| **HTTP** | `url` + `headers` | 远程端点 |

### 工具发现

启动时自动调用每个 MCP 服务器的 `tools/list`，将发现的工具注册到 Agent 工具池。工具名称以 `mcp:<server>:<tool>` 格式标识。

### 热重载

MCP 配置支持热重载 — `McpConfigWatcher` 以固定间隔 (默认 5s) 轮询配置文件的 `tools.mcpServers` 段。
当检测到变更时，自动断开旧连接并重新连接新配置的 MCP 服务器。

### CLI 检查

```bash
# 查看 MCP 服务器状态
pyclaw mcp status

# 列出所有 MCP 工具
pyclaw mcp list-tools
```

---

## 4. Gateway CLI 命令

`pyclaw gateway` 子命令组提供网关的运维与调试能力。

| 命令 | 说明 | 关键参数 |
|------|------|----------|
| `pyclaw gateway` (无子命令) | 启动 Gateway 服务器（等同 `run`） | `--port`, `--bind`, `--auth-token` |
| `pyclaw gateway run` | 启动 Gateway 服务器 | `--port`, `--bind`, `--auth-token` |
| `pyclaw gateway status` | 显示服务状态 + 可选 RPC 探测 | `--url`, `--token`, `--password`, `--timeout`, `--no-probe`, `--deep`, `--json` |
| `pyclaw gateway probe` | 探测 Gateway 连通性 | `--url`, `--token`, `--password`, `--timeout`, `--json` |
| `pyclaw gateway call` | 底层 RPC 调用 | `METHOD` (位置参数), `--params`, `--url`, `--token`, `--password`, `--timeout`, `--json` |
| `pyclaw gateway discover` | 局域网发现 (mDNS/端口扫描) | `--timeout`, `--json` |

### 示例

```bash
# 查看 Gateway 状态（含探测）
pyclaw gateway status --deep --json

# 探测连通性
pyclaw gateway probe --url ws://192.168.1.100:18789

# 调用任意 RPC 方法
pyclaw gateway call health --params '{}'
pyclaw gateway call chat.send --params '{"message": "Hello"}'

# 局域网发现
pyclaw gateway discover --json
```

---

## 5. 本地模型管理 CLI

`pyclaw models` 子命令组中新增的本地模型管理命令：

| 命令 | 说明 | 关键参数 |
|------|------|----------|
| `pyclaw models download` | 从 HuggingFace/ModelScope 下载模型 | `REPO_ID`, `--filename`, `--backend` (llamacpp/mlx), `--source` |
| `pyclaw models local` | 列出已下载的本地模型 | `--json` |
| `pyclaw models delete-local` | 删除本地模型文件 | `MODEL_ID` |
| `pyclaw models select` | 设置默认活跃模型 | `MODEL_ID` |

### 支持后端

| 后端 | 安装 | 说明 |
|------|------|------|
| `llamacpp` | `pip install 'openclaw-py[llamacpp]'` | llama.cpp (GGUF 格式, CPU/GPU) |
| `mlx` | `pip install 'openclaw-py[mlx]'` | MLX (Apple Silicon 专用) |
| `ollama` | 外部安装 Ollama | 通过 OpenAI 兼容 API 接入 |

### 示例

```bash
# 下载 GGUF 模型
pyclaw models download Qwen/Qwen3-4B-GGUF

# 下载 MLX 模型 (Apple Silicon)
pyclaw models download mlx-community/Llama-3-8B-4bit --backend mlx

# 从 ModelScope 下载
pyclaw models download qwen/Qwen3-4B-GGUF --source modelscope

# 列出本地模型
pyclaw models local

# 设置默认模型
pyclaw models select "Qwen/Qwen3-4B-GGUF/qwen3-4b-q4_k_m.gguf"
```

---

## 6. Agent 工具扩展

Phase 63-65 新增的 Agent 工具：

| 工具 | 功能 | 注册方式 |
|------|------|----------|
| `desktop_screenshot` | 跨平台桌面截图 (mss) + macOS 窗口截图 | 默认注册 |
| `send_file` | 向用户发送文件 (自动检测 MIME 类型) | 默认注册 |
| `read_pdf` | PDF 文件文本提取 | 需 `pyclaw[office]` |
| `read_docx` | Word 文档文本提取 | 需 `pyclaw[office]` |
| `read_xlsx` | Excel 表格数据提取 | 需 `pyclaw[office]` |
| `read_pptx` | PowerPoint 幻灯片文本提取 | 需 `pyclaw[office]` |

---

## 7. 错误码

| 错误码 | 含义 |
|--------|------|
| `AUTH_REQUIRED` | 未认证或 token 无效 |
| `NOT_FOUND` | 资源不存在 (会话、Agent 等) |
| `INVALID_PARAMS` | 请求参数无效 |
| `RATE_LIMITED` | 请求频率超限 |
| `INTERNAL_ERROR` | 服务器内部错误 |
| `METHOD_NOT_FOUND` | RPC 方法不存在 |
| `ALREADY_EXISTS` | 资源已存在 |
| `ABORTED` | 操作被中止 |
| `NOT_IMPLEMENTED` | 方法已注册但尚未实现 |
