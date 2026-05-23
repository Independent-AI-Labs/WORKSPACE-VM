<#
.SYNOPSIS
    Stop a running MTP llama-server instance
.PARAMETER BuildDir
    Build directory (cpu or sycl). Default: cpu
.PARAMETER SpecDraftNMax
    Max draft tokens (1-3). Default: 2
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [ValidateSet("cpu", "sycl")]
    [string]$BuildDir = "cpu",

    [Parameter(Mandatory = $false)]
    [int]$SpecDraftNMax = 2
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = (Get-Item (Split-Path -Parent $ScriptDir)).Parent.FullName
$PidFile = Join-Path $ProjectRoot ".mtp-server-${BuildDir}-nmax${SpecDraftNMax}.pid"
$LogFile = Join-Path $ProjectRoot ".mtp-server-${BuildDir}-nmax${SpecDraftNMax}.log"

if (-not (Test-Path $PidFile)) {
    Write-Host "No PID file found for $BuildDir n-max=$SpecDraftNMax"
    exit 0
}

$serverPid = Get-Content $PidFile
$proc = Get-Process -Id $serverPid -ErrorAction SilentlyContinue

if ($proc) {
    Write-Host "Stopping llama-server (PID: $serverPid)..."
    Stop-Process -Id $serverPid -Force
    Start-Sleep 2
    $stillRunning = Get-Process -Id $serverPid -ErrorAction SilentlyContinue
    if ($stillRunning) {
        Write-Host "Process still running, forcing..."
        Stop-Process -Id $serverPid -Force
    }
    Write-Host "Stopped" -ForegroundColor Green
} else {
    Write-Host "Process $serverPid not found (already stopped)"
}

Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
Remove-Item $LogFile -Force -ErrorAction SilentlyContinue
