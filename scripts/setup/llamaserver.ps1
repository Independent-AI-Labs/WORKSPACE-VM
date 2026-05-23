<#
.SYNOPSIS
    LlamaServer management script for Windows
    Replaces Makefile.llamaserver + systemd service management

.DESCRIPTION
    Supports multiple build flavors: cpu, vulkan, sycl
    Manages build, clean, install, uninstall, restart, status, logs

.PARAMETER Action
    Required. One of: build, clean, install, uninstall, restart, status, logs, list

.PARAMETER Flavor
    Required for most actions. One of: cpu, vulkan, sycl

.PARAMETER Lines
    Number of log lines to show (default: 50). Only used with 'logs' action.

.EXAMPLE
    .\llamaserver.ps1 -Action build -Flavor cpu
    .\llamaserver.ps1 -Action build -Flavor vulkan
    .\llamaserver.ps1 -Action clean -Flavor sycl
    .\llamaserver.ps1 -Action install -Flavor cpu
    .\llamaserver.ps1 -Action status -Flavor vulkan
    .\llamaserver.ps1 -Action logs -Flavor cpu -Lines 100
    .\llamaserver.ps1 -Action list
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("build", "clean", "install", "uninstall", "restart", "status", "logs", "list")]
    [string]$Action,

    [Parameter(Mandatory = $false)]
    [ValidateSet("cpu", "vulkan", "sycl")]
    [string]$Flavor = "",

    [Parameter(Mandatory = $false)]
    [int]$Lines = 50
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = (Get-Item $ScriptDir).Parent.FullName
$LlamaDir = Join-Path $ProjectRoot "projects\llama.cpp"
$InstallDir = Join-Path $ProjectRoot ".boot-win\llamaserver"
$ServiceName = "llamaserver"

function Get-BuildDir {
    param([string]$flavor)
    return Join-Path $LlamaDir "build-$flavor"
}

function Get-BinaryPath {
    param([string]$flavor)
    $buildDir = Get-BuildDir -flavor $flavor
    return Join-Path $buildDir "bin\Release\llama-server.exe"
}

function Get-ServiceConfigPath {
    return Join-Path $InstallDir "config.json"
}

function Check-Flavor {
    if ([string]::IsNullOrEmpty($Flavor)) {
        Write-Error "Flavor is required. Usage: .\llamaserver.ps1 -Action $Action -Flavor cpu"
        exit 1
    }
}

function Action-Build {
    Check-Flavor
    $binaryPath = Get-BinaryPath -flavor $Flavor
    if (Test-Path $binaryPath) {
        Write-Host "llama.cpp ($Flavor) already built at $binaryPath"
        Write-Host "   (use: .\llamaserver.ps1 -Action clean -Flavor $Flavor to rebuild)"
        return
    }

    Write-Host "Building llama.cpp ($Flavor)..."
    $scriptPath = Join-Path $ScriptDir "build-llama-$Flavor.cmd"
    if (-not (Test-Path $scriptPath)) {
        Write-Error "Build script not found: $scriptPath"
        exit 1
    }

    & $scriptPath
    if ($LASTEXITCODE -ne 0) {
        Write-Error "$Flavor build failed"
        exit 1
    }
    Write-Host "$Flavor build complete" -ForegroundColor Green
}

function Action-Clean {
    Check-Flavor
    $buildDir = Get-BuildDir -flavor $Flavor
    if (Test-Path $buildDir) {
        Remove-Item -Recurse -Force $buildDir
        Write-Host "Cleaned build-$Flavor" -ForegroundColor Green
    } else {
        Write-Host "build-$Flavor does not exist, nothing to clean"
    }
}

function Action-Install {
    Check-Flavor
    $binaryPath = Get-BinaryPath -flavor $Flavor
    if (-not (Test-Path $binaryPath)) {
        Write-Error "Binary not found: $binaryPath"
        Write-Error "Run: .\llamaserver.ps1 -Action build -Flavor $Flavor"
        exit 1
    }

    if (-not (Test-Path $InstallDir)) {
        New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    }

    $flavorDir = Join-Path $InstallDir $Flavor
    if (-not (Test-Path $flavorDir)) {
        New-Item -ItemType Directory -Path $flavorDir -Force | Out-Null
    }

    Copy-Item -Path $binaryPath -Destination (Join-Path $flavorDir "llama-server.exe") -Force

    $configPath = Get-ServiceConfigPath
    $config = @{
        flavor    = $Flavor
        binary    = Join-Path $flavorDir "llama-server.exe"
        installed = (Get-Date).ToString("o")
    } | ConvertTo-Json
    $config | Out-File -FilePath $configPath -Encoding utf8

    Write-Host "llamaserver@$Flavor installed to $flavorDir" -ForegroundColor Green
}

function Action-Uninstall {
    Check-Flavor
    $flavorDir = Join-Path $InstallDir $Flavor

    $svc = Get-Service -Name "$ServiceName-$Flavor" -ErrorAction SilentlyContinue
    if ($svc) {
        Stop-Service -Name "$ServiceName-$Flavor" -Force -ErrorAction SilentlyContinue
        sc.exe delete "$ServiceName-$Flavor" | Out-Null
    }

    if (Test-Path $flavorDir) {
        Remove-Item -Recurse -Force $flavorDir
    }

    Write-Host "llamaserver@$Flavor removed" -ForegroundColor Green
}

function Action-Restart {
    Check-Flavor
    $svc = Get-Service -Name "$ServiceName-$Flavor" -ErrorAction Stop
    Restart-Service -Name "$ServiceName-$Flavor"
    Write-Host "llamaserver@$Flavor restarted" -ForegroundColor Green
}

function Action-Status {
    Check-Flavor
    $svc = Get-Service -Name "$ServiceName-$Flavor" -ErrorAction SilentlyContinue
    if ($svc) {
        Write-Host "Status: $($svc.Status)"
        Write-Host "Name: $($svc.Name)"
        Write-Host "DisplayName: $($svc.DisplayName)"
    } else {
        Write-Host "llamaserver@$Flavor is not installed"
    }
}

function Action-Logs {
    Check-Flavor
    $logFile = Join-Path $InstallDir "$Flavor.log"
    if (Test-Path $logFile) {
        Get-Content -Path $logFile -Tail $Lines
    } else {
        Write-Host "No log file found for llamaserver@$Flavor"
        Write-Host "Expected: $logFile"
    }
}

function Action-List {
    $units = Get-Service -Name "$ServiceName-*" -ErrorAction SilentlyContinue
    if ($units) {
        $units | Format-Table -Property Name, Status, DisplayName -AutoSize
    } else {
        Write-Host "No llamaserver services found"
    }
}

switch ($Action) {
    "build"      { Action-Build }
    "clean"      { Action-Clean }
    "install"    { Action-Install }
    "uninstall"  { Action-Uninstall }
    "restart"    { Action-Restart }
    "status"     { Action-Status }
    "logs"       { Action-Logs }
    "list"       { Action-List }
}
