#!/usr/bin/env bash
# Generate release notes from git log between two tags (or since last tag).
#
# Usage:
#   ./scripts/generate-release-notes.sh              # since last tag
#   ./scripts/generate-release-notes.sh v0.1.0       # since v0.1.0
#   ./scripts/generate-release-notes.sh v0.1.0 v0.2.0  # between tags

set -euo pipefail

FROM_TAG="${1:-$(git describe --tags --abbrev=0 2>/dev/null || echo "")}"
TO_TAG="${2:-HEAD}"

if [ -z "$FROM_TAG" ]; then
    RANGE="$TO_TAG"
    echo "# Release Notes"
    echo ""
    echo "> All commits up to ${TO_TAG}"
else
    RANGE="${FROM_TAG}..${TO_TAG}"
    echo "# Release Notes (${FROM_TAG} → ${TO_TAG})"
    echo ""
fi

echo ""

declare -A SECTIONS
SECTIONS=(
    ["feat"]="New Features"
    ["fix"]="Bug Fixes"
    ["docs"]="Documentation"
    ["test"]="Tests"
    ["refactor"]="Refactoring"
    ["perf"]="Performance"
    ["ci"]="CI/CD"
    ["chore"]="Chores"
)

CATEGORIES=("feat" "fix" "docs" "test" "refactor" "perf" "ci" "chore")
OTHER_COMMITS=""

for category in "${CATEGORIES[@]}"; do
    commits=$(git log "$RANGE" --pretty=format:"- %s (%h)" --no-merges --grep="^${category}:" --grep="^${category}(" 2>/dev/null || true)
    if [ -n "$commits" ]; then
        echo "## ${SECTIONS[$category]}"
        echo ""
        echo "$commits"
        echo ""
    fi
done

uncategorized=$(git log "$RANGE" --pretty=format:"%s|%h" --no-merges 2>/dev/null | while IFS='|' read -r msg hash; do
    matched=false
    for cat in "${CATEGORIES[@]}"; do
        if echo "$msg" | grep -qE "^${cat}[:(]"; then
            matched=true
            break
        fi
    done
    if [ "$matched" = false ]; then
        echo "- ${msg} (${hash})"
    fi
done)

if [ -n "$uncategorized" ]; then
    echo "## Other Changes"
    echo ""
    echo "$uncategorized"
    echo ""
fi

echo "---"
echo ""
echo "**Full diff**: https://github.com/chensaics/openclaw-py/compare/${FROM_TAG}...${TO_TAG}"
