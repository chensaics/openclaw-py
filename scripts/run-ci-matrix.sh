#!/usr/bin/env bash
# 在多个 Python 版本上运行与 CI 一致的校验（对应 CI matrix: 3.10–3.14）。
# 用于在推送前发现「仅在某版本失败」的问题。
#
# 用法: ./scripts/run-ci-matrix.sh
# 会依次用 python3.10, python3.11, ... 执行 scripts/ci-local.sh（跳过未安装的版本）。

set -e

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
[ -n "$ROOT" ] && cd "$ROOT"

VERSIONS=(3.10 3.11 3.12 3.13 3.14)
FAILED=()
PASSED=()

for v in "${VERSIONS[@]}"; do
  py="python${v}"
  if ! command -v "$py" &>/dev/null; then
    echo "[skip] $py not found"
    continue
  fi
  echo ""
  echo "========== $py =========="
  if PYTHON="$py" ./scripts/ci-local.sh; then
    PASSED+=("$py")
  else
    FAILED+=("$py")
  fi
done

echo ""
echo "========== Matrix 结果 =========="
echo "通过: ${PASSED[*]:-(无)}"
echo "失败: ${FAILED[*]:-(无)}"
if [ ${#FAILED[@]} -gt 0 ]; then
  exit 1
fi
exit 0
