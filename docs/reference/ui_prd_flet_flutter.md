# PyClaw UI 产品功能 PRD（Flet + Flutter）

> 版本：v1.0  
> 日期：2026-03-05  
> 适用范围：`pyclaw ui`（Flet 客户端）与 Flutter 设计体系反哺

---

## 1. 背景与目标

本 PRD 目标是基于参考实现 `claw_examples/openclaw/ui` 的成熟功能，定义 `openclaw-py` 的 UI 产品能力范围与开发计划，形成可直接执行的功能蓝图。

本次文档强调：
- 对齐参考实现的核心页面能力（Chat / Channels / Agents / Sessions / Usage / Cron / Skills / Nodes / Config / Debug / Logs）。
- 结合 `pyclaw` 当前 Flet 版本已实现能力，明确差距与优先级。
- 产出不含人日估算的分阶段开发计划与验收标准。

---

## 2. 输入依据

### 2.1 当前项目（openclaw-py）现状依据

- UI 主入口：`src/pyclaw/ui/app.py`
- 核心面板：
  - `src/pyclaw/ui/channels_panel.py`
  - `src/pyclaw/ui/agents_panel.py`
  - `src/pyclaw/ui/voice.py`
  - `src/pyclaw/ui/gateway_client.py`
  - `src/pyclaw/ui/responsive_shell.py`
- 既有规划文档：`docs/reference/ui_upgrade_plan.md`

### 2.2 参考实现（openclaw/ui）依据

- 导航定义：`/mnt/g/chensai/claw_examples/openclaw/ui/src/ui/navigation.ts`
- 主渲染编排：`/mnt/g/chensai/claw_examples/openclaw/ui/src/ui/app-render.ts`
- 关键页面：
  - Chat / Channels / Agents / Sessions / Usage / Cron
  - Overview / Instances / Nodes / Skills / Config / Debug / Logs

---

## 3. 当前问题与改造动因

### 3.1 运行稳定性问题（已观察）

- 语音转写入口异常：`FilePicker` 调用 `pick_files_async` 报 `AttributeError`，导致 STT 功能不可用。
- 退出与重连生命周期存在清理问题：出现 pending task 与引擎视图清理警告。
- UI 异常兜底不足：部分操作失败后仅日志记录，缺少用户可见错误恢复流程。

### 3.2 功能覆盖差距（相对参考实现）

- 当前导航已有：Chat / Agents / Channels / Plans / Cron / Voice / System / Settings。
- 参考实现重点能力尚未完整产品化：
  - Overview（连接与接入态总览）
  - Instances（在线实例与 Presence）
  - Sessions（会话运维页）
  - Usage（用量分析与导出）
  - Skills（全局技能管理）
  - Nodes（设备配对、Exec 绑定、审批）
  - Config（Schema 驱动表单+Raw 双模式）
  - Debug（手工 RPC + 事件日志）
  - Logs（过滤/导出/自动跟随）

---

## 4. 用户角色与核心场景

- 个人开发者：本地调试模型与渠道连接，快速排错。
- 运维/管理员：多渠道状态、定时任务、日志、设备与权限治理。
- Agent 维护者：Agent 文件、工具策略、技能启停、模型路由管理。

核心场景：
- 在一个控制台完成“连通性检查 -> 聊天验证 -> 渠道监控 -> 运维排障”闭环。
- 在不中断在线服务前提下，完成配置变更、技能调整与回滚验证。

---

## 5. 产品范围（In / Out）

### 5.1 In Scope（本 PRD 范围内）

- 基于 Gateway RPC 的统一控制台体验。
- 与参考实现对齐的核心页面能力与主要交互模式。
- Flet 主实现 + Flutter 设计体系（视觉/交互规范）反哺。
- Web/Desktop/Mobile 响应式一致体验。

### 5.2 Out of Scope（本期不做）

- 完全复刻参考项目前端技术栈（Lit/Web Components）实现细节。
- 新建独立 Flutter 客户端双轨维护。
- 与 UI 无关的后端协议重构（仅在 UI 需要范围内补齐）。

---

## 6. 目标信息架构（IA）与导航

建议导航分组如下：

- Chat
  - Chat
- Control
  - Overview
  - Channels
  - Instances
  - Sessions
  - Usage
  - Cron
- Agent
  - Agents
  - Skills
  - Nodes
  - Plans（保留 pyclaw 特色）
- Settings / Ops
  - Config
  - Debug
  - Logs
  - System
  - Voice（可置于工具区或独立页）

说明：
- 保留现有 `Plans` 与 `Voice`，作为 pyclaw 差异化能力。
- `System` 与 `Debug/Logs` 避免重叠：System 偏状态看板，Debug/Logs 偏诊断操作。

---

## 7. 详细功能需求（PRD）

以下使用优先级：
- P0：必须上线能力（稳定可用）。
- P1：高价值增强（首个稳定版本后优先补齐）。
- P2：体验优化与高级能力。

### 7.1 Chat（对齐参考实现核心）

**P0**
- 支持网关流式消息渲染（delta 增量）。
- 支持中断生成（Abort）。
- 支持工具调用流（tool start/end 卡片）。
- 支持会话切换与历史刷新。
- 支持失败提示与重试入口。

**P1**
- 支持图片粘贴/附件预览（与 `media_preview` 联动）。
- 支持焦点模式（Focus mode）。
- 支持工具输出侧边栏与分栏宽度调节。
- 支持“新消息在下方”提醒与一键滚底。

**P2**
- 消息分组与阅读态指示优化。
- 上下文压缩提示、模型 fallback 状态提示。

### 7.2 Overview（新）

**P0**
- 网关连接状态、版本、健康、认证模式展示。
- Gateway URL / Token / Password / Session Key 基础配置。
- 一键连接与刷新。

**P1**
- 连接失败原因智能提示（鉴权/安全上下文/设备配对）。
- 快速跳转到文档或诊断入口。

### 7.3 Channels

**P0**
- 渠道列表状态卡片（configured/running/connected/error）。
- 每渠道基础配置入口（与 config form 联动）。
- 统一刷新与错误态。

**P1**
- 分渠道专属交互：
  - WhatsApp 登录流程（start/wait/logout）
  - Nostr profile 编辑与导入
  - 多账号状态展示
- 渠道健康快照视图（原始 JSON + 结构化摘要）。

### 7.4 Instances（新）

**P0**
- 在线实例列表（host/platform/version/last input）。
- Presence 时间与角色/权限展示。

### 7.5 Sessions

**P0**
- 会话列表与过滤（active window/limit/include flags）。
- 会话标签与参数覆盖（thinking/verbose/reasoning）编辑。
- 删除会话、跳转到 chat session。

**P1**
- 更丰富筛选与批处理。

### 7.6 Usage（新）

**P0**
- 时间范围查询、刷新、基础统计卡片。
- Session 粒度 token/cost 排序与筛选。
- CSV/JSON 导出。

**P1**
- 每日图表、时段分布、会话详情（日志/时序）联动。
- 多维过滤（agent/channel/provider/model/tool/query）。

### 7.7 Cron

**P0**
- 任务列表、启停、删除、手动触发。
- 新建/编辑任务表单（基础校验）。
- 执行记录列表。

**P1**
- 任务查询、排序、状态过滤。
- 运行记录高级筛选（状态/投递状态/范围）。
- 建议值联想（agent/model/timezone/channel/to）。

### 7.8 Agents

**P0**
- Agent 列表、默认 Agent 标识、选择切换。
- Agent 概览（身份、workspace、模型配置）。

**P1**
- 子面板化管理：
  - Files：读取/编辑/保存
  - Tools：profile/allow/deny
  - Skills：按 agent 维度启停
  - Channels/Cron：按 agent 关联视图

### 7.9 Skills（新）

**P0**
- 技能列表与搜索。
- 启停开关、缺失依赖提示。
- API Key 编辑保存。

**P1**
- 技能分组、安装入口与操作消息反馈。

### 7.10 Nodes（新）

**P0**
- 设备配对请求审批（approve/reject）。
- 已配对设备与 token 管理（rotate/revoke）。
- 节点列表展示。

**P1**
- Exec node binding（默认+按 agent）。
- Exec approvals 策略编辑与保存。

### 7.11 Config（新）

**P0**
- Raw JSON 编辑、校验、保存、应用。
- 基础 schema 显示与错误列表。

**P1**
- Form/Raw 双模式切换。
- Schema 驱动分区表单、搜索与标签过滤。
- 配置变更 diff 视图（可选增强）。

### 7.12 Debug（新）

**P0**
- status/health/heartbeat 快照查看。
- 手工 RPC 调用（method + params JSON）。
- 事件日志面板。

### 7.13 Logs（新）

**P0**
- 日志实时列表、关键字过滤、级别过滤。
- 自动跟随（auto-follow）。
- 导出当前可见日志。

### 7.14 Voice（修复与增强）

**P0**
- 修复文件选择 API 兼容问题，保障音频选取可用。
- 明确 TTS/STT 状态反馈与异常提示。

**P1**
- 与 Gateway 语音 RPC 对齐（`tts.*`），减少本地依赖差异。

### 7.15 Plans / System（保留并规范）

**P0**
- Plans：列表/状态/恢复/删除可用且错误处理一致。
- System：`system.info`、`doctor.run`、`backup.export`、`logs.tail` 能力整合。

**P1**
- Plans 详情视图（步骤链路与上下文）。
- System 指标卡与趋势化展示。

---

## 8. 接口与数据契约要求

UI 侧必须优先依赖 Gateway RPC，避免本地直读配置与本地分叉逻辑。

关键 RPC 族：
- `chat.*`
- `channels.*`
- `sessions.*`
- `cron.*`
- `plan.*`
- `agents.*`
- `skills.*`
- `config.*`
- `logs.*`
- `system.*`
- `doctor.*`
- `backup.*`
- `models.*`
- `tools.*`
- `exec.approval.*`（若可用）

事件要求：
- Chat 流式事件、工具事件、错误事件必须统一订阅/解绑机制，避免泄漏。

---

## 9. 体验与设计规范（Flet + Flutter）

### 9.1 设计原则

- 信息密度高但层级清晰（卡片 + 分组 + 明确状态色）。
- 操作可恢复（撤销/重试/确认提示）。
- 异步可感知（loading、progress、skeleton、disabled 态）。

### 9.2 响应式规范

- Desktop：侧边导航 + 会话侧栏 + 主内容三栏。
- Tablet：压缩导航，保留主内容与关键操作。
- Mobile：底部导航，简化高密度控制项。

### 9.3 一致性规范

- 统一空态、错误态、加载态组件。
- 统一状态颜色语义（success/warn/error/info/muted）。
- 表单控件统一校验反馈风格与文案规范。

---

## 10. 非功能需求

- 稳定性：页面切换、断线重连、窗口关闭场景无未清理任务泄漏。
- 性能：首屏可交互、列表滚动、日志刷新满足桌面端顺滑体验。
- 兼容性：Linux/Windows/macOS 及 Web 端行为一致。
- 可观测性：关键操作有可追踪日志与用户可见错误码。
- 国际化：至少 `en` / `zh-CN` 关键页面文案覆盖。

---

## 11. 开发计划（不含人日）

## Phase A：稳定性与基础设施（P0-基础）

交付目标：
- 修复语音文件选择与生命周期清理问题。
- 统一网关连接状态、错误处理、事件订阅解绑框架。
- 建立页面级空态/错态/加载态统一组件。

完成标准：
- 关键崩溃问题关闭，核心路径可连续运行。

## Phase B：控制台骨架对齐（P0-核心页面）

交付目标：
- 导航分组升级：补齐 Overview / Instances / Sessions / Logs / Debug 页面入口。
- Chat/Channels/Cron/Agents 统一到同一交互规范。
- 保留 Plans/Voice/System 并纳入统一信息架构。

完成标准：
- 日常运维闭环可在 UI 内完成（连接、会话、渠道、任务、日志）。

## Phase C：Agent 与运维深水区（P1）

交付目标：
- Agents 子面板（files/tools/skills/channels/cron）。
- Nodes（设备配对、token、exec binding、审批策略）。
- Config Form/Raw 双模与 schema 驱动配置编辑。

完成标准：
- Agent 与节点治理能力达到可替代 CLI 的核心操作覆盖。

## Phase D：分析与高级体验（P1/P2）

交付目标：
- Usage 分析页（筛选、图表、导出、会话级钻取）。
- Chat 高级体验（focus、附件、侧栏工具输出、消息提示优化）。
- System/Plans 详情化与视觉增强。

完成标准：
- 产品从“可用”提升到“高效可运维”。

## Phase E：发布与质量收敛

交付目标：
- 全链路回归测试（Web/Desktop/Mobile）。
- 文档、帮助与故障排查指南同步。
- 版本发布检查与回滚方案演练。

---

## 12. 验收标准（Release Gate）

- 功能完整性：P0 功能全部通过验收用例。
- 稳定性：核心路径（连接、聊天、配置、日志）无阻塞性缺陷。
- 可用性：关键页面有一致的空态/错态/加载态反馈。
- 运维可达性：无需离开 UI 即可完成主要排障动作。
- 文档一致性：用户文档与 UI 实际能力一致。

---

## 13. 风险与缓解

- RPC 兼容差异风险：统一接口适配层 + 明确版本协商策略。
- 多端行为不一致风险：建立 Web/Desktop/Mobile 对照测试清单。
- 页面膨胀风险：按导航分组拆分模块，严格控制单文件复杂度。
- 回归风险：引入关键页面 smoke 测试与事件流回放测试。

---

## 14. 附录：参考功能映射（摘要）

| 参考 openclaw/ui | pyclaw 当前 | 本 PRD 目标 |
|---|---|---|
| chat | 已有（基础流式） | 完整对齐并增强 |
| overview | 缺失 | 新增 |
| channels | 已有（简版） | 增强至专属交互 |
| instances | 缺失 | 新增 |
| sessions | 侧栏+局部能力 | 独立页面化 |
| usage | 缺失 | 新增 |
| cron | 已有（简版） | 增强 |
| agents | 已有（简版） | 子面板化增强 |
| skills | 缺失 | 新增 |
| nodes | 缺失 | 新增 |
| config | settings 局部 | 完整 config 页 |
| debug | 缺失 | 新增 |
| logs | system 局部 | 独立 logs 页 |
| plans | 已有 | 保留并增强 |
| voice | 已有（有缺陷） | 修复并增强 |

