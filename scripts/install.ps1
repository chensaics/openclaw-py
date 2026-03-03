# pyclaw installer for Windows (PowerShell)
# Usage:
#   irm https://raw.githubusercontent.com/chensaics/openclaw-py/master/scripts/install.ps1 | iex
#
# Options (set env vars before piping):
#   $env:PYCLAW_EXTRAS = "llamacpp"        Install optional dependencies
#   $env:PYCLAW_VERSION = "0.1.0"          Install specific version
#   $env:PYCLAW_FROM_SOURCE = "1"          Install from git source
#
# Or download and run directly:
#   .\install.ps1 -Extras llamacpp -Version 0.1.0 -FromSource

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

# Support env-var overrides for piped execution (irm | iex)
if (-not $Extras -and $env:PYCLAW_EXTRAS) { $Extras = $env:PYCLAW_EXTRAS }
if (-not $Version -and $env:PYCLAW_VERSION) { $Version = $env:PYCLAW_VERSION }
if (-not $FromSource -and $env:PYCLAW_FROM_SOURCE -eq "1") { $FromSource = $true }

Write-Info "pyclaw installer for Windows"

# --- Check Python ---
$python = $null
foreach ($cmd in @("python3.13", "python3.12", "python3", "python", "py")) {
    try {
        $ver = & $cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($ver) {
            $parts = $ver.Split(".")
            $verNum = [int]$parts[0] * 100 + [int]$parts[1]
            if ($verNum -ge 312) {
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

# --- Check installer ---
$installer = "pip"
try {
    $null = Get-Command pipx -ErrorAction Stop
    $installer = "pipx"
    Write-Ok "Found pipx"
} catch {
    try {
        $null = Get-Command uv -ErrorAction Stop
        $installer = "uv"
        Write-Ok "Found uv"
    } catch {
        Write-Info "Using pip (consider installing pipx for isolated environments)"
    }
}

# --- Build spec ---
$spec = "pyclaw"
if ($Version) { $spec = "pyclaw==$Version" }

$tmpDir = $null
if ($FromSource) {
    Write-Info "Installing from source..."
    $tmpDir = Join-Path $env:TEMP "pyclaw-install"
    if (Test-Path $tmpDir) { Remove-Item -Recurse -Force $tmpDir }
    git clone --depth 1 "https://github.com/chensaics/openclaw-py.git" $tmpDir
    $spec = $tmpDir
}

if ($Extras) { $spec = "${spec}[$Extras]" }

# --- Install ---
Write-Info "Installing $spec..."
if ($installer -eq "pipx") {
    pipx install $spec --python $python
} elseif ($installer -eq "uv") {
    uv tool install $spec --python $python
} else {
    & $python -m pip install $spec
}

# --- Verify ---
try {
    $null = Get-Command pyclaw -ErrorAction Stop
    Write-Ok "pyclaw installed successfully!"
    $pyclawVer = pyclaw --version 2>&1
    Write-Info "Version: $pyclawVer"
    Write-Host ""
    Write-Info "Get started:"
    Write-Host "  pyclaw setup --wizard     # Interactive setup"
    Write-Host "  pyclaw gateway            # Start the gateway"
    Write-Host "  pyclaw agent 'Hello!'     # Chat with the agent"
} catch {
    Write-Warn "pyclaw installed but may not be in PATH. Open a new terminal."
    Write-Info "Try: & $python -m pyclaw --help"
}

# Cleanup
if ($FromSource -and $tmpDir -and (Test-Path $tmpDir)) {
    Remove-Item -Recurse -Force $tmpDir
}
