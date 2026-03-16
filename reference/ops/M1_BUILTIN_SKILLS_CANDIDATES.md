# M1 首批内置技能包候选清单与优先级

> 适用里程碑：M1 Skills 兼容与内置化  
> 维护方式：每周更新一次优先级与验收状态

## 1) 候选池总览

| skill_key | 运行时 | 优先级 | 当前状态 | 主要价值 | 验收负责人类型 |
|---|---|---|---|---|---|
| `repo-review` | python-native | P0 | 已接线 | 代码审查与风险分级 | Agent/Tools Owner |
| `docs-sync` | python-native | P0 | 已接线 | 文档-实现一致性巡检 | Agent/Tools Owner |
| `release-helper` | python-native | P0 | 已接线 | 发布门禁检查与阻塞项汇总 | Release/Infra Owner |
| `incident-triage` | python-native | P1 | 已接线 | 事故分级与处置清单生成 | Agent/Tools Owner |
| `channel-ops` | python-native | P1 | 已接线 | 通道策略与投递健康巡检 | Channel Owner |
| `office-reader` (`pdf/docx/xlsx/pptx`) | python-native | P1 | 已接线 | Office 文档读取统一入口 | Agent/Tools Owner |
| `mcp-admin` | mcp-bridge | P1 | 已接线 | MCP 服务探活与诊断 | Tools/MCP Owner |
| `node-toolchain` | node-wrapper | P2 | 已接线 | Node 生态技能桥接与依赖探测 | Tools Owner |
| `social` | python-native | P2 | 已接线 | 代理社交网络接入 | Agent Owner |
| `claw-redbook-auto` | python-native | P1 | 已接线 | 小红书运营与自动化能力融合 | Agent/Channel Owner |

## 2) 统一验收门禁（DoD）

- `spec`：`SKILL.md` frontmatter 字段完整且与运行时一致。
- `run`：`pyclaw skills run <skill_key>` 能返回结构化结果。
- `script-runtime`：存在 `scripts/runtime.py` 骨架并可执行（可先返回占位结果）。
- `install`：支持本地安装与 URL 安装；无路径穿越与 SSRF 风险。
- `rollback`：文档声明回滚策略，执行失败时可退回只读/降级模式。
- `test`：至少包含 1 条 CLI 或 runner 路径回归测试（可逐步补齐）。

## 3) 本轮完成情况（2026-03-15）

- 已建立统一 `skills/*/scripts/runtime.py` 入口骨架。
- 已完成 `pyclaw skills run` 的脚本运行时桥接（含回退策略）。
- 已打通 skills 安装链路（URL bundle + clawhub CLI fallback）。
- 已补充安装安全基线（SSRF 拦截、路径安全校验、响应体上限）。

## 4) 下一步（M1 收口）

1. 为 `repo-review/docs-sync/release-helper/channel-ops` 补充最小测试夹具（P0）。
2. 补齐 `node-toolchain/mcp-admin` 的审批与网络策略校验（P1）。
3. 把 `claw-redbook-auto` 从骨架升级为真实执行闭环（auth/search/detail）。
