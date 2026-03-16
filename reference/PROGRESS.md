# OpenClaw-Py 执行进度（里程碑驱动）

> 最后更新：2026-03-16  
> 项目路径：`/mnt/g/chensai/openclaw-py`  
> 本文定位：**执行视角**（里程碑、看板、风险、退出条件）  
> 决策矩阵与能力对照：见 `reference/REFERENCE_TABLES.md`

---

## 1) 当前状态快照

### 1.1 基线能力（已具备）

- Gateway + WebSocket v3 + OpenAI 兼容 HTTP 已可用。
- Agent 运行时、25+ 通道、MCP、Hooks、Memory、Security、CLI 体系已成型；CLI 主命令为 `pyclaw`。
- Flet 客户端为当前生产主线；`flutter_app` 已具备完整工程骨架与历史页面资产。
- 配置与路径兼容已覆盖 `.pyclaw/.openclaw`、`PYCLAW_*` 与 `OPENCLAW_*`。
- Skills 已支持 `bundled/global/workspace` 多源发现和覆盖优先级。

### 1.2 当前重点转移

- 从“功能堆叠式 phase 记录”转为“可交付里程碑 + 持续运维闭环”。
- 从“单客户端叙事”升级为“**双轨客户端**（Flet 稳定线 + Flutter 增强线）”。
- 从“技能可发现”升级到“技能可运行、可审计、可发布”。

### 1.3 文档治理原则

- `PROGRESS.md` 只回答：现在做什么、做到哪、下一步是什么、何时能收敛。
- 详细矩阵、差距、职责边界、验收指标统一放到 `REFERENCE_TABLES.md`。
- 历史 phase 明细不再在正文重复维护，按附录索引保留.

---

## 2) 里程碑总览（M0-M4）

| 里程碑 | 周期（建议） | 目标 | 进度 | 退出条件（DoD） |
|---|---|---|---|---|
| M0 | 1-2 周 | 文档重建与执行基线统一 | 已完成 | 两份核心文档完成重排，形成执行/决策分工 |
| M1 | 2-4 周 | Skills 运行时契约 + 首批内置技能 | 进行中 | Skill Contract 落地，6-8 个内置技能可运行可测 |
| M2 | 3-6 周 | 双轨客户端打通（Flet 稳定、Flutter 恢复） | 进行中 | Flet/Flutter 共享 Gateway 能力基线并通过回归 |
| M3 | 2-4 周 | 多平台构建发布与质量门禁 | 进行中 | 各目标平台 build 流水线 + 发布检查表稳定执行 |
| M4 | 持续 | 上游 OpenClaw 对齐闭环 | 进行中 | release/docs 差距追踪制度化并可周更 |

---

## 3) M0：文档重建（当前执行）

### 3.1 目标

- 建立“执行文档（PROGRESS）+ 决策文档（REFERENCE_TABLES）”双文档体系。
- 清理历史流水账式结构，让后续研发可按里程碑推进与复盘。

### 3.2 范围

- 重构 `reference/PROGRESS.md`：
  - 里程碑导向、周看板、风险与退出条件。
  - 历史 Phase 移至附录索引，不再正文堆叠。
- 重构 `reference/REFERENCE_TABLES.md`：
  - 能力矩阵、差距矩阵、技能兼容矩阵、双客户端矩阵、发布矩阵、风险矩阵。

### 3.3 风险

- 历史信息压缩后，个别细节追溯成本上升。
- 双轨策略若无明确边界，容易造成重复建设。

### 3.4 退出条件

- 两份文档结构稳定、分工清晰、无重复冲突。
- 每个长期任务具备负责人类型、输入输出、DoD、风险与回滚说明。

---

## 4) M1：Skills 兼容与内置化

### 4.1 目标

- 从“SKILL.md 发现”升级为“运行时契约 + 依赖校验 + 安全分级 + 发布流程”。
- 支持 Python 原生、Node/TS 包装、MCP 桥接三类技能运行路径。

### 4.2 范围

- Skill Runtime Contract（规范层）
  - `spec`：`SKILL.md + frontmatter`
  - `capability`：tools/runtime/deps/security-level
  - `launcher`：Python-native/Node-wrapper/MCP-bridge
- 依赖与环境校验（执行前）
  - 运行时存在性校验（python/node/mcp endpoint）
  - 最小权限校验（workspace、exec allowlist、network policy）
- 首批内置技能包（建议）
  - `repo-review`
  - `docs-sync`
  - `release-helper`
  - `incident-triage`
  - `office-reader`
  - `channel-ops`

### 4.3 风险

- Node/TS 技能直接执行带来进程与安全管理复杂度。
- 技能声明与真实工具权限不一致会导致“可装不可用”。

### 4.4 退出条件

- Skill Contract 被配置/加载/执行链路共同消费。
- 至少 6 个内置技能具备安装、验证、回滚、测试样例。
- 高风险技能全部经过审批策略与审计日志链路。

### 4.5 当前落地进展（2026-03）

- 内置技能目录已统一到仓库根 `skills/`，并通过打包映射到 `pyclaw/bundled_skills`。
- `loader` 已支持 `PYCLAW_BUNDLED_SKILLS` 覆盖与开发态 `skills/` 兜底发现。
- 已新增 `pyclaw skills run <skill_key>` 统一执行入口，覆盖 `repo-review/docs-sync/release-helper/incident-triage/channel-ops/node-toolchain/mcp-admin/office-reader` 路径。
- `pyclaw skills run` 已新增执行前契约门禁：默认阻断缺失依赖与 `userInvocable: false` 技能，返回结构化 `blocking_items`（支持 `ignore_runtime_contract=true` 诊断绕过）。
- M1 技能相关测试已迁移到 `tests/pyclaw/agents/skills` 与 `tests/pyclaw/cli`。
- P0/P1 治理脚手架已补齐：`reference/ops` 周报与审计模板、配置文档契约测试、Provider capability registry 与 browser 生命周期审计命令。

---

## 5) M2：双轨客户端（Flet + Flutter）

### 5.1 目标

- Flet 继续承担稳定生产入口。
- `flutter_app` 从“归档参考”恢复为“增强体验线”，并与 Gateway 能力保持同步。

### 5.2 范围

- Flet 稳定线
  - 保持现有功能完备性与跨平台一致性。
  - 补齐诊断、错误态、权限提示、构建结果可观测。
- Flutter 增强线
  - Stage F0：恢复 Gateway API 同步与核心页面可运行。
  - Stage F1：打包验证（Android/iOS/Desktop/Web）。
  - Stage F2：承接 Flet 不经济的高阶交互能力（例如复杂媒体与动画）。
- `serious-python` 策略
  - 默认不强依赖；
  - 仅在 Flutter 端需“本地嵌入 Python 运行时”场景启用。

### 5.3 风险

- 双轨并行导致协议适配与 QA 成本上升。
- Flutter 线恢复后如缺少最小能力基线，容易与 Flet 行为漂移。

### 5.4 退出条件

- 双端遵循统一能力基线（消息、会话、任务、日志、配置、状态）。
- 双端对同一 Gateway 版本有稳定回归结果与差异清单。

---

## 6) M3：发布工程化与质量门禁

### 6.1 目标

- 将“能构建”升级为“可发布、可回滚、可审计”。

### 6.2 范围

- Flet 多平台打包链路（`web/macos/windows/linux/apk/aab/ipa`）。
- Flutter 多平台打包链路（与 `flet` 产物策略并行但职责分离）。
- GitHub Pages 与文档部署流程治理（构建、发布、回滚）。
- 发布检查表
  - 版本号、签名/证书、权限声明、产物命名、哈希与归档、发布说明。
- 质量门禁
  - 单元/契约/冒烟测试
  - 平台构建成功率
  - 核心 RPC 回归通过率

### 6.3 风险

- iOS/macOS/Android 签名与权限流程复杂，容易阻塞 CI。
- 平台依赖版本漂移（Flutter/Flet/SDK）导致构建不稳定。

### 6.4 退出条件

- 形成可重复执行的“发布流水线 + Gate 清单 + 回滚手册”。
- 最近 3 次版本发布均满足门禁，不依赖人工临时修补。

---

## 7) M4：上游对齐闭环（持续）

### 7.1 目标

- 将 OpenClaw 上游能力跟踪制度化，避免“突击对齐”。

### 7.2 范围

- 周期性追踪：
  - `openclaw/openclaw` release 变化
  - `docs.openclaw.ai` 新增/变更能力
  - 关键安全修复与配置变更
- 差距归档机制
  - 影响评估（P0/P1/P2）
  - 对应改造工单
  - 预计周期与负责人类型

### 7.3 退出条件

- 每周有差距报告快照（即使“无新增差距”也有记录）。
- 新差距在 1 周内进入优先级池并可追踪状态。

---

## 8) 本周 / 下周执行看板

### 8.1 本周（当前）

- [x] 完成长期规划定稿（双轨客户端方向）。
- [x] 启动文档重建（M0）。
- [x] 完成 `PROGRESS.md` 重排（里程碑、看板、DoD、风险）。
- [x] 完成 `REFERENCE_TABLES.md` 重排（六大矩阵）。
- [x] 建立 Skill Contract 草案字段与样例。

### 8.2 下周（计划）

- [x] 产出首批内置技能包候选清单与优先级。
- [x] 明确 Flet/Flutter 双端能力基线与回归清单。
- [x] 整理多平台打包发布 Gate v1（含签名与权限核对表）。
- [x] 建立上游 release/docs 周期跟踪模板。

### 8.3 本轮补齐产物（2026-03-15）

- [x] `reference/ops/M1_BUILTIN_SKILLS_CANDIDATES.md`（首批内置技能候选与 DoD）。
- [x] `reference/ops/M2_CLIENT_BASELINE_CHECKLIST.md`（Flet/Flutter 双端基线与回归清单）。
- [x] `reference/ops/M3_RELEASE_GATE_V1.md`（多平台发布 Gate v1）。
- [x] `reference/ops/M4_UPSTREAM_RELEASE_DOCS_TRACKER.md`（上游 release/docs 周跟踪模板）。
- [x] Skills 运行时桥接：`skills/*/scripts/runtime.py` 骨架 + `pyclaw skills run` 脚本运行路径。
- [x] Skills 运行前契约门禁：依赖缺失阻断、非用户可调用技能阻断、诊断绕过开关与测试补齐。

### 8.4 本轮 Code Review 与修复（2026-03-15）

- 发现并修复：`skills run` 未在执行前强制消费 `runtime_contract` 与调用策略，导致“声明缺依赖但仍可执行”的治理缺口。
- 已修复行为：
  - 缺依赖技能默认返回 `needs_attention` + `missing_dep:*`。
  - `userInvocable: false` 技能默认返回 `invalid`。
  - 保留诊断路径：支持 `ignore_runtime_contract=true`（仅建议诊断场景使用）。
  - `mcp-admin/node-toolchain` 作为探测型技能，保留“依赖缺失仍可运行并给出诊断”的行为。
- 验证结果：`tests/pyclaw/cli/test_skills_run.py`、`tests/pyclaw/agents/skills/test_runtime_contract.py`、`tests/pyclaw/cli/test_browser_audit.py` 目标回归集已通过。

### 8.5 本轮待开发事项清零（2026-03-15）

- [x] M3 发布 Gate 自动化命令：`pyclaw ops release-gate`（版本一致性、产物命名规则、`SHA256SUMS` 生成、报告落盘）。
- [x] M2 基线自动化子集命令：`pyclaw ops m2-baseline`（gateway 可见性、`skills run` 成功与失败结构化链路）。
- [x] M4 周期巡检快照命令：`pyclaw ops m4-snapshot`（周窗口与结论自动留痕到 tracker）。
- [x] 对应 CLI 与测试补齐：`tests/pyclaw/cli/test_ops_cmd.py` 新增覆盖。
- [x] 目标回归集通过：`test_ops_cmd` + `test_skills_run` + `test_runtime_contract` + `test_browser_audit`。

---

## 9) 负责人类型与协作模式

| 领域 | 负责人类型 | 主要产出 |
|---|---|---|
| Skills 兼容 | Agent/Tools Owner | Skill Contract、运行时校验、内置技能 |
| 客户端双轨 | UI Owner（Flet/Flutter） | 双端能力基线、交互一致性、回归报告 |
| 发布工程化 | Release/Infra Owner | CI/CD、签名权限清单、发布与回滚手册 |
| 上游对齐 | Architecture/PM Owner | 差距评估、优先级池、节奏治理 |

---

## 10) 附录：历史明细索引

- Phase 39–43 已完成；历史 phase 级新增文件与长篇进度明细：请以 Git 历史版本中的 `reference/PROGRESS.md` 为准（已转入存档语义）。
- 当前唯一“矩阵化真源”：`reference/REFERENCE_TABLES.md`。

---

## 11) Flet UI/UX 质量升级（本轮落地）

- [x] 连接状态统一：`GatewayClient` 增加 `connecting/reconnecting/connected/offline/error` 生命周期事件，UI 指示器与 Overview 统一消费。
- [x] 修复已复现异常：`overview` 状态刷新路径移除对未挂载控件 `page` 属性的直接访问，避免 `Control must be added to the page first`。
- [x] 聊天流式性能优化：流式阶段轻量文本渲染 + 节流，结束后一次性 markdown 还原。
- [x] 会话语义收敛：会话 `id -> path` 映射缓存，预览/删除优先使用真实 path；本地删除改为精确匹配，避免误删。
- [x] 反馈闭环：`skills/config` 面板操作失败不再静默，统一通过 snackbar 暴露错误与成功反馈。
- [x] 自动化测试扩展：新增 UI 状态与流式测试、UI-Gateway 契约测试、真实 Web smoke E2E（环境开关控制）。
- [x] 长时重连稳定性回归：补充 `GatewayClient` 重连循环恢复测试（多次失败后恢复）。
- [x] CI 门禁升级：新增 `ui-smoke` 作业（UI 变更触发）与 `ui-e2e-nightly` 夜间真实 E2E 作业。

## Phase 54-58 重点修复了...

- **代码质量改进**：
  - 修复了 Ruff 代码检查中发现的所有问题
  - 移除了未使用的局部变量
  - 优化了布尔表达式和字典迭代模式
  - 修正了导入顺序问题

- **UI/UX 改进**：
  - 优化了主题系统和颜色处理逻辑
  - 改进了会话管理 UI 和快速操作栏
  - 修复了消息气泡渲染和布局问题
  - 增强了设置面板的用户体验

- **稳定性提升**：
  - 修复了网关连接指示器的问题
  - 优化了错误处理机制
  - 完善了测试覆盖率
  - 提升了聊天界面性能