#!/usr/bin/env bash
set -euo pipefail

# Build OpenClaw for all supported platforms.
#
# Usage:
#   ./scripts/build-all.sh              # build for current OS + web
#   ./scripts/build-all.sh --targets web,macos,linux,windows
#   ./scripts/build-all.sh --targets apk,ipa
#
# Requirements:
#   - flet >= 0.21 (pip install flet)
#   - For iOS:  macOS + Xcode
#   - For Android: Android SDK + ANDROID_HOME set

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

FLET_COMMON_ARGS=(
    --project "OpenClaw"
    --org "ai.openclaw"
    --description "Multi-channel AI gateway"
    --product "OpenClaw"
    --module-name flet_app
)

TARGETS=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --targets) TARGETS="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: build-all.sh [--targets TARGET1,TARGET2,...]"
            echo ""
            echo "Available targets: web, macos, linux, windows, apk, ipa"
            echo "Default: web + current OS desktop"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

if [ -z "$TARGETS" ]; then
    case "$(uname -s)" in
        Darwin)  TARGETS="web,macos" ;;
        Linux)   TARGETS="web,linux" ;;
        MINGW*|MSYS*|CYGWIN*) TARGETS="web,windows" ;;
        *) TARGETS="web" ;;
    esac
fi

cd "$PROJECT_DIR"

IFS=',' read -ra TARGET_LIST <<< "$TARGETS"

SUCCEEDED=()
FAILED=()

for target in "${TARGET_LIST[@]}"; do
    target="$(echo "$target" | xargs)"
    echo ""
    echo "═══════════════════════════════════════════════"
    echo "  Building: $target"
    echo "═══════════════════════════════════════════════"
    echo ""

    if flet build "$target" "${FLET_COMMON_ARGS[@]}"; then
        SUCCEEDED+=("$target")
        echo "✓ $target build succeeded → build/$target/"
    else
        FAILED+=("$target")
        echo "✗ $target build FAILED"
    fi
done

echo ""
echo "═══════════════════════════════════════════════"
echo "  Build Summary"
echo "═══════════════════════════════════════════════"

if [ ${#SUCCEEDED[@]} -gt 0 ]; then
    echo "  Succeeded: ${SUCCEEDED[*]}"
fi
if [ ${#FAILED[@]} -gt 0 ]; then
    echo "  Failed:    ${FAILED[*]}"
    exit 1
fi

echo ""
echo "All builds completed. Output in build/<target>/"
