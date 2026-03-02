#!/usr/bin/env bash
set -euo pipefail

# Build the Flet desktop app for the current platform.
#
# Usage:
#   ./scripts/build-desktop.sh [macos|linux|windows]
#
# Defaults to the current OS if no argument is given.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

TARGET="${1:-}"
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

flet build "$TARGET" \
    --project "OpenClaw" \
    --org "ai.openclaw" \
    --description "Multi-channel AI gateway" \
    --product "OpenClaw" \
    --module-name flet_app

echo "Build complete. Output in build/$TARGET/"
