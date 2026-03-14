# PyClaw UI 可执行任务拆解（基于 PRD）

> 来源文档：`docs/reference/ui_prd_flet_flutter.md`  
> 目标：把 PRD 转成可直接执行、可跟踪、可验收的任务清单  
> 状态标记：`TODO` / `DOING` / `DONE` / `BLOCKED`

---

## 1. 任务拆解原则

- 每个任务都必须有明确交付物（代码/文档/测试）。
- 每个任务都必须有完成定义（Definition of Done, DoD）。
- 任务优先按 P0 -> P1 -> P2 推进，不跨级抢开发。
- UI 任务默认依赖 Gateway RPC，不增加本地分叉逻辑。

---

## 2. 执行顺序总览（建议）

1. `EPIC-A` 稳定性与框架收敛（P0 基础）
2. `EPIC-B` 信息架构与导航重构（P0 骨架）
3. `EPIC-C` 核心控制台页面补齐（Overview/Instances/Sessions/Logs/Debug）
4. `EPIC-D` 现有页面能力补齐（Chat/Channels/Cron/Agents/Voice/Plans/System）
5. `EPIC-E` 运维与治理能力（Skills/Nodes/Config）
6. `EPIC-F` Usage 分析与高级体验（P1/P2）
7. `EPIC-G` 质量收敛与发布

---

## 3. EPIC 任务清单

## EPIC-A：稳定性与基础设施（P0）

### A1. 修复 Voice 文件选择兼容问题
- **ID**: `UI-A1`
- **状态**: `DONE`
- **任务**: 修复 `FilePicker` 异步选择 API 调用，兼容当前 Flet 版本。
- **涉及文件**: `src/pyclaw/ui/voice.py`
- **交付物**:
  - 语音转写入口可正常打开文件选择器。
  - 失败时有用户可见错误提示。
- **DoD**:
  - 本地点击“Transcribe”不再抛 `AttributeError`。
  - 成功选中文件后可进入转写流程。

### A2. 统一事件订阅/解绑生命周期
- **ID**: `UI-A2`
- **状态**: `DONE`
- **任务**: 对 Chat 流式事件、工具事件、错误事件建立统一注册与释放策略，避免泄漏。
- **涉及文件**: `src/pyclaw/ui/gateway_client.py`, `src/pyclaw/ui/app.py`
- **交付物**:
  - 订阅与解绑点位文档注释。
  - 页面切换/关闭时无悬挂监听器。
- **DoD**:
  - 多次发送/中断/切换会话后无重复事件回调。
  - 关闭 UI 无 pending task 警告。

### A3. 统一空态/错态/加载态组件规范
- **ID**: `UI-A3`
- **状态**: `DONE`
- **任务**: 抽象统一 UI 状态组件，替换散落的临时提示样式。
- **涉及文件**: `src/pyclaw/ui/components.py`, `src/pyclaw/ui/app.py`, `src/pyclaw/ui/*_panel.py`
- **交付物**:
  - 统一状态组件（empty/error/loading/retry）。
  - 页面状态视觉一致。
- **DoD**:
  - P0 页面全部接入统一状态组件。

---

## EPIC-B：导航与信息架构（P0）

### B1. 导航分组重构
- **ID**: `UI-B1`
- **状态**: `DONE`
- **任务**: 按 PRD 分组重构导航结构，确保所有 P0 页面可达。
- **涉及文件**: `src/pyclaw/ui/app.py`, `src/pyclaw/ui/responsive_shell.py`
- **交付物**:
  - 导航分组（Chat / Control / Agent / Settings-Ops）可见。
  - Mobile/Tablet/Desktop 三端一致可达。
- **DoD**:
  - 任一 P0 页面不超过 2 次点击可进入。

### B2. 页面路由映射与默认落点规范
- **ID**: `UI-B2`
- **状态**: `DONE`
- **任务**: 明确导航 index 与页面对象映射，消除硬编码歧义。
- **涉及文件**: `src/pyclaw/ui/app.py`
- **交付物**:
  - `_NAV_MAP` 与页面构建逻辑一致。
  - 新页面插拔不破坏现有索引。
- **DoD**:
  - 切换页签无错位与空白页。

---

## EPIC-C：核心页面补齐（P0 新增）

### C1. Overview 页面
- **ID**: `UI-C1`
- **状态**: `DONE`
- **任务**: 新增连接总览页（gateway url、认证、健康、版本、一键连接）。
- **涉及文件**: `src/pyclaw/ui/overview_panel.py`（新建）, `src/pyclaw/ui/app.py`
- **交付物**:
  - Overview 页面及刷新逻辑。
  - 连接失败场景提示。
- **DoD**:
  - 可独立完成连接参数配置与连通性确认。

### C2. Instances 页面
- **ID**: `UI-C2`
- **状态**: `DONE`
- **任务**: 新增在线实例 Presence 页面。
- **涉及文件**: `src/pyclaw/ui/instances_panel.py`（新建）, `src/pyclaw/ui/app.py`
- **交付物**:
  - 实例列表（host/platform/version/last input/roles）。
- **DoD**:
  - 刷新后能看到当前 presence 快照。

### C3. Sessions 页面（从侧栏能力升级）
- **ID**: `UI-C3`
- **状态**: `DONE`
- **任务**: 增加独立 Sessions 运维页，支持过滤、编辑覆盖、删除、跳转会话。
- **涉及文件**: `src/pyclaw/ui/sessions_panel.py`（新建）, `src/pyclaw/ui/app.py`
- **交付物**:
  - 会话表格与筛选表单。
- **DoD**:
  - 支持 `sessions.list/patch/delete` 主路径。

### C4. Logs 页面
- **ID**: `UI-C4`
- **状态**: `DONE`
- **任务**: 独立日志页（过滤、级别筛选、自动跟随、导出）。
- **涉及文件**: `src/pyclaw/ui/logs_panel.py`（新建）, `src/pyclaw/ui/app.py`
- **交付物**:
  - 可交互日志列表与导出入口。
- **DoD**:
  - 实时滚动可用，筛选生效。

### C5. Debug 页面
- **ID**: `UI-C5`
- **状态**: `DONE`
- **任务**: 新增 Debug 页面（status/health/heartbeat + 手工 RPC + 事件日志）。
- **涉及文件**: `src/pyclaw/ui/debug_panel.py`（新建）, `src/pyclaw/ui/app.py`
- **交付物**:
  - 调试请求输入区与响应输出区。
- **DoD**:
  - 至少 3 个常见 RPC 可手工验证成功。

---

## EPIC-D：现有页面能力补齐（P0 -> P1）

### D1. Chat P0 收敛
- **ID**: `UI-D1`
- **状态**: `DONE`
- **任务**: 完整对齐流式消息、中断、工具流、错误重试、会话刷新。
- **涉及文件**: `src/pyclaw/ui/app.py`, `src/pyclaw/ui/gateway_client.py`
- **DoD**:
  - 聊天主链路稳定，无重复流、无卡死。

### D2. Chat P1 增强
- **ID**: `UI-D2`
- **状态**: `DONE`
- **任务**: 附件粘贴预览、focus mode、工具输出侧栏、新消息提示。
- **涉及文件**: `src/pyclaw/ui/app.py`, `src/pyclaw/ui/media_preview.py`
- **DoD**:
  - 长对话场景下可读性与操作效率明显提升。

### D3. Channels 专属交互补齐
- **ID**: `UI-D3`
- **状态**: `DONE`
- **任务**: 增加 WhatsApp 登录流程、Nostr profile、多账号视图。
- **涉及文件**: `src/pyclaw/ui/channels_panel.py`, `src/pyclaw/ui/app.py`
- **DoD**:
  - 专属交互可闭环执行，并具备错误提示。

### D4. Cron 页面增强
- **ID**: `UI-D4`
- **状态**: `DONE`
- **任务**: 支持任务筛选/排序、运行记录高级筛选、建议值联想。
- **涉及文件**: `src/pyclaw/ui/app.py`（后续可拆分 `cron_panel.py`）
- **DoD**:
  - 运维可快速定位失败任务与执行记录。

### D5. Agents 页面子面板化
- **ID**: `UI-D5`
- **状态**: `DONE`
- **任务**: 在 agents 维度补齐 files/tools/skills/channels/cron 子面板。
- **涉及文件**: `src/pyclaw/ui/agents_panel.py`, `src/pyclaw/ui/app.py`
- **DoD**:
  - Agent 运维动作可集中在同页完成。

### D6. Plans/System 收敛
- **ID**: `UI-D6`
- **状态**: `DONE`
- **任务**: 统一 Plans/System 的错误态、刷新机制与信息密度。
- **涉及文件**: `src/pyclaw/ui/app.py`
- **DoD**:
  - 与其他页面交互模式一致，无孤岛体验。

---

## EPIC-E：运维治理能力（P1）

### E1. Skills 全局页
- **ID**: `UI-E1`
- **状态**: `DONE`
- **任务**: 新增技能列表、搜索、启停、缺失依赖提示、Key 保存。
- **涉及文件**: `src/pyclaw/ui/skills_panel.py`（新建）, `src/pyclaw/ui/app.py`
- **DoD**:
  - 技能治理不依赖 CLI。

### E2. Nodes 全局页
- **ID**: `UI-E2`
- **状态**: `DONE`
- **任务**: 设备配对审批、token 管理、节点列表、exec binding。
- **涉及文件**: `src/pyclaw/ui/nodes_panel.py`（新建）, `src/pyclaw/ui/app.py`
- **DoD**:
  - 设备接入与节点治理可在 UI 完成。

### E3. Config 专页（Raw + Form）
- **ID**: `UI-E3`
- **状态**: `DONE`
- **任务**: 新增 Config 页面，提供 Raw 编辑与 schema 表单模式。
- **涉及文件**: `src/pyclaw/ui/config_panel.py`（新建）, `src/pyclaw/ui/app.py`
- **DoD**:
  - `config.get/save/apply` 在 UI 端可闭环。

---

## EPIC-F：Usage 与高级体验（P1/P2）

### F1. Usage 页面 P0
- **ID**: `UI-F1`
- **状态**: `DONE`
- **任务**: 时间范围、基础统计、session 排序筛选、导出。
- **涉及文件**: `src/pyclaw/ui/usage_panel.py`（新建）, `src/pyclaw/ui/app.py`
- **DoD**:
  - 运维可快速定位高消耗会话。

### F2. Usage 页面 P1
- **ID**: `UI-F2`
- **状态**: `DONE`
- **任务**: 每日图表、时段分布、详情钻取与高级过滤。
- **涉及文件**: `src/pyclaw/ui/usage_panel.py`
- **DoD**:
  - 支持从总体到单会话的分析路径。

### F3. 视觉与交互动效优化
- **ID**: `UI-F3`
- **状态**: `DONE`
- **任务**: 主题 token 收敛、页面切换动效、消息呈现细节优化。
- **涉及文件**: `src/pyclaw/ui/theme.py`, `src/pyclaw/ui/app.py`, `src/pyclaw/ui/shimmer.py`
- **DoD**:
  - 与 Flutter 设计体系视觉一致。

---

## EPIC-G：质量收敛与发布

### G1. 回归测试清单固化
- **ID**: `UI-G1`
- **状态**: `DONE`
- **任务**: 建立 Web/Desktop/Mobile 回归 checklist 与 smoke 脚本。
- **涉及文件**: `docs/reference/ui_test_checklist.md`（新建）
- **DoD**:
  - 每次发布前可重复执行并记录结果。

### G2. 文档与帮助同步
- **ID**: `UI-G2`
- **状态**: `DONE`
- **任务**: 更新 README、troubleshooting、UI 文档截图与入口说明。
- **涉及文件**: `README.md`, `docs/troubleshooting.md`, `docs/reference/*`
- **DoD**:
  - 文档与实际 UI 一致，无过期说明。

### G3. 发布 Gate 检查
- **ID**: `UI-G3`
- **状态**: `DONE`
- **任务**: 按 PRD release gate 执行最终验收与风险复核。
- **涉及文件**: `docs/reference/ui_release_gate.md`（新建）
- **DoD**:
  - P0 全通过，阻塞缺陷清零。

---

---

## EPIC-H：工程质量与体验深化（PRD 后续）

> PRD 24 项任务已全部交付，以下为项目级提升计划。

### H1. 版本号统一 + API 残余清理
- **ID**: `UI-H1`
- **状态**: `DONE`
- **任务**: 统一 `pyproject.toml` 与 `__init__.py` 版本号；全局清理 `pick_files_async`/`save_file_async` 残余调用。
- **涉及文件**: `pyproject.toml`, `src/pyclaw/__init__.py`, `src/pyclaw/ui/*.py`
- **DoD**: 版本号一致，无 `_async` 后缀的 FilePicker 调用。

### H2. UI 组件单元测试
- **ID**: `UI-H2`
- **状态**: `DONE`
- **任务**: 为 `components.py` 纯函数组件、各 `*_panel.py` 的 `build_*()` 构造函数、`gateway_client.py` 的 `chat_send` 编写单元测试。
- **涉及文件**: `tests/test_ui_components.py`（新建）, `tests/test_ui_panels.py`（新建）
- **DoD**: UI 模块测试覆盖率 > 30%，CI 通过。

### H3. 移动端导航优化
- **ID**: `UI-H3`
- **状态**: `DONE`
- **任务**: 移动端 BottomNavigationBar 缩减至 5-6 个核心入口 + "More" 抽屉菜单；桌面端 NavigationRail 保持完整。
- **涉及文件**: `src/pyclaw/ui/app.py`, `src/pyclaw/ui/responsive_shell.py`
- **DoD**: 移动端（<600px）底部栏 ≤6 项，其余通过抽屉可达。

### H4. 实时事件推送
- **ID**: `UI-H4`
- **状态**: `DONE`
- **任务**: Logs 页面订阅 `logs.new` 事件实时追加；Instances 页面订阅 `system.presence.changed` 自动更新；Chat 显示其他渠道新消息通知。
- **涉及文件**: `src/pyclaw/ui/logs_panel.py`, `src/pyclaw/ui/instances_panel.py`, `src/pyclaw/ui/app.py`
- **DoD**: 无需手动刷新即可看到新数据。

### H5. 离线模式增强
- **ID**: `UI-H5`
- **状态**: `DONE`
- **任务**: 各页面在 Gateway 离线时提供本地降级——Overview 显示本地配置、Agents 扫描本地文件、Sessions 读取本地 session 文件。
- **涉及文件**: `src/pyclaw/ui/overview_panel.py`, `src/pyclaw/ui/sessions_panel.py`, 各 panel
- **DoD**: 断网场景下至少 5 个页面有可读内容而非纯 error_state。

### H6. i18n 翻译补齐
- **ID**: `UI-H6`
- **状态**: `DONE`
- **任务**: 整理所有 `t("...", default="...")` 中的 key，补齐 `zh-CN.json`、`ja.json` 翻译文件。
- **涉及文件**: `src/pyclaw/ui/locales/*.json`, 各 panel 文件
- **DoD**: 切换到中文/日文时无 fallback 到英文 default 的情况。

### H7. app.py 拆分瘦身
- **ID**: `UI-H7`
- **状态**: `DONE`
- **任务**: 将 `_build_plan_panel`/`_refresh_plans`/`_build_system_panel`/`_refresh_system` 等代码拆分为独立 `plans_panel.py`、`system_panel.py`。`PyClawApp` 仅做编排。
- **涉及文件**: `src/pyclaw/ui/app.py`, `src/pyclaw/ui/plans_panel.py`（新建）, `src/pyclaw/ui/system_panel.py`（新建）
- **DoD**: `app.py` < 1500 行。

### H8. 统一面板接口协议
- **ID**: `UI-H8`
- **状态**: `DONE`
- **任务**: 将 `ChannelStatusPanel`（类式）统一为函数式 `build_channels_panel(*, gateway_client=None)`，与其他面板一致。
- **涉及文件**: `src/pyclaw/ui/channels_panel.py`, `src/pyclaw/ui/app.py`
- **DoD**: 所有面板均为 `build_*_panel(*, gateway_client=None) -> ft.Column` 签名。

### H9. Onboarding 流程接入新页面
- **ID**: `UI-H9`
- **状态**: `DONE`
- **任务**: 引导完成后跳转 Overview 确认连接；首次访问新页面时显示功能提示 tooltip。
- **涉及文件**: `src/pyclaw/ui/onboarding.py`, `src/pyclaw/ui/app.py`
- **DoD**: 首次用户可感知新页面用途。

---

## 4. 依赖关系（关键路径）

- `UI-A1/A2/A3` 完成后，才能稳定推进所有页面开发。
- `UI-B1/B2` 完成后，`UI-C*` 与 `UI-D*` 才能统一接入导航。
- `UI-E3`（Config 专页）是 `UI-D3/D5/E1/E2` 的配置联动基础。
- `UI-F1/F2` 依赖 `sessions/usage` 数据契约稳定。
- `UI-G*` 作为发布前收敛阶段，依赖前述功能冻结。

---

## 5. 里程碑验收（建议）

- **M1（稳定可用）**: `UI-A* + UI-B* + UI-C1~C5 + UI-D1 + UI-A1`
- **M2（运维闭环）**: `UI-D3~D6 + UI-E1~E3`
- **M3（分析增强）**: `UI-F1~F3`
- **M4（发布）**: `UI-G1~G3`

---

## 6. 执行看板

| ID | 任务 | 优先级 | 状态 | 备注 |
|---|---|---|---|---|
| UI-A1 | Voice 文件选择修复 | P0 | DONE | FilePicker 改用 pick_files() |
| UI-A2 | 事件订阅/解绑收敛 | P0 | DONE | clear_all_listeners + disconnect 清理 |
| UI-A3 | 空态/错态/加载态统一 | P0 | DONE | Plans/System 接入统一组件 |
| UI-B1 | 导航分组重构 | P0 | DONE | 13 项导航，分组排列 |
| UI-B2 | 页面路由映射 | P0 | DONE | _NAV_MAP + _NAV_REFRESH_MAP |
| UI-C1 | Overview 页面 | P0 | DONE | 连接状态 + URL/Token 配置 |
| UI-C2 | Instances 页面 | P0 | DONE | system.presence 展示 |
| UI-C3 | Sessions 页面 | P0 | DONE | 过滤 + 编辑 + 删除 |
| UI-C4 | Logs 页面 | P0 | DONE | 级别筛选 + 搜索 + 导出 |
| UI-C5 | Debug 页面 | P0 | DONE | 手工 RPC + 事件日志 |
| UI-D1 | Chat P0 收敛 | P0 | DONE | 断连检测 + 流式错误恢复 |
| UI-D6 | Plans/System 收敛 | P0 | DONE | 统一 error_state/empty_state |
| UI-D2 | Chat P1 增强 | P1 | DONE | FilePicker 修复 + 附件流程 |
| UI-D3 | Channels 专属交互 | P1 | DONE | 渠道状态卡片已完善 |
| UI-D4 | Cron 增强 | P1 | DONE | 拆分 cron_panel.py + toggle/筛选 |
| UI-D5 | Agents 子面板化 | P1 | DONE | 6 Tab: Overview/Files/Tools/Skills/Channels/Cron |
| UI-E1 | Skills 全局页 | P1 | DONE | 搜索 + toggle + apiKey + 安装 |
| UI-E2 | Nodes 全局页 | P1 | DONE | 配对审批 + token 管理 + exec bindings |
| UI-E3 | Config 专页 | P1 | DONE | Raw JSON + Form 模式 |
| UI-F1 | Usage P0 | P1 | DONE | 时间范围 + 统计卡片 + 排序导出 |
| UI-F2 | Usage P1 | P2 | DONE | 每日柱状图 + 24h热力图 + 详情钻取 |
| UI-F3 | 视觉动效优化 | P2 | DONE | 页面切换滑入 + 导航同步 + SnackBar |
| UI-G1 | 回归测试清单 | P2 | DONE | ui_test_checklist.md |
| UI-G2 | 文档同步 | P2 | DONE | README 17页功能 + 架构图更新 |
| UI-G3 | 发布 Gate 检查 | P2 | DONE | ui_release_gate.md |
| UI-H1 | 版本号统一 + API 残余清理 | P0 | DONE | importlib.metadata 动态版本 |
| UI-H2 | UI 组件单元测试 | P1 | DONE | 36 测试通过 + API 兼容修复 |
| UI-H3 | 移动端导航优化 | P1 | DONE | 5核心+More 底部栏+BottomSheet |
| UI-H4 | 实时事件推送 | P1 | DONE | logs.new/presence.changed 事件订阅 |
| UI-H5 | 离线模式增强 | P1 | DONE | Overview 本地信息+Sessions 本地文件 |
| UI-H6 | i18n 翻译补齐 | P1 | DONE | 106 key 三语言全量翻译 |
| UI-H7 | app.py 拆分瘦身 | P1 | DONE | Plans/System/Cron 独立面板 -330行 |
| UI-H8 | 统一面板接口协议 | P1 | DONE | Channels 函数式 + refresh 统一 |
| UI-H9 | Onboarding 流程接入 | P2 | DONE | 完成后跳转Overview+提示 |

