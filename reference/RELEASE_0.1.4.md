# OpenClaw-Py v0.1.4 发布说明

**发布日期**: 2026-03-15

## 概述

本版本以 **测试与发版流程简化** 为主：减少 pre-push 与 release 的重复测试、缩短两个长时间 sleep 的测试、提供可版本控制的 pre-push 钩子，并统一“本地只跑一次 pytest”的策略。

## 主要变更

### 新增
- **可版本控制的 pre-push 钩子**：`scripts/githooks/pre-push`，推送 tag 时跳过本地测试（由 release workflow 执行）
- `scripts/githooks/README.md`：钩子安装说明

### 变更
- **pre-push**：仅对**分支**推送跑全量 pytest；**推送 tag** 时跳过，避免与 release 的 preflight 重复跑两遍
- **ci-local.sh**：不再跑 pytest，只做 ruff + mypy；pytest 由 pre-push 统一执行，避免与 pre-push 重复
- **commit.sh**：提示改为“本地检查（ruff + mypy）”

### 修复
- **测试耗时**：`test_infra_misc.test_with_timeout_expired`、`test_cron_tts_logging.test_timeout` 中 `asyncio.sleep(10)` 改为满足断言的最小时长（0.1s / 0.2s），pre-push 全量测试减少约 20 秒

## 安装

```bash
pip install openclaw-py==0.1.4
```

## 链接

- [变更列表 (v0.1.3...v0.1.4)](https://github.com/chensaics/openclaw-py/compare/v0.1.3...v0.1.4)
- [CHANGELOG 全文](../CHANGELOG.md)
