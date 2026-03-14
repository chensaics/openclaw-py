#!/usr/bin/env bash
set -euo pipefail

# Build the documentation site using MkDocs Material.
#
# Usage:
#   ./scripts/build-docs.sh          # build only
#   ./scripts/build-docs.sh serve    # local preview at http://localhost:8000
#
# Prerequisites:
#   pip install mkdocs-material mkdocs-minify-plugin

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

if ! command -v mkdocs &>/dev/null; then
    echo "mkdocs not found — installing mkdocs-material..."
    pip install mkdocs-material mkdocs-minify-plugin
fi

MKDOCS_CFG="$PROJECT_DIR/docs/mkdocs.yml"

if [ "${1:-}" = "serve" ]; then
    echo "Starting MkDocs dev server..."
    mkdocs serve -f "$MKDOCS_CFG"
else
    echo "Building documentation site..."
    mkdocs build --strict -f "$MKDOCS_CFG"
    echo "Build complete. Output in site/"
    echo ""
    echo "To preview locally:"
    echo "  mkdocs serve -f docs/mkdocs.yml"
    echo "  open http://localhost:8000"
fi
