# maxclaw (Go) 与 openclaw-py (Python) 功能差异分析与集成计划

> 生成日期：2026-03-02  
> 目标：审查 maxclaw (Go) 项目的独特功能，评估 openclaw-py 可借鉴的功能点，并给出集成计划

---

## 一、项目概览对比

| 维度 | maxclaw (Go) | openclaw-py (Python) |
|------|-------------|---------------------|
| 语言 | Go 1.22+ | Python 3.12+ |
| CLI | Cobra | Typer + Rich |
| Web 框架 | 自建 HTTP + gorilla/websocket | FastAPI + uvicorn + websockets |
| UI | React Web + Electron 桌面 | Flet（桌面/Web/移动） |
| LLM | OpenAI 兼容 API | OpenAI / Anthropic / Gemini / Ollama |
| 配置 | JSON (`~/.maxclaw/config.json`) | JSON5 (`~/.pyclaw/pyclaw.json`) |
| 通道数 | ~10 个 | 25+ 个 |
| 工具数 | ~12 个 | 20+ 个 |
| 记忆 | Markdown + grep | SQLite FTS5 + LanceDB + MMR |
| 定时任务 | robfig/cron | APScheduler |
| 部署 | 单二进制 + Docker | pip + Docker |

---

## 二、功能差异全景

### 2.1 maxclaw 独有功能（openclaw-py 缺失）

| 编号 | 功能 | maxclaw 实现 | openclaw-py 现状 | 优先级 |
|------|------|------------|-----------------|--------|
| F01 | **任务规划系统 (Plan/Step)** | `internal/agent/plan.go` — Plan/Step/PlanManager/StepDetector | 无 | **P0** |
| F02 | **用户打断机制 (Interrupt)** | `internal/agent/interrupt.go` — InterruptibleContext, cancel/append 双模式 | 无 | **P0** |
| F03 | **意图分析器 (IntentAnalyzer)** | `internal/agent/intent.go` — 基于规则的 stop/correction/append/continue 识别 | 无 | **P0** |
| F04 | **消息总线按 Session Peek** | `internal/bus/` — PeekInboundForSession 非阻塞取消息 | 无等价实现 | **P0** |
| F05 | **每日摘要服务 (DailySummary)** | `internal/memory/daily_summary.go` — 定时汇总前一天会话 | 无 | **P1** |
| F06 | **Message 级 Timeline** | `internal/session/` — 消息中嵌入 TimelineEntry/TimelineActivity | 无 | **P1** |
| F07 | **Cron 执行历史** | `internal/cron/` — ExecutionRecord/HistoryStore | 仅有调度，无历史记录 | **P1** |
| F08 | **Cron every/once 调度** | `internal/cron/` — every_ms / once / at 解析 | 仅支持 cron 表达式 | **P1** |
| F09 | **Spawn NotifyParent** | `pkg/tools/spawn.go` — 子 Agent 完成后通知父会话 | 有 spawn 但无 NotifyParent | **P1** |
| F10 | **RuntimeContext 注入** | `pkg/tools/` — channel/chatId 注入工具执行上下文 | 部分实现 | **P2** |
| F11 | **Electron 桌面集成** | 终端(xterm)、文件预览、自动更新、全局快捷键 | Flet 无这些功能 | **P2** |
| F12 | **数据导入导出** | Electron — JSZip 打包 config+sessions | 无 | **P2** |
| F13 | **Markdown 记忆备选** | MEMORY.md + HISTORY.md + grep 简单策略 | 用 SQLite+向量，可互补 | **P3** |
| F14 | **Web Fetch Chrome 模式** | 复用 Chrome profile / CDP | Playwright 为主 | **P3** |

### 2.2 openclaw-py 独有优势（maxclaw 缺失）

| 功能 | 说明 |
|------|------|
| 25+ 消息通道 | maxclaw 仅 ~10 个 |
| SQLite FTS5 + LanceDB 记忆 | 结构化混合检索，远超 Markdown grep |
| 本地模型推理 (llama.cpp / MLX) | maxclaw 无本地模型 |
| 安全审计体系 | exec_hardening、SSRF、audit_extra 等 |
| 插件/钩子系统 | entry_point + HOOK.md |
| Office 文件读取 | PDF/DOCX/XLSX/PPTX |
| 桌面截图 | mss 跨平台截图 |
| Flet 跨平台 UI | 桌面+Web+移动统一 |
| ACP 协议集成 | Agent Control Protocol |

---

## 三、可借鉴功能详细分析

### 3.1 [P0] 任务规划系统 (Plan/Step)

#### maxclaw 实现要点

```
Plan {
  ID, Goal, Status (pending/running/paused/completed/failed)
  Steps []Step {ID, Description, Status, Result, Progress{Current,Total}}
  CurrentStepIndex, IterationCount
}

PlanManager — 内存缓存 + 文件持久化 (<workspace>/.sessions/<key>/plan.json)
StepDetector — 三步检测：显式标记 → 过渡词 → 超时
```

- **步骤完成检测**：检测 `[done]`/`[完成]` 标记、过渡词（"接下来"/"then"）、迭代超时
- **暂停/恢复**：支持 `PlanStatusPaused` → `IsContinueIntent()` 恢复
- **上下文注入**：`ToContextString()` 生成计划摘要注入 LLM system prompt

#### 集成方案

1. 新建 `src/pyclaw/agents/planner.py`
2. 定义 `Plan`、`Step`、`PlanManager` Pydantic 模型
3. 实现 `StepDetector` 逻辑（关键词 + 过渡词 + 超时）
4. 在 `runner.py` 的 Agent 循环中集成 Plan 上下文
5. 在 `session.py` 中增加 plan 持久化
6. 添加 `plan.list`/`plan.get`/`plan.resume` Gateway 方法

#### 工作量估算

- 开发：3-4 天
- 测试：1-2 天

---

### 3.2 [P0] 用户打断机制 (Interrupt)

#### maxclaw 实现要点

```
InterruptMode: cancel | append
InterruptibleContext {ctx, cancel, interrupts, appendQueue, onInterrupt}

cancel 模式 — 调用 ctx.cancel() 终止 LLM 流式生成
append 模式 — 消息入 appendQueue，下一轮注入上下文
```

- **500ms 轮询**：每次 Agent 循环中 `checkIncomingMessages` 定时检查新消息
- **PeekInboundForSession**：非阻塞从消息总线取目标 session 消息
- **与意图分析联动**：`HandleInterruption` → `IntentAnalyzer` → 决定 cancel/append

#### 集成方案

1. 新建 `src/pyclaw/agents/interrupt.py`
2. 实现 `InterruptibleContext`，基于 `asyncio.Event` / `asyncio.Queue`
3. 在 Gateway WebSocket 层增加 session-level 消息 peek
4. 修改 `runner.py`，在流式循环中检查 interrupt 信号
5. cancel 模式：取消当前 `stream_llm` 协程
6. append 模式：将补充消息加入下一轮上下文

#### 工作量估算

- 开发：3-4 天
- 测试：2 天（需覆盖流式中断场景）

---

### 3.3 [P0] 意图分析器 (IntentAnalyzer)

#### maxclaw 实现要点

```
UserIntent: continue | correction | append | new_topic | stop
IntentResult: {Intent, Confidence, IsInterrupt, Explanation}

规则优先级：stop(0.95) > correction(0.85) > append(0.80) > 短消息启发式(0.60)
关键词：中英双语
```

- 纯规则，无 LLM 调用，响应极快
- `IsInterrupt` 决定走 cancel 还是 append 路径

#### 集成方案

1. 新建 `src/pyclaw/agents/intent.py`
2. 定义 `UserIntent` 枚举、`IntentResult` 模型
3. 实现 `IntentAnalyzer` 类，包含中英文关键词规则
4. 与 `interrupt.py` 集成

#### 工作量估算

- 开发：1 天
- 测试：0.5 天

---

### 3.4 [P0] 消息总线 Session Peek

#### maxclaw 实现要点

```
MessageBus {inbound chan, outbound chan}
PeekInboundForSession(sessionKey) — 非阻塞取目标 session 消息，其余放回
```

#### 集成方案

1. 在 `src/pyclaw/gateway/` 中增加 `message_bus.py`
2. 基于 `asyncio.Queue` 实现双通道消息总线
3. 实现 `peek_inbound_for_session()` — 遍历队列找目标 session 消息
4. 修改 Gateway WebSocket handler，将入站消息发布到 bus
5. 在 Agent runner 中消费 bus 消息

#### 工作量估算

- 开发：2 天
- 测试：1 天

---

### 3.5 [P1] 每日摘要服务 (DailySummary)

#### maxclaw 实现要点

- 定时（默认每小时）扫描前一天会话
- 多源合并：session 文件 + HISTORY.md
- 幂等写入 MEMORY.md `## Daily Summaries` 节
- `uniqueTopN` 提取用户/助手亮点

#### 集成方案

1. 新建 `src/pyclaw/memory/daily_summary.py`
2. 使用 APScheduler 定时触发
3. 从 SessionManager 获取前日会话数据
4. 生成摘要并写入 memory store（SQLite 或 Markdown 文件）
5. 作为 Gateway 后台服务启动

#### 工作量估算

- 开发：2 天
- 测试：1 天

---

### 3.6 [P1] Message 级 Timeline

#### maxclaw 实现要点

```
Message {
  Role, Content,
  Timeline []TimelineEntry {
    Kind, Activity {Type, Summary, Detail}
  }
}
```

- 工具调用、状态变更等活动嵌入消息结构
- 便于 UI 展示完整执行过程

#### 集成方案

1. 在 `session.py` 的 `AgentMessage` 中添加 `timeline` 字段
2. 定义 `TimelineEntry`、`TimelineActivity` Pydantic 模型
3. 在 `runner.py` 工具调用前后写入 timeline
4. WebSocket 事件中携带 timeline 数据
5. UI 层展示 timeline 条目

#### 工作量估算

- 开发：2 天
- 测试：1 天

---

### 3.7 [P1] Cron 增强

#### maxclaw 实现要点

- **三种调度类型**：`every`（周期 ms）、`cron`（cron 表达式）、`once`（一次性定时）
- **at 时间解析**：RFC3339、`YYYY-MM-DD HH:MM`、仅 `HH:MM`（下一天同时间）
- **执行历史**：`ExecutionRecord` 含 startedAt、endedAt、status、output、error、duration
- **HistoryStore**：内存 + 持久化，最多 1000 条
- **通知集成**：任务完成后通过 channel 推送结果

#### 集成方案

1. 扩展 `src/pyclaw/cron/scheduler.py`：
   - 新增 `every` 调度（`IntervalTrigger`）
   - 新增 `once` 调度（`DateTrigger`）
   - 新增 `at` 时间解析
2. 新建 `src/pyclaw/cron/history.py`：
   - `ExecutionRecord` 模型
   - `HistoryStore`（SQLite 或内存 + JSON）
3. 扩展 `CronTool`：支持 `every`/`once`/`at` 参数
4. 添加 `cron.history` Gateway 方法

#### 工作量估算

- 开发：2-3 天
- 测试：1 天

---

### 3.8 [P1] Spawn 工具增强

#### maxclaw 实现要点

- **NotifyParent**：子 Agent 完成后回调父会话
- **ListRunningTasks**：列出当前运行中的子任务
- **RuntimeContext**：传递 channel/chatId 给子 Agent

#### 集成方案

1. 修改 `src/pyclaw/agents/subagents/` 中的 spawn 逻辑
2. 添加 `notify_parent` 回调机制
3. 添加任务跟踪器（running tasks registry）
4. 在 `SubagentsTool` 中增加 `list_running` 功能
5. 通过 RuntimeContext 传递 channel 信息

#### 工作量估算

- 开发：2 天
- 测试：1 天

---

### 3.9 [P2] RuntimeContext 注入

#### maxclaw 实现要点

```go
type RuntimeContext struct {
    Channel  string
    ChatID   string
    Session  string
}
RuntimeContextFrom(ctx) — 从 context.Context 中提取
```

- 所有工具通过 RuntimeContext 获取当前 channel/chatId
- spawn / message / cron 工具依赖此机制

#### 集成方案

1. 在 `src/pyclaw/agents/tools/` 中定义 `RuntimeContext` dataclass
2. 在 runner 循环中构建并传递 RuntimeContext
3. 各工具通过 RuntimeContext 获取上下文信息

#### 工作量估算

- 开发：1 天
- 测试：0.5 天

---

### 3.10 [P2] 数据导入导出

#### maxclaw 实现要点

- JSZip 打包 config + sessions
- 导入时恢复配置和会话

#### 集成方案

1. 新建 `src/pyclaw/cli/commands/backup_cmd.py`
2. 使用 `zipfile` 标准库
3. 导出：打包 `~/.pyclaw/` 下的配置和会话文件
4. 导入：解压并恢复
5. 添加 `pyclaw backup export` / `pyclaw backup import` CLI 命令
6. 添加 `backup.export` / `backup.import` Gateway 方法

#### 工作量估算

- 开发：1-2 天
- 测试：0.5 天

---

## 四、集成优先级路线图

### Phase 1 — 核心 Agent 增强（P0，约 2 周）

```
Week 1:
├── [F03] 意图分析器 IntentAnalyzer        (1.5 天)
├── [F04] 消息总线 Session Peek            (3 天)
└── [F02] 用户打断机制 Interrupt           (3.5 天，依赖 F03+F04)

Week 2:
├── [F01] 任务规划系统 Plan/Step           (5 天)
└── 集成测试 + 修复                         (2 天)
```

### Phase 2 — 记忆与调度增强（P1，约 2 周）

```
Week 3:
├── [F05] 每日摘要服务 DailySummary        (3 天)
├── [F06] Message Timeline                  (3 天)
└── [F07+F08] Cron 增强                    (3 天)

Week 4:
├── [F09] Spawn NotifyParent               (3 天)
└── 集成测试 + 修复                         (2 天)
```

### Phase 3 — 辅助功能（P2，约 1 周）

```
Week 5:
├── [F10] RuntimeContext 注入              (1.5 天)
├── [F12] 数据导入导出                     (2 天)
└── UI 层适配 + 文档更新                   (1.5 天)
```

---

## 五、技术实现注意事项

### 5.1 异步适配

maxclaw 使用 Go 的 goroutine + channel 实现并发，移植到 Python 需使用 `asyncio` 生态：

| maxclaw (Go) | openclaw-py (Python) |
|-------------|---------------------|
| `go func()` | `asyncio.create_task()` |
| `chan T` | `asyncio.Queue` |
| `context.WithCancel` | `asyncio.Event` / `CancelScope` |
| `sync.RWMutex` | `asyncio.Lock` |
| `select {}` | `asyncio.wait()` / `asyncio.gather()` |

### 5.2 持久化策略

maxclaw 使用文件（JSON + Markdown），openclaw-py 已有 SQLite + JSONL 基础设施，建议：

- Plan 持久化：扩展现有 JSONL session 格式，新增 `plan` entry 类型
- 执行历史：使用 SQLite 表，与 memory 共享数据库连接
- 每日摘要：写入 memory store，同时生成 Markdown 可读文件

### 5.3 向后兼容

- 所有新功能默认关闭或无感知启用
- 配置 schema 新增字段使用合理默认值
- WebSocket v3 协议新增方法不影响现有客户端

### 5.4 测试策略

- 每个新模块需要单元测试覆盖 ≥80%
- 打断机制需要端到端集成测试
- Plan/Step 需要模拟多轮对话的场景测试

---

## 六、总结

### 核心收益

1. **任务规划 (Plan/Step)**：使 Agent 能处理复杂多步骤任务，大幅提升任务成功率
2. **用户打断 (Interrupt)**：实现更自然的人机交互，用户可实时纠正 Agent 方向
3. **意图分析 (Intent)**：智能判断用户意图，减少误解和无效循环
4. **每日摘要 (DailySummary)**：自动积累长期记忆，提升 Agent 连续性

### 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| 打断机制引入竞态条件 | 使用 asyncio 锁，充分测试并发场景 |
| Plan 系统过于复杂影响响应速度 | 步骤检测使用纯规则，不调用 LLM |
| 每日摘要生成质量不稳定 | 可选配 LLM 辅助生成摘要 |
| 向后兼容破坏 | 功能开关 + 渐进式启用 |

### 不建议直接移植的功能

| 功能 | 原因 |
|------|------|
| Electron 桌面端 | openclaw-py 已选择 Flet，技术栈差异太大 |
| MEMORY.md + grep 记忆 | openclaw-py 的 SQLite+向量方案更强 |
| WhatsApp Bridge (Node.js) | openclaw-py 已有 neonize 方案 |
| Web Fetch Chrome 模式 | 复杂度高，Playwright 已足够 |
