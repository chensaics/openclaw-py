# pyclaw installer for Windows (PowerShell)
# Usage: irm https://raw.githubusercontent.com/chensaics/openclaw-py/main/scripts/install.ps1 | iex

param(
    [string]$Extras = "",
    [string]$Version = "",
    [switch]$FromSource
)

$ErrorActionPreference = "Stop"

function Write-Info  { Write-Host "[info]  $args" -ForegroundColor Blue }
function Write-Ok    { Write-Host "[ok]    $args" -ForegroundColor Green }
function Write-Warn  { Write-Host "[warn]  $args" -ForegroundColor Yellow }
function Write-Err   { Write-Host "[error] $args" -ForegroundColor Red; exit 1 }

Write-Info "pyclaw installer for Windows"

# --- Check Python ---
$python = $null
foreach ($cmd in @("python3.13", "python3.12", "python3", "python", "py")) {
    try {
        $ver = & $cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($ver) {
            $parts = $ver.Split(".")
            if ([int]$parts[0] -ge 3 -and [int]$parts[1] -ge 12) {
                $python = $cmd
                break
            }
        }
    } catch { }
}

if (-not $python) {
    Write-Err "Python >= 3.12 is required. Install from https://python.org/downloads/"
}

$pyver = & $python --version 2>&1
Write-Ok "Found $python ($pyver)"

# --- Build spec ---
$spec = "pyclaw"
if ($Version) { $spec = "pyclaw==$Version" }
if ($FromSource) {
    Write-Info "Installing from source..."
    $tmpDir = Join-Path $env:TEMP "pyclaw-install"
    if (Test-Path $tmpDir) { Remove-Item -Recurse -Force $tmpDir }
    git clone --depth 1 "https://github.com/chensaics/openclaw-py.git" $tmpDir
    $spec = $tmpDir
}

if ($Extras) { $spec = "${spec}[$Extras]" }

# --- Install via pip ---
Write-Info "Installing $spec..."
& $python -m pip install $spec

# --- Verify ---
try {
    $null = Get-Command pyclaw -ErrorAction Stop
    Write-Ok "pyclaw installed successfully!"
    Write-Info "Get started:"
    Write-Host "  pyclaw setup --wizard"
    Write-Host "  pyclaw gateway"
    Write-Host "  pyclaw agent 'Hello!'"
} catch {
    Write-Warn "pyclaw installed but may not be in PATH. Open a new terminal."
}

if ($FromSource -and (Test-Path $tmpDir)) {
    Remove-Item -Recurse -Force $tmpDir
}
