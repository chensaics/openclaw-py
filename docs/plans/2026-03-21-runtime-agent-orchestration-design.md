# 运行时智能体编排设计（草案）

> **日期**：2026-03-21  
> **状态**：设计草案（待实现拆分）  
> **依赖文档**：[架构设计](../architecture.md)、[概念总览](../concepts.md)、[RPD 客户端](../RPD_CLIENT_DESIGN.md)  
> **范围**：Gateway / Agent Runtime — 主 Agent 在**任务初期**完成编排，**执行阶段**以子 Agent 委派为主，并允许主 Agent **动态增删**运行中的子 Agent 或计划中的角色。

---

## 1. 目标与非目标

### 1.1 目标

- **任务初始编排**：在同一用户任务（或会话内明确划分的「工作单元」）开始时，由主 Agent 决定初始「班组」——角色、职责边界、是否并行、工具/MCP/技能子集偏好、可选模型覆盖策略。
- **执行以委派为主**：具体长路径工作尽量由子 Agent 完成；主 Agent 负责协调、合并结果、对用户的最终答复与风险把关。
- **拓扑可演进**：主 Agent 在运行中可**新增**子任务（新 spawn）或**终止**不再需要的运行中子 Agent（kill）；可对运行中子 Agent 纠偏（steer）。
- **与现有能力对齐**：延续 `SubagentManager`（深度、并发上限、`steer`/`kill`/事件）、配置中的 `SubagentConfig`（`tools_enabled` / `tools_disabled`、`agent_id`、`label` 等）。

### 1.2 非目标（本设计不一次性解决）

- 替换现有 7 级「消息 → Agent」路由；编排发生在**已选定主 Agent 之后**的会话内。
- 完整多租户隔离与跨用户子 Agent 共享（默认仍为单主会话树）。
- Canvas/A2UI 的可视化编排编辑器（可与 RPD 后续结合，本设计仅预留**结构化编排制品**供 UI 消费）。

---

## 2. 运行时模型（三阶段）

```text
[编排 Orchestrate] → [委派 Execute / Delegate] → [协调 Reconcile]
        ↑________________________|________________________|
                    （按需循环：增派 / steer / kill / 更新计划）
```

| 阶段 | 主 Agent 行为 | 子 Agent |
|------|----------------|----------|
| **编排** | 产出**编排制品**（见 §3）；决定首批子任务与并发关系 | 通常尚未创建 |
| **委派** | 通过工具发起 spawn；聚合子结果；决定下一步 | 执行具体子任务 |
| **协调** | 评估是否追加角色、终止冗余子任务、或 steer | 可能被 kill 或接收新指令 |

**「去除 Agent」语义**：

- **运行中**：`subagents` + `kill` — 与现有一致。
- **计划中**（尚未 spawn）：主 Agent 更新编排制品中的角色状态为 `retired` / `cancelled`，后续不得再向该角色派发；无需系统级进程。

---

## 3. 编排制品（Orchestration Manifest）

建议在**主会话**中持久化一份机器可读、体积可控的 JSON（或等价结构），由主 Agent 在编排阶段写入，之后 turn 只增量补丁。

**建议字段（最小集）**：

| 字段 | 说明 |
|------|------|
| `version` | 制品格式版本 |
| `task_id` / `goal` | 任务锚点与一句话目标 |
| `roles[]` | `id`, `name`, `responsibility`, `status`（`planned` / `running` / `completed` / `retired`） |
| `spawn_policy` | `max_parallel`, `preferred_models`（可选） |
| `tool_policy` | 每角色或全局：`allow` / `deny` 工具名模式（与 `SubagentConfig.tools_*` 对齐） |

**用途**：

- 主 Agent 自我约束：「当前班组」与「仍可派发」的角色一目了然。
- UI/调试：可在 Debug 或未来 Agents 面板展示「拓扑快照」（RPD 能力管理类面板可渐进接入）。

---

## 4. 与现有代码的映射与缺口

### 4.1 已存在

- `SubagentManager`：`MAX_CONCURRENT`、`MAX_DEPTH`、`spawn`、`kill`、`steer`、`list_active`。
- 工具：`sessions_spawn`（spawn 并等待完成）、`subagents`（list / steer / kill）、`agents_list`（磁盘上的 agent 目录，与「会话内子 Agent 班组」不同概念，需在提示词中区分）。

### 4.2 关键缺口（实现时必须处理）

1. **子 Agent 默认无工具**：`SubagentManager._run_default` 当前 `tools=[]`，与 `SubagentConfig.tools_enabled/disabled` 未贯通。委派「真干活」需要把主会话侧的 `ToolRegistry`（或裁剪子集）注入子 `run_agent`。
2. **`sessions_spawn` 为同步等待**：一次工具调用会阻塞到子 Agent 跑完；若编排要求**并行**多子 Agent，需要要么支持 LLM 单轮多 tool call 并行执行，要么新增「异步 spawn + 后续 join/poll」类工具与状态机（设计推荐在实现计划中二选一）。
3. **Steering 消费**：`steering_instructions` 已入队，需确认 `run_agent` 循环是否**消费**这些指令（若未接线，实现阶段需补全）。
4. **主会话与子会话上下文**：子 Agent 默认 in-memory session；是否需要摘要回灌主会话、或通过 `notify_parent` 写入主会话，需在实现计划中明确。

---

## 5. 错误处理与边界

- **深度与并发**：达到 `MAX_DEPTH` / `MAX_CONCURRENT` 时，工具返回明确错误；主 Agent 应在编排制品中降级为串行或合并角色。
- **Kill**：子 Agent 应返回 `ABORTED`，主 Agent 将结果标记为「已终止」并更新制品状态。
- **失败重试**：由主 Agent 策略决定（换 prompt、换子 Agent、或收缩工具集）；不在本设计强制自动重试。

---

## 6. 测试建议

- **单元**：`SubagentManager` 在 manifest 约束下的 spawn/kill/steer；工具策略裁剪后子 Agent 仅暴露允许的工具。
- **集成**：单主会话多子任务串并行；编排后动态 `retired` 角色不再被派发；kill 后无悬挂事件。
- **契约**：编排制品 JSON schema（版本化）快照测试。

---

## 7. 与文档体系的关系

- [architecture.md](../architecture.md) 中 Agent Runtime、子 Agent 小节可在实现落地后增补「编排制品 + 工具注入」一句指向本文。
- [RPD_CLIENT_DESIGN.md](../RPD_CLIENT_DESIGN.md) 中 Agents / Debug 面板可后续增加「会话内班组拓扑」只读视图（可选）。

---

## 8. 开放决策（实现前需拍板）

1. **并行委派**：优先「单轮多 tool call 并行」还是「async spawn + poll」API？
2. **编排制品存储**：主会话 JSONL 元数据字段 vs 独立 sidecar 文件？
3. **子 Agent 系统提示**：完全由主 Agent 在 spawn 参数中传入，还是结合磁盘 `AGENTS.md` / 按 `agent_id` 加载？

---

## 9. 下一步

使用 **writing-plans** 工作流将 §4–§8 拆为可交付的实现任务（Runner/工具/Manifest 持久化/测试），并按优先级排序。
