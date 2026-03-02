#!/usr/bin/env bash
set -euo pipefail

# Build the Flet mobile app.
#
# Usage:
#   ./scripts/build-mobile.sh [ios|android]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

TARGET="${1:?Usage: build-mobile.sh [ios|android]}"

echo "Building OpenClaw mobile app for $TARGET..."

cd "$PROJECT_DIR"

flet build "$TARGET" \
    --project "OpenClaw" \
    --org "ai.openclaw" \
    --description "Multi-channel AI gateway" \
    --product "OpenClaw" \
    --module-name flet_app

echo "Build complete. Output in build/$TARGET/"
