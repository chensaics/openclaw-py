#!/usr/bin/env bash
# 与 GitHub CI 保持一致的本地检查（提交前运行可避免 CI 失败）
set -e

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
[ -n "$ROOT" ] && cd "$ROOT"

echo "=== 1. Ruff format ==="
ruff format --check src tests

echo "=== 2. Ruff check ==="
ruff check src tests

echo "=== 3. Mypy (与 CI typecheck job 一致，建议 Python 3.13) ==="
mypy src/pyclaw

echo "=== 4. Pytest ==="
pytest --cov=pyclaw --cov-report=term-missing tests/

echo "=== 全部通过，与 CI 一致 ==="
