<#
.SYNOPSIS
    Uninstall openclaw-py.

.DESCRIPTION
    Detects how openclaw-py was installed (pipx/uv/pip) and removes it.
    With -Purge, also removes all data and config.

.PARAMETER Purge
    Remove all data and config (~/.pyclaw) in addition to the package.

.EXAMPLE
    irm https://raw.githubusercontent.com/chensaics/openclaw-py/master/scripts/uninstall.ps1 | iex

.EXAMPLE
    .\uninstall.ps1 -Purge
#>

param(
    [switch]$Purge
)

$ErrorActionPreference = "Stop"

# Support env-var override for piped execution (irm | iex)
if (-not $Purge -and $env:PYCLAW_PURGE -eq "1") { $Purge = $true }

function Write-Info  { Write-Host "[info]  $args" -ForegroundColor Blue }
function Write-Ok    { Write-Host "[ok]    $args" -ForegroundColor Green }
function Write-Warn  { Write-Host "[warn]  $args" -ForegroundColor Yellow }

Write-Info "openclaw-py uninstaller"

$uninstalled = $false

# --- Detect installer ---
try {
    $null = Get-Command pipx -ErrorAction Stop
    $pipxList = pipx list 2>&1 | Out-String
    if ($pipxList -match "openclaw-py") {
        Write-Info "Uninstalling via pipx..."
        pipx uninstall openclaw-py
        $uninstalled = $true
    }
} catch { }

if (-not $uninstalled) {
    try {
        $null = Get-Command uv -ErrorAction Stop
        $uvList = uv tool list 2>&1 | Out-String
        if ($uvList -match "openclaw-py") {
            Write-Info "Uninstalling via uv..."
            uv tool uninstall openclaw-py
            $uninstalled = $true
        }
    } catch { }
}

if (-not $uninstalled) {
    foreach ($cmd in @("python3", "python", "py")) {
        try {
            $pipShow = & $cmd -m pip show openclaw-py 2>&1 | Out-String
            if ($pipShow -match "Name: openclaw-py") {
                Write-Info "Uninstalling via pip..."
                & $cmd -m pip uninstall -y openclaw-py
                $uninstalled = $true
                break
            }
        } catch { }
    }
}

if ($uninstalled) {
    Write-Ok "openclaw-py package removed."
} else {
    Write-Warn "openclaw-py package not found (may already be uninstalled)."
}

# --- Purge data ---
if ($Purge) {
    Write-Info "Removing data and config..."
    $dirs = @(
        (Join-Path $env:USERPROFILE ".pyclaw"),
        (Join-Path $env:APPDATA "pyclaw")
    )
    foreach ($d in $dirs) {
        if (Test-Path $d) {
            Remove-Item -Recurse -Force $d
            Write-Ok "Removed: $d"
        }
    }
    Write-Ok "All data and config purged."
} else {
    Write-Host ""
    Write-Info "Data and config were kept."
    Write-Info "To also remove them, run with -Purge:"
    Write-Host "  .\uninstall.ps1 -Purge"
}

Write-Host ""
Write-Ok "Uninstall complete."
