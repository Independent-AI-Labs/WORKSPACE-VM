<#
.SYNOPSIS
    Start llama-server in background with MTP speculative decoding
.DESCRIPTION
    Starts llama-server as a background process, waits for health check,
    and writes PID to a file for later management.
.PARAMETER Model
    Path to GGUF model file
.PARAMETER SpecDraftNMax
    Max draft tokens (1-3). Default: 2
.PARAMETER Port
    Server port. Default: 8080
.PARAMETER Threads
    CPU threads. Default: 16
.PARAMETER Ngl
    GPU layers. Default: 0 (CPU only)
.PARAMETER CtxSize
    Context size. Default: 4096
.PARAMETER BuildDir
    Build directory (cpu or sycl). Default: cpu
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Model,

    [Parameter(Mandatory = $false)]
    [int]$SpecDraftNMax = 2,

    [Parameter(Mandatory = $false)]
    [int]$Port = 8080,

    [Parameter(Mandatory = $false)]
    [int]$Threads = 16,

    [Parameter(Mandatory = $false)]
    [int]$Ngl = 0,

    [Parameter(Mandatory = $false)]
    [int]$Ngld = -1,

    [Parameter(Mandatory = $false)]
    [switch]$AutoFit,

    [Parameter(Mandatory = $false)]
    [int]$CtxSize = 4096,

    [Parameter(Mandatory = $false)]
    [ValidateSet("cpu", "sycl")]
    [string]$BuildDir = "cpu",

    [Parameter(Mandatory = $false)]
    [switch]$NoWait
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = (Get-Item (Split-Path -Parent $ScriptDir)).Parent.FullName
$LlamaDir = Join-Path $ProjectRoot "projects\llama.cpp"
$ServerExe = Join-Path $LlamaDir "build-$BuildDir\bin\Release\llama-server.exe"
if (-not (Test-Path $ServerExe)) {
    $ServerExe = Join-Path $LlamaDir "build-$BuildDir\bin\llama-server.exe"
}
$PidFile = Join-Path $ProjectRoot ".mtp-server-${BuildDir}-nmax${SpecDraftNMax}.pid"
$LogFile = Join-Path $ProjectRoot ".mtp-server-${BuildDir}-nmax${SpecDraftNMax}.log"

if (-not (Test-Path $ServerExe)) {
    Write-Error "Server binary not found: $ServerExe"
    exit 1
}

if (-not (Test-Path $Model)) {
    Write-Error "Model not found: $Model"
    exit 1
}

if (Test-Path $PidFile) {
    $oldPid = Get-Content $PidFile
    $proc = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
    if ($proc -and $proc.ProcessName -eq "llama-server") {
        Write-Host "Server already running (PID: $oldPid, port: $Port)"
        Write-Host "Stop it first: Stop-Process -Id $oldPid"
        exit 0
    }
    Remove-Item $PidFile -Force
}

$args = @(
    "-m", $Model
    "--port", "$Port"
    "--spec-type", "draft-mtp"
    "--spec-draft-n-max", "$SpecDraftNMax"
    "-t", "$Threads"
    "-ngl", "$Ngl"
    "-c", "$CtxSize"
    "--log-disable"
)

if ($Ngld -ge 0) {
    $args += @("-ngld", "$Ngld")
}

Write-Host "Starting llama-server ($BuildDir) with MTP n-max=$SpecDraftNMax..."
Write-Host "  Model: $Model"
Write-Host "  Port: $Port"
$nglStr = "NGL: $Ngl"
if ($Ngld -ge 0) { $nglStr += ", NGLD: $Ngld" }
Write-Host "  Threads: $Threads, $nglStr, Ctx: $CtxSize"

$batFile = Join-Path $env:TEMP "start-llama-${BuildDir}-nmax${SpecDraftNMax}.bat"
$argStr = ($args -join " ")
if ($AutoFit) {
    $argStr += " -fit on"
}
if ($BuildDir -eq "sycl") {
    $batContent = "@echo off`ncall `"C:\Program Files (x86)\Intel\oneAPI\setvars.bat`" intel64 --force >nul 2>&1`n`"$ServerExe`" $argStr 2>>`"$LogFile`""
} else {
    $batContent = "@echo off`n`"$ServerExe`" $argStr 2>>`"$LogFile`""
}
$batContent | Out-File -FilePath $batFile -Encoding ASCII -Force

$wshell = New-Object -ComObject WScript.Shell
$wshell.Run("cmd /c `"$batFile`"", 0, $false)
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($wshell) | Out-Null

Start-Sleep 20
$proc = Get-Process -Name "llama-server" -ErrorAction SilentlyContinue | Sort-Object StartTime -Descending | Select-Object -First 1
if (-not $proc) {
    Write-Error "Server process not found after start"
    exit 1
}

Write-Host "PID: $($proc.Id)"
$proc.Id | Out-File -FilePath $PidFile -Encoding ASCII

if ($NoWait) {
    Write-Host "Server starting in background. Health check: curl.exe -s http://localhost:$Port/health"
    exit 0
}

Write-Host "Waiting for server..."
for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep 2
    try {
        $r = curl.exe -s --max-time 2 "http://localhost:$Port/health" 2>$null
        if ($r -match '"ok"') {
            Write-Host "Server ready after $(($i + 1) * 2)s (PID: $($proc.Id))" -ForegroundColor Green
            exit 0
        }
    } catch {}
}

Write-Error "Server failed to start within 180s"
exit 1
