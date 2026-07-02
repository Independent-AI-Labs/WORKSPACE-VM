param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("install", "uninstall", "start", "stop", "status", "set-key", "reinstall")]
    [string]$Action,

    [Parameter(Mandatory = $false)]
    [string]$ApiKey
)

$ErrorActionPreference = "Stop"

$TaskName = "LlamaCpp-CPU-Service"
$TaskPath = "\AMI\"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = (Get-Item (Split-Path -Parent $ScriptDir)).Parent.FullName
$LauncherPath = Join-Path $ScriptDir "start-llama-cpu-service.cmd"
$EnvFile = Join-Path $ProjectRoot ".env"
$LogFile = Join-Path $ProjectRoot ".llama-cpu-service.log"

function Test-Admin {
    return ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Require-Admin {
    if (-not (Test-Admin)) {
        $scriptPath = $MyInvocation.MyCommand.Definition
        Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`" -Action $Action"
        exit
    }
}

function Get-ApiKey {
    if (Test-Path $EnvFile) {
        $line = Get-Content $EnvFile | Where-Object { $_ -match "^LLAMA_API_KEY=" }
        if ($line) {
            return ($line -split "=", 2)[1].Trim().Trim('"').Trim("'")
        }
    }
    return ""
}

function Test-ServerRunning {
    $key = Get-ApiKey
    $headers = @{}
    if ($key) { $headers["Authorization"] = "Bearer $key" }
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8080/health" -Method Get -Headers $headers -TimeoutSec 2 -UseBasicParsing
        return ($r.StatusCode -eq 200)
    } catch {
        try {
            $r = curl.exe -s -max-time 2 "http://localhost:8080/health" 2>$null
            return ($r -match '"ok"')
        } catch {
            return $false
        }
    }
}

function Kill-LlamaProcesses {
    $procs = Get-Process -Name "llama-server" -ErrorAction SilentlyContinue
    if ($procs) {
        foreach ($p in $procs) {
            try {
                taskkill /F /PID $p.Id 2>$null | Out-Null
            } catch {}
        }
        Start-Sleep 2
    }
    $remaining = Get-Process -Name "llama-server" -ErrorAction SilentlyContinue
    if ($remaining) {
        foreach ($p in $remaining) {
            try {
                Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
            } catch {}
        }
    }
}

function Do-Install {
    Require-Admin

    if (-not (Test-Path $LauncherPath)) {
        Write-Error "Launcher not found: $LauncherPath"
        exit 1
    }

    $existing = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -Confirm:$false
    }

    $action = New-ScheduledTaskAction `
        -Execute "powershell.exe" `
        -Argument "-NoProfile -WindowStyle Hidden -Command `"& '$LauncherPath'`"" `
        -WorkingDirectory $ScriptDir

    $triggers = @(
        (New-ScheduledTaskTrigger -AtStartup),
        (New-ScheduledTaskTrigger -AtLogOn)
    )

    Register-ScheduledTask `
        -TaskName $TaskName `
        -TaskPath $TaskPath `
        -Action $action `
        -Trigger $triggers `
        -Settings (New-ScheduledTaskSettingsSet `
            -AllowStartIfOnBatteries `
            -DontStopIfGoingOnBatteries `
            -StartWhenAvailable `
            -RestartCount 3 `
            -RestartInterval (New-TimeSpan -Minutes 1) `
            -ExecutionTimeLimit (New-TimeSpan -Hours 0)
        ) `
        -RunLevel Highest `
        -User "SYSTEM" `
        -Force | Out-Null

    Write-Host "Installed: $TaskPath$TaskName" -ForegroundColor Green
}

function Do-Uninstall {
    Require-Admin

    schtasks /end /tn "$TaskPath$TaskName" 2>$null
    Start-Sleep 2
    Kill-LlamaProcesses

    $task = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction SilentlyContinue
    if ($task) {
        Unregister-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -Confirm:$false
        Write-Host "Uninstalled." -ForegroundColor Green
    } else {
        Write-Host "Not installed." -ForegroundColor Yellow
    }
}

function Do-Start {
    Require-Admin

    if (Test-ServerRunning) {
        Write-Host "Already running." -ForegroundColor Yellow
        return
    }

    Kill-LlamaProcesses
    Start-Sleep 2

    $task = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction SilentlyContinue
    if (-not $task) {
        Write-Error "Not installed. Run: -Action install"
        exit 1
    }

    schtasks /run /tn "$TaskPath$TaskName" 2>&1 | Out-Null
    Write-Host "Starting..."

    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep 2
        if (Test-ServerRunning) {
            Write-Host "Running." -ForegroundColor Green
            return
        }
    }
    Write-Error "Failed to start within 120s"
    exit 1
}

function Do-Stop {
    Require-Admin

    schtasks /end /tn "$TaskPath$TaskName" 2>$null
    Start-Sleep 2
    Kill-LlamaProcesses
    Start-Sleep 2

    $procs = Get-Process -Name "llama-server" -ErrorAction SilentlyContinue
    if ($procs) {
        Write-Host "WARNING: $($procs.Count) process(es) still running" -ForegroundColor Yellow
        $procs | Select-Object Id, StartTime, SessionId
    } else {
        Write-Host "Stopped." -ForegroundColor Green
    }
}

function Do-Status {
    $task = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction SilentlyContinue
    if ($task) {
        $info = Get-ScheduledTaskInfo -TaskName $TaskName -TaskPath $TaskPath
        Write-Host "Task: $TaskPath$TaskName" -ForegroundColor Cyan
        Write-Host "  State: $($task.State)"
        Write-Host "  Last Run: $($info.LastRunTime)"
        Write-Host "  Last Result: $($info.LastTaskResult)"
    } else {
        Write-Host "Task: NOT INSTALLED" -ForegroundColor Yellow
    }

    $procs = Get-Process -Name "llama-server" -ErrorAction SilentlyContinue
    if ($procs) {
        Write-Host "Processes: $($procs.Count) running" -ForegroundColor Green
        $procs | Select-Object Id, StartTime, SessionId
    } else {
        Write-Host "Processes: none" -ForegroundColor Red
    }

    if (Test-ServerRunning) {
        Write-Host "Server: RUNNING" -ForegroundColor Green
        try {
            $r = curl.exe -s -max-time 2 "http://localhost:8080/health" 2>$null
            if ($r -match '"ok"') { Write-Host "Health: OK" -ForegroundColor Green }
        } catch { Write-Host "Health: unreachable" -ForegroundColor Red }
    } else {
        Write-Host "Server: STOPPED or unreachable" -ForegroundColor Red
    }
}

function Do-Reinstall {
    Write-Host "=== Reinstall ===" -ForegroundColor Cyan
    Do-Stop
    Do-Install
    Do-Start
}

function Do-SetKey {
    if (-not $ApiKey) {
        Write-Error "Provide -ApiKey <value>"
        exit 1
    }

    $lines = @()
    if (Test-Path $EnvFile) {
        $lines = Get-Content $EnvFile | Where-Object { $_ -notmatch "^LLAMA_API_KEY=" }
    }
    $lines += "LLAMA_API_KEY=$ApiKey"
    $lines | Out-File -FilePath $EnvFile -Encoding UTF8 -Force

    $acl = Get-Acl $EnvFile
    $acl.SetAccessRuleProtection($true, $false)
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        [System.Security.Principal.WindowsIdentity]::GetCurrent().Name,
        "FullControl", "Allow"
    )
    $acl.AddAccessRule($rule)
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        "SYSTEM", "FullControl", "Allow"
    )
    $acl.AddAccessRule($rule)
    Set-Acl $EnvFile $acl

    Write-Host "API key saved to $EnvFile (ACL restricted)" -ForegroundColor Green
}

switch ($Action) {
    "install"   { Do-Install }
    "uninstall" { Do-Uninstall }
    "start"     { Do-Start }
    "stop"      { Do-Stop }
    "status"    { Do-Status }
    "set-key"   { Do-SetKey }
    "reinstall" { Do-Reinstall }
}
