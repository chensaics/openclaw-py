# reference 目录说明

> 本目录为 openclaw-py 的**参考与规整文档**入口。所有计划、进度、差距、待办、能力矩阵与架构的**唯一信息源**见 [REFERENCE_TABLES.md](REFERENCE_TABLES.md)。

---

## 1. 文档结构（哪里找什么）

| 需求 | 文档 | 章节 |
|------|------|------|
| Phase 列表与进度 | [REFERENCE_TABLES.md](REFERENCE_TABLES.md) | §1 Phase 总览表 |
| 平台 / 渠道能力矩阵 | [REFERENCE_TABLES.md](REFERENCE_TABLES.md) | §2 平台能力矩阵、§3 核心渠道能力矩阵 |
| 按模块的工作包与关键文件 | [REFERENCE_TABLES.md](REFERENCE_TABLES.md) | §4 按模块聚合的工作包 |
| TS vs Python 差距与状态 | [REFERENCE_TABLES.md](REFERENCE_TABLES.md) | §5 差距总览表 |
| 待办与占位、完成情况 | [REFERENCE_TABLES.md](REFERENCE_TABLES.md) | §6 待办与占位表 |
| 代码统计（LOC、测试、通道数） | [REFERENCE_TABLES.md](REFERENCE_TABLES.md) | §7 代码统计 |
| 项目架构与目录树 | [REFERENCE_TABLES.md](REFERENCE_TABLES.md) | §8 架构概览 |
| 平台与 UI 计划（Phase A/B/C、风险、验收、UI 路线图） | [REFERENCE_TABLES.md](REFERENCE_TABLES.md) | §9 平台与 UI 计划摘要 |
| 按领域的差距明细（通道/Agent/Gateway 等） | [REFERENCE_TABLES.md](REFERENCE_TABLES.md) | §10 差距明细（按领域） |
| 专项计划索引 | [REFERENCE_TABLES.md](REFERENCE_TABLES.md) | §11 专项计划索引 |
| 历史文档索引与规整关系 | [REFERENCE_INDEX.md](REFERENCE_INDEX.md) | 文档清单表 |

---

## 2. 规整文档（唯一信息源）

- **[REFERENCE_TABLES.md](REFERENCE_TABLES.md)**  
  计划、进度、差距、待办、能力矩阵、代码统计、架构概览均集中在此，**不再分散到多份文档**。  
  新增或更新上述信息时，只改此文件。

---

## 3. 专项文档（独立主题，不合并入表格）

以下文档为独立方案或专题，保留原文件，与 REFERENCE_TABLES 无重复：

| 文档 | 用途 |
|------|------|
| [python-flet-rewrite-plan.md](python-flet-rewrite-plan.md) | Python + Flet 重写总纲领、架构思想、设计原则、可复用资产、技术选型与阶段路线 |
| [ui_upgrade_plan.md](ui_upgrade_plan.md) | Flet 重构 + Flutter 美化、Gateway Client、Chat/Session/Settings 增强、Phase 1/2 路线 |

---

## 4. 历史/补充文档（仅作明细）

| 文档 | 说明 |
|------|------|
| [PROGRESS.md](PROGRESS.md) | 各 Phase 的「新增文件/说明」细表（总览见 REFERENCE_TABLES §1、§8） |

---

## 5. 使用建议

1. **查进度、差距、待办、能力、架构**：直接打开 [REFERENCE_TABLES.md](REFERENCE_TABLES.md)，按章节查看。
2. **更新上述任何一项**：只修改 REFERENCE_TABLES.md 对应节，避免在其它文档中重复维护。
3. **查专项方案**：从本节「专项文档」或 [REFERENCE_INDEX.md](REFERENCE_INDEX.md) 进入对应文件。
