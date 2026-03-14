# UI 发布 Gate 检查文档

> 用于 `pyclaw ui` 发布前的最终验收与风险复核  
> 关联文档：[ui_prd_flet_flutter.md](ui_prd_flet_flutter.md)、[ui_execution_task_breakdown.md](ui_execution_task_breakdown.md)

---

## 1. 发布前提条件

| 条件 | 要求 |
|------|------|
| P0 任务 | 全部 DONE（12/12） |
| P1 任务 | 全部 DONE（8/8） |
| P2 任务 | 全部 DONE（5/5） |
| Linter | 无阻塞错误 |

---

## 2. 功能验收矩阵

| EPIC | 说明 | 状态 |
|------|------|------|
| **A** | 稳定性与基础设施（Voice 修复、事件解绑、统一空态/错态/加载态） | ✅ DONE |
| **B** | 导航与信息架构（17 项分组、路由映射） | ✅ DONE |
| **C** | 核心页面补齐（Overview/Instances/Sessions/Logs/Debug） | ✅ DONE |
| **D** | 现有页面能力补齐（Chat/Channels/Cron/Agents/Plans/System） | ✅ DONE |
| **E** | 运维治理能力（Skills/Nodes/Config） | ✅ DONE |
| **F** | Usage 分析与高级体验 | ✅ DONE（P0/P1） |
| **G** | 质量收敛与发布（回归测试、文档、Release Gate） | 待验收 |

---

## 3. 已知限制与风险

| 风险项 | 说明 |
|--------|------|
| 离线模式降级 | 依赖 Gateway RPC 的页面在离线模式下体验降级，部分功能不可用 |
| FilePicker 跨平台差异 | Flet FilePicker API 在不同平台（Web/Desktop/Mobile）可能行为不一致 |
| Usage 图表依赖 | Usage 页面每日图表、时段分布依赖后端提供 `dailyBreakdown` 数据 |
| 移动端导航压力 | NavigationBar 项目数量较多（17 项），移动端需验证可用性与滚动/折叠表现 |

---

## 4. 发布 Checklist

- [ ] 回归测试通过（参见 [ui_test_checklist.md](ui_test_checklist.md)）
- [ ] PROGRESS.md 已更新
- [ ] README.md UI 段落已同步
- [ ] 构建脚本验证（Web/Desktop/Mobile）
- [ ] 无 TODO/FIXME 在关键路径代码中
