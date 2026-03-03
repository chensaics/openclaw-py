#!/usr/bin/env bash
# pyclaw one-line installer
# Usage: curl -fsSL https://raw.githubusercontent.com/chensaics/openclaw-py/main/scripts/install.sh | bash
# Options:
#   --extras ollama,llamacpp,mlx   Install optional dependencies
#   --version 0.1.0                Install specific version
#   --from-source                  Install from git source

set -euo pipefail

REPO="chensaics/openclaw-py"
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=12
EXTRAS=""
VERSION=""
FROM_SOURCE=false

_info()  { printf '\033[1;34m[info]\033[0m  %s\n' "$*"; }
_ok()    { printf '\033[1;32m[ok]\033[0m    %s\n' "$*"; }
_warn()  { printf '\033[1;33m[warn]\033[0m  %s\n' "$*"; }
_error() { printf '\033[1;31m[error]\033[0m %s\n' "$*"; exit 1; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --extras)   EXTRAS="$2"; shift 2 ;;
        --version)  VERSION="$2"; shift 2 ;;
        --from-source) FROM_SOURCE=true; shift ;;
        *) _warn "Unknown option: $1"; shift ;;
    esac
done

_info "pyclaw installer"

# --- Check Python ---
PYTHON=""
for cmd in python3.13 python3.12 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || true)
        if [[ -n "$ver" ]]; then
            major="${ver%%.*}"
            minor="${ver#*.}"
            ver_num=$((major * 100 + minor))
            min_num=$((MIN_PYTHON_MAJOR * 100 + MIN_PYTHON_MINOR))
            if [[ "$ver_num" -ge "$min_num" ]]; then
                PYTHON="$cmd"
                break
            fi
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    _error "Python >= ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR} is required but not found.
Install it:
  macOS:   brew install python@3.12
  Ubuntu:  sudo apt install python3.12 python3.12-venv
  Fedora:  sudo dnf install python3.12"
fi

_ok "Found $PYTHON ($("$PYTHON" --version 2>&1))"

# --- Check pipx ---
INSTALLER=""
if command -v pipx &>/dev/null; then
    INSTALLER="pipx"
    _ok "Found pipx"
elif command -v uv &>/dev/null; then
    INSTALLER="uv"
    _ok "Found uv"
else
    _info "Installing pipx..."
    "$PYTHON" -m pip install --user pipx 2>/dev/null || "$PYTHON" -m pip install pipx
    "$PYTHON" -m pipx ensurepath 2>/dev/null || true
    if command -v pipx &>/dev/null; then
        INSTALLER="pipx"
    else
        INSTALLER="pip"
        _warn "pipx not found after install, falling back to pip"
    fi
fi

# --- Build install spec ---
if [[ "$FROM_SOURCE" == true ]]; then
    _info "Installing from source..."
    CLONE_DIR=$(mktemp -d)
    git clone --depth 1 "https://github.com/${REPO}.git" "$CLONE_DIR/pyclaw"
    SPEC="$CLONE_DIR/pyclaw"
else
    SPEC="pyclaw"
    if [[ -n "$VERSION" ]]; then
        SPEC="pyclaw==${VERSION}"
    fi
fi

EXTRA_SPEC=""
if [[ -n "$EXTRAS" ]]; then
    IFS=',' read -ra EXTRA_PARTS <<< "$EXTRAS"
    for extra in "${EXTRA_PARTS[@]}"; do
        extra=$(echo "$extra" | tr -d ' ')
        if [[ -n "$EXTRA_SPEC" ]]; then
            EXTRA_SPEC="${EXTRA_SPEC},${extra}"
        else
            EXTRA_SPEC="$extra"
        fi
    done
fi

# --- Install ---
INSTALL_TARGET="$SPEC"
if [[ -n "$EXTRA_SPEC" ]]; then
    INSTALL_TARGET="${SPEC}[${EXTRA_SPEC}]"
fi

if [[ "$INSTALLER" == "pipx" ]]; then
    pipx install "$INSTALL_TARGET" --python "$PYTHON"
elif [[ "$INSTALLER" == "uv" ]]; then
    uv tool install "$INSTALL_TARGET" --python "$PYTHON"
else
    "$PYTHON" -m pip install "$INSTALL_TARGET"
fi

# --- Verify ---
if command -v pyclaw &>/dev/null; then
    _ok "pyclaw installed successfully!"
    _info "Version: $(pyclaw --version 2>/dev/null || echo 'unknown')"
    echo ""
    _info "Get started:"
    echo "  pyclaw setup --wizard     # Interactive setup"
    echo "  pyclaw gateway            # Start the gateway"
    echo "  pyclaw agent 'Hello!'     # Chat with the agent"
else
    _warn "pyclaw installed but not in PATH."
    _info "Try opening a new terminal, or run:"
    echo "  $PYTHON -m pyclaw --help"
fi

# Cleanup
if [[ "$FROM_SOURCE" == true && -d "${CLONE_DIR:-}" ]]; then
    rm -rf "$CLONE_DIR"
fi
