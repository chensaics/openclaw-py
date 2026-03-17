#!/usr/bin/env bash
# 与 GitHub Actions CI 完全一致的本地校验（lint + typecheck + pytest）。
# 推送前执行此脚本可最大程度避免「本地通过、远端失败」。
#
# 用法:
#   ./scripts/ci-local.sh           # 使用当前 Python
#   PYTHON=python3.10 ./scripts/ci-local.sh
#   ./scripts/ci-local.sh --install # 先 pip install -e ".[dev]" 再跑
#
# 多版本校验（与 CI matrix 一致）:
#   ./scripts/run-ci-matrix.sh

set -e

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
[ -n "$ROOT" ] && cd "$ROOT"

PYTHON="${PYTHON:-python3}"
DO_INSTALL=false
for arg in "$@"; do
  case "$arg" in
    --install) DO_INSTALL=true ;;
  esac
done

echo "=== CI 本地校验（与 .github/workflows/ci.yml 一致）==="
echo "Python: $($PYTHON --version 2>&1)"
echo ""

if [ "$DO_INSTALL" = true ]; then
  echo "=== 安装依赖 (pip install -e \".[dev]\") ==="
  "$PYTHON" -m pip install --upgrade pip -q
  "$PYTHON" -m pip install -e ".[dev]" -q
  echo ""
fi

echo "=== 1. Lint (ruff format + ruff check) ==="
"$PYTHON" -m ruff format --check src tests
"$PYTHON" -m ruff check src tests
echo ""

echo "=== 2. Type check (mypy) ==="
"$PYTHON" -m mypy src/pyclaw
echo ""

echo "=== 3. Tests (与 CI 相同: pytest --cov=pyclaw --cov-report=term-missing --cov-report=xml tests/) ==="
"$PYTHON" -m pytest --cov=pyclaw --cov-report=term-missing --cov-report=xml tests/
echo ""

echo "=== 全部通过（与 CI test job 一致）==="
