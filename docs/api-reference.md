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
  "type": "request",
  "id": "unique-request-id",
  "method": "method.name",
  "params": { ... }
}
```

#### 响应帧 (Server → Client)

```json
{
  "type": "response",
  "id": "same-request-id",
  "status": "ok",
  "payload": { ... }
}
```

错误响应：

```json
{
  "type": "response",
  "id": "same-request-id",
  "status": "error",
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

连接后第一个请求必须是 `connect`，携带认证 token：

```json
{
  "type": "request",
  "id": "1",
  "method": "connect",
  "params": {
    "token": "your-auth-token",
    "clientName": "my-app",
    "protocolVersion": 3
  }
}
```

### RPC 方法列表

#### 连接与健康

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `connect` | `token`, `clientName`, `protocolVersion` | `{ connected: true }` | 认证并建立连接 |
| `health` | (无) | `{ status, uptime, connections }` | 健康检查 |

#### 聊天

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `chat.send` | `sessionId`, `message`, `model?` | `{ messageId }` | 发送消息 (触发 agent 回复) |
| `chat.abort` | `sessionId` | `{ aborted }` | 中止当前生成 |
| `chat.resend` | `sessionId`, `messageId` | `{ messageId }` | 重新生成回复 |
| `chat.edit` | `sessionId`, `messageId`, `text` | `{ ok }` | 编辑已发送消息 |

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
| `sessions.list` | `limit?`, `offset?` | `[{ id, title, ... }]` | 列出会话 |
| `sessions.get` | `sessionId` | `{ id, messages, ... }` | 获取会话详情 |
| `sessions.create` | `title?`, `agentId?` | `{ id }` | 创建新会话 |
| `sessions.delete` | `sessionId` | `{ deleted }` | 删除会话 |
| `sessions.cleanup` | `olderThanDays?` | `{ removed }` | 清理旧会话 |

#### Agent 管理

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `agents.list` | (无) | `[{ id, name, model }]` | 列出 Agent |
| `agents.bindings` | (无) | `[{ pattern, agentId }]` | 查看路由绑定 |

#### 通道

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `channels.list` | (无) | `[{ id, type, status }]` | 列出通道 |
| `channels.status` | (无) | `[{ id, connected, issues }]` | 通道状态 |

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
| `browser.start` | `headless?` | `{ sessionId }` | 启动浏览器 |
| `browser.navigate` | `url` | `{ ok }` | 导航 |
| `browser.screenshot` | `format?` | `{ data }` (base64) | 截图 |
| `browser.click` | `selector` | `{ ok }` | 点击元素 |
| `browser.close` | (无) | `{ ok }` | 关闭浏览器 |

#### 定时任务

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `cron.list` | (无) | `[{ id, cron, ... }]` | 列出定时任务 |
| `cron.add` | `cron`, `message`, `agentId?` | `{ id }` | 添加任务 |
| `cron.remove` | `id` | `{ ok }` | 删除任务 |

#### 工具

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `tools.list` | (无) | `[{ name, description }]` | 列出可用工具 |
| `tools.exec_approve` | `requestId`, `approved` | `{ ok }` | 审批命令执行请求 |

#### 设备配对

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `device.initiate` | `deviceName` | `{ code }` | 发起配对 |
| `device.complete` | `code`, `response` | `{ paired }` | 完成配对 |

#### 日志

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `logs.query` | `level?`, `limit?`, `since?` | `[{ ts, level, msg }]` | 查询日志 |

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

### CLI 检查

```bash
# 查看 MCP 服务器状态
pyclaw mcp status

# 列出所有 MCP 工具
pyclaw mcp list-tools
```

---

## 4. 错误码

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
