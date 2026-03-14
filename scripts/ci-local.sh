#!/usr/bin/env bash
# 本地检查：ruff + mypy。pytest 由 pre-push 统一执行，避免与 pre-push 重复跑两遍。
set -e

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
[ -n "$ROOT" ] && cd "$ROOT"

echo "=== 1. Ruff format ==="
ruff format --check src tests

echo "=== 2. Ruff check ==="
ruff check src tests

echo "=== 3. Mypy (与 CI typecheck job 一致，建议 Python 3.13) ==="
mypy src/pyclaw

echo "=== 4. Pytest (由 pre-push 或 CI 统一执行，此处跳过避免重复) ==="
echo "    push 时 pre-push 会跑全量测试；CI 会跑带 coverage 的测试。"

echo "=== 全部通过（ruff + mypy），可提交；push 前将跑 pytest）==="
