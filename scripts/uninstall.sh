#!/usr/bin/env bash
# openclaw-py uninstaller
# Usage: curl -fsSL https://raw.githubusercontent.com/chensaics/openclaw-py/master/scripts/uninstall.sh | bash
# Options:
#   --purge     Also remove all data and config (~/.pyclaw)

set -euo pipefail

PURGE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --purge) PURGE=true; shift ;;
        *) shift ;;
    esac
done

_info()  { printf '\033[1;34m[info]\033[0m  %s\n' "$*"; }
_ok()    { printf '\033[1;32m[ok]\033[0m    %s\n' "$*"; }
_warn()  { printf '\033[1;33m[warn]\033[0m  %s\n' "$*"; }
_error() { printf '\033[1;31m[error]\033[0m %s\n' "$*"; }

_info "openclaw-py uninstaller"

# --- Detect how it was installed ---
UNINSTALLED=false

if command -v pipx &>/dev/null && pipx list 2>/dev/null | grep -q "openclaw-py"; then
    _info "Uninstalling via pipx..."
    pipx uninstall openclaw-py
    UNINSTALLED=true
elif command -v uv &>/dev/null && uv tool list 2>/dev/null | grep -q "openclaw-py"; then
    _info "Uninstalling via uv..."
    uv tool uninstall openclaw-py
    UNINSTALLED=true
else
    # Try pip
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            if "$cmd" -m pip show openclaw-py &>/dev/null 2>&1; then
                _info "Uninstalling via pip..."
                "$cmd" -m pip uninstall -y openclaw-py
                UNINSTALLED=true
                break
            fi
        fi
    done
fi

if [[ "$UNINSTALLED" == true ]]; then
    _ok "openclaw-py package removed."
else
    _warn "openclaw-py package not found (may already be uninstalled)."
fi

# --- Purge data ---
if [[ "$PURGE" == true ]]; then
    _info "Removing data and config..."
    DIRS=("$HOME/.pyclaw" "$HOME/.config/pyclaw")
    for d in "${DIRS[@]}"; do
        if [[ -d "$d" ]]; then
            rm -rf "$d"
            _ok "Removed: $d"
        fi
    done
    _ok "All data and config purged."
else
    echo ""
    _info "Data and config in ~/.pyclaw were kept."
    _info "To also remove them, run with --purge:"
    echo "  curl -fsSL https://raw.githubusercontent.com/chensaics/openclaw-py/master/scripts/uninstall.sh | bash -s -- --purge"
fi

echo ""
_ok "Uninstall complete."
