#!/usr/bin/env bash
# 与 GitHub Actions CI 完全一致的本地校验（lint + typecheck + pytest）。
# 推送前执行此脚本可最大程度避免「本地通过、远端失败」。
#
# 用法:
#   ./scripts/ci-local.sh           # 使用当前 Python
#   PYTHON=python3.10 ./scripts/ci-local.sh
#   ./scripts/ci-local.sh --install # 先 pip install -e ".[dev,ui]" 再跑
#
# 多版本校验（与 CI matrix 一致）:
#   ./scripts/run-ci-matrix.sh

set -e

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
[ -n "$ROOT" ] && cd "$ROOT"
export PYTHONPATH="${ROOT}/src:${PYTHONPATH:-}"

PYTHON="${PYTHON:-python3}"
PYCLAW_CACHE_ROOT="${PYCLAW_CACHE_ROOT:-/tmp/openclaw-py-cache}"
RUFF_CACHE_DIR="${RUFF_CACHE_DIR:-$PYCLAW_CACHE_ROOT/ruff}"
MYPY_CACHE_DIR="${MYPY_CACHE_DIR:-$PYCLAW_CACHE_ROOT/mypy}"
PYTEST_CACHE_DIR="${PYTEST_CACHE_DIR:-$PYCLAW_CACHE_ROOT/pytest}"
export RUFF_CACHE_DIR
export MYPY_CACHE_DIR
export PYTEST_ADDOPTS="-o cache_dir=$PYTEST_CACHE_DIR"
DO_INSTALL=false
for arg in "$@"; do
  case "$arg" in
    --install) DO_INSTALL=true ;;
  esac
done

echo "=== CI 本地校验（与 .github/workflows/ci.yml 一致）==="
echo "Python: $($PYTHON --version 2>&1)"
echo "Cache root: $PYCLAW_CACHE_ROOT"
echo ""

if [ "$DO_INSTALL" = true ]; then
  echo "=== 安装依赖 (pip install -e \".[dev,ui]\") ==="
  "$PYTHON" -m pip install --upgrade pip -q
  "$PYTHON" -m pip install -e ".[dev,ui]" -q
  echo ""
fi

echo "=== 1. Lint (ruff format + ruff check) ==="
rm -rf "$RUFF_CACHE_DIR"
"$PYTHON" -m ruff format --check src tests
"$PYTHON" -m ruff check src tests
echo ""

echo "=== 2. Type check (mypy) ==="
rm -rf "$MYPY_CACHE_DIR"
"$PYTHON" -m mypy src/pyclaw
echo ""

echo "=== 3. Tests (与 CI 相同: pytest --cov=pyclaw --cov-report=term-missing --cov-report=xml tests/) ==="
rm -rf "$PYTEST_CACHE_DIR"
"$PYTHON" -m pytest -o "cache_dir=$PYTEST_CACHE_DIR" --cov=pyclaw --cov-report=term-missing --cov-report=xml tests/
echo ""

echo "=== 全部通过（与 CI test job 一致）==="
 