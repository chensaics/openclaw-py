#!/usr/bin/env bash
set -euo pipefail

# Build the Flet desktop app for the current platform.
#
# Usage:
#   ./scripts/build-desktop.sh [macos|linux|windows]
#   ./scripts/build-desktop.sh macos --build-version 1.2.3
#
# Defaults to the current OS if no argument is given.
# Output goes to build/<target>/

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

TARGET="${1:-}"
BUILD_VERSION=""

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        macos|linux|windows) TARGET="$1"; shift ;;
        --build-version) BUILD_VERSION="$2"; shift 2 ;;
        *) shift ;;
    esac
done

if [ -z "$TARGET" ]; then
    case "$(uname -s)" in
        Darwin) TARGET="macos" ;;
        Linux) TARGET="linux" ;;
        MINGW*|MSYS*|CYGWIN*) TARGET="windows" ;;
        *) echo "Unknown OS; specify macos, linux, or windows"; exit 1 ;;
    esac
fi

echo "Building OpenClaw desktop app for $TARGET..."

cd "$PROJECT_DIR"

EXTRA_ARGS=()
if [ -n "$BUILD_VERSION" ]; then
    EXTRA_ARGS+=(--build-version "$BUILD_VERSION")
fi

flet build "$TARGET" \
    --project "OpenClaw" \
    --org "ai.openclaw" \
    --description "Multi-channel AI gateway" \
    --product "OpenClaw" \
    --module-name flet_app \
    "${EXTRA_ARGS[@]}"

echo ""
echo "Build complete. Output in build/$TARGET/"

case "$TARGET" in
    macos)  echo "  → build/macos/OpenClaw.app" ;;
    linux)  echo "  → build/linux/" ;;
    windows) echo "  → build/windows/OpenClaw.exe" ;;
esac
