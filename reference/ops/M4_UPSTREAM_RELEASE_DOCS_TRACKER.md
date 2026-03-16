# M4 上游 release/docs 周期跟踪模板

> 适用里程碑：M4 上游对齐闭环  
> 建议节奏：每周一次（即使“无差距”也需留痕）

## 0) 自动化入口（已实现）

- [x] 已提供命令：`pyclaw ops m4-snapshot`
- [x] 自动追加巡检窗口与本周结论到 tracker 文档

示例：

```bash
pyclaw ops m4-snapshot \
  --window-start 2026-03-08 \
  --window-end 2026-03-15 \
  --summary "无新增P0差距，P1进入排期"
```

## 1) 巡检输入

- 上游仓库：`openclaw/openclaw`
- 上游文档：`docs.openclaw.ai`
- 巡检窗口：`YYYY-MM-DD ~ YYYY-MM-DD`

## 2) 差距评估表

| upstream_ref | area | change_summary | impact | action | owner_type | eta | status |
|---|---|---|---|---|---|---|---|
| release/tag or doc URL | Browser/Skills/Gateway/Channels/UI/Security |  | P0/P1/P2 |  | Agent/UI/Infra/Security | YYYY-MM-DD | backlog/in_progress/done/deferred |

## 3) 本周结论

- 新增 P0：
- 新增 P1：
- 新增 P2：
- 无差距结论（如适用）：

## 4) 执行约束（强制）

- 新增 P0：1 周内进入执行计划。
- 安全相关差距：优先级高于常规功能。
- 状态更新必须同步到 `reference/PROGRESS.md` 与 issue/PR。

## 5) 关联链接

- 上游 release/issues：
- 本项目 issue/PR：
- 证据（测试报告/日志/截图）：
