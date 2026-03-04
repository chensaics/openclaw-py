#!/usr/bin/env bash
set -euo pipefail

# Build the Flet web app (PWA).
#
# Usage:
#   ./scripts/build-web.sh [--port PORT]
#
# Output goes to build/web/. Serve with any HTTP server,
# or use `python -m http.server -d build/web` for local testing.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "Building OpenClaw PWA web app..."

flet build web \
    --project "OpenClaw" \
    --org "ai.openclaw" \
    --description "Multi-channel AI gateway" \
    --product "OpenClaw" \
    --module-name flet_app

echo "Build complete. Output in build/web/"
echo ""
echo "To serve locally:"
echo "  python3 -m http.server -d build/web 8080"
echo "  open http://localhost:8080"
