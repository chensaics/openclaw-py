#!/usr/bin/env bash
set -euo pipefail

# Build the Flet mobile app.
#
# Usage:
#   ./scripts/build-mobile.sh apk              # Android APK
#   ./scripts/build-mobile.sh aab              # Android App Bundle (Play Store)
#   ./scripts/build-mobile.sh ipa              # iOS IPA (requires macOS + Xcode)
#   ./scripts/build-mobile.sh apk --build-version 1.2.3
#
# Prerequisites:
#   - apk/aab: Android SDK installed, ANDROID_HOME set
#   - ipa: macOS with Xcode, Apple Developer account configured

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

TARGET="${1:?Usage: build-mobile.sh <apk|aab|ipa> [--build-version VERSION]}"
shift

BUILD_VERSION=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --build-version) BUILD_VERSION="$2"; shift 2 ;;
        *) shift ;;
    esac
done

echo "Building OpenClaw mobile app for $TARGET..."

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
    apk) echo "  → build/apk/OpenClaw.apk"
         echo "  Install: adb install build/apk/OpenClaw.apk" ;;
    aab) echo "  → build/aab/OpenClaw.aab"
         echo "  Upload to Google Play Console" ;;
    ipa) echo "  → build/ipa/OpenClaw.ipa"
         echo "  Upload via Xcode Organizer or Transporter" ;;
esac
