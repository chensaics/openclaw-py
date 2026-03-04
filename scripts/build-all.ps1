<# 
.SYNOPSIS
    Build OpenClaw for Windows and Web platforms.

.DESCRIPTION
    Builds the Flet application as Windows .exe and/or Web PWA.

.PARAMETER Targets
    Comma-separated build targets. Default: "web,windows"
    Available: web, windows, macos, linux, apk, ipa

.EXAMPLE
    .\scripts\build-all.ps1
    .\scripts\build-all.ps1 -Targets "web,windows"
#>

param(
    [string]$Targets = "web,windows"
)

$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectDir

$FletCommonArgs = @(
    "--project", "OpenClaw",
    "--org", "ai.openclaw",
    "--description", "Multi-channel AI gateway",
    "--product", "OpenClaw",
    "--module-name", "flet_app"
)

$TargetList = $Targets -split ","
$Succeeded = @()
$Failed = @()

foreach ($target in $TargetList) {
    $target = $target.Trim()
    Write-Host ""
    Write-Host "========================================"
    Write-Host "  Building: $target"
    Write-Host "========================================"
    Write-Host ""

    try {
        & flet build $target @FletCommonArgs
        if ($LASTEXITCODE -eq 0) {
            $Succeeded += $target
            Write-Host "[OK] $target build succeeded -> build\$target\"
        } else {
            $Failed += $target
            Write-Host "[FAIL] $target build FAILED"
        }
    }
    catch {
        $Failed += $target
        Write-Host "[FAIL] $target build FAILED: $_"
    }
}

Write-Host ""
Write-Host "========================================"
Write-Host "  Build Summary"
Write-Host "========================================"

if ($Succeeded.Count -gt 0) {
    Write-Host "  Succeeded: $($Succeeded -join ', ')"
}
if ($Failed.Count -gt 0) {
    Write-Host "  Failed:    $($Failed -join ', ')"
    exit 1
}

Write-Host ""
Write-Host "All builds completed. Output in build\<target>\"
