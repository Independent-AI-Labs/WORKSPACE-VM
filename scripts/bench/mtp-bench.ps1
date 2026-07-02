#!/usr/bin/env pwsh
# MTP Benchmark Script for llama.cpp (Windows)
# llama-bench for baselines, llama-server API for MTP
param(
    [string]$ModelDir = "$PSScriptRoot\..\..\projects\llama.cpp\models",
    [string]$BenchExe = "$PSScriptRoot\..\..\projects\llama.cpp\build-cpu\bin\Release\llama-bench.exe",
    [string]$ServerExe = "$PSScriptRoot\..\..\projects\llama.cpp\build-cpu\bin\Release\llama-server.exe",
    [string]$SyclBenchExe = "$PSScriptRoot\..\..\projects\llama.cpp\build-sycl\bin\Release\llama-bench.exe",
    [string]$SyclServerExe = "$PSScriptRoot\..\..\projects\llama.cpp\build-sycl\bin\Release\llama-server.exe",
    [string]$OutputDir = "$PSScriptRoot\..\results",
    [int]$Threads = 16,
    [int]$Reps = 3,
    [switch]$SkipSycl,
    [switch]$SkipCpu,
    [string]$Models = "all",
    [string]$Sizes = "512,128 1024,128",
    [string]$MtpConfigs = "none 2 3"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $OutputDir)) { New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null }

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$csvFile = Join-Path $OutputDir "mtp-bench-$timestamp.csv"

$modelList = if ($Models -eq "all") {
    @("Qwen3.6-35B-A3B-Q4_K_M.gguf", "Qwen3.6-35B-A3B-UD-IQ2_M.gguf", "Qwen3.6-35B-A3B-MTP-Q8_0.gguf")
} else { $Models -split "," }

$sizeList = @()
foreach ($s in $Sizes -split " ") { $p = $s -split ","; $sizeList += [PSCustomObject]@{ pp = [int]$p[0]; tg = [int]$p[1] } }
$mtpList = $MtpConfigs -split " "

"backend,model,pp,tg,spec_type,spec_n_max,threads,ngl,pp_t_s,tg_t_s,timestamp" | Out-File $csvFile -Encoding utf8

function Stop-Server { Get-Process llama-server -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue; Start-Sleep 2 }

function Start-Server {
    param([string]$Exe, [string]$Model, [int]$Ngl, [string]$SpecType, [int]$SpecNmax, [int]$Port)
    $args = @("-m", $Model, "-port", "$Port", "-t", "$Threads", "-ngl", "$Ngl", "-c", "4096", "-log-disable")
    if ($SpecType -ne "none") { $args += @("-spec-type", $SpecType, "-spec-draft-n-max", "$SpecNmax") }
    Start-Process $Exe -ArgumentList $args -NoNewWindow -RedirectStandardError "$env:TEMP\llama-srv-$Port.log"
    for ($i = 0; $i -lt 90; $i++) {
        try { $r = Invoke-WebRequest "http://localhost:$Port/health" -TimeoutSec 2 -UseBasicParsing; if ($r.StatusCode -eq 200) { return $true } } catch {}
        Start-Sleep 1
    }
    return $false
}

function Bench-Server {
    param([int]$Port, [int]$Pp, [int]$Tg, [int]$Reps)
    $ppMs = @(); $tgMs = @()
    for ($i = 0; $i -lt $Reps; $i++) {
        $body = @{ prompt = "Hello"; n_predict = $Tg; cache_prompt = $true } | ConvertTo-Json -Compress
        try {
            $r = Invoke-WebRequest "http://localhost:$Port/completion" -Method POST -Body $body -ContentType "application/json" -TimeoutSec 300 -UseBasicParsing
            $j = $r.Content | ConvertFrom-Json
            if ($j.timings) { $ppMs += $j.timings.prompt_ms; $tgMs += $j.timings.predicted_ms }
        } catch {}
    }
    if ($ppMs.Count -gt 0 -and $tgMs.Count -gt 0) {
        $aP = ($ppMs | Measure-Object -Average).Average; $aT = ($tgMs | Measure-Object -Average).Average
        return [PSCustomObject]@{ pp = [math]::Round(($Pp / $aP) * 1000, 2); tg = [math]::Round(($Tg / $aT) * 1000, 2) }
    }
    return $null
}

function Parse-BenchCsv {
    param([string[]]$Lines)
    $pp = 0; $tg = 0
    foreach ($line in $Lines) {
        if ($line -notmatch "^#") {
            $cols = $line -split ","
            $nPrompt = [int]$cols[33]; $nGen = [int]$cols[34]; $ts = [double]$cols[39]
            if ($nPrompt -gt 0 -and $nGen -eq 0) { $pp = $ts }
            if ($nPrompt -eq 0 -and $nGen -gt 0) { $tg = $ts }
        }
    }
    if ($pp -gt 0 -and $tg -gt 0) { return [PSCustomObject]@{ pp = $pp; tg = $tg } }
    return $null
}

$totalTests = $modelList.Count * $sizeList.Count * $mtpList.Count * 2
$currentTest = 0; $port = 8080

foreach ($model in $modelList) {
    $modelPath = Join-Path $ModelDir $model
    if (-not (Test-Path $modelPath)) { Write-Host "SKIP: $model"; continue }
    $szGB = [math]::Round((Get-Item $modelPath).Length / 1GB, 2)
    Write-Host "Model: $model ($szGB GB)" -ForegroundColor White

    foreach ($size in $sizeList) {
        foreach ($mtp in $mtpList) {
            $specLabel = if ($mtp -eq "none") { "none" } else { "draft-mtp" }
            $specNmax = if ($mtp -eq "none") { 0 } else { [int]$mtp }

            if (-not $SkipCpu) {
                $currentTest++
                Write-Host "  [$currentTest/$totalTests] CPU  pp=$($size.pp) tg=$($size.tg) spec=$specLabel" -NoNewline
                if ($mtp -eq "none") {
                    $raw = & $BenchExe -m $modelPath -p $size.pp -n $size.tg -t $Threads -ngl 0 -r $Reps -o csv 2>$null
                    $r = Parse-BenchCsv $raw
                    if ($r) { "cpu,$model,$($size.pp),$($size.tg),none,0,$Threads,0,$($r.pp),$($r.tg),$timestamp" | Out-File $csvFile -Append -Encoding utf8; Write-Host " pp=$($r.pp) tg=$($r.tg)" -ForegroundColor Green }
                    else { Write-Host " FAIL" -ForegroundColor Red }
                } else {
                    Stop-Server
                    if (Start-Server $ServerExe $modelPath 0 $specLabel $specNmax $port) {
                        $r = Bench-Server $port $size.pp $size.tg $Reps; Stop-Server
                        if ($r) { "cpu,$model,$($size.pp),$($size.tg),$specLabel,$specNmax,$Threads,0,$($r.pp),$($r.tg),$timestamp" | Out-File $csvFile -Append -Encoding utf8; Write-Host " pp=$($r.pp) tg=$($r.tg)" -ForegroundColor Green }
                        else { Write-Host " FAIL" -ForegroundColor Red }
                    } else { Stop-Server; Write-Host " TIMEOUT" -ForegroundColor Red }
                }
            }

            if (-not $SkipSycl) {
                $currentTest++
                Write-Host "  [$currentTest/$totalTests] SYCL pp=$($size.pp) tg=$($size.tg) spec=$specLabel" -NoNewline
                if ($mtp -eq "none") {
                    $raw = & $SyclBenchExe -m $modelPath -p $size.pp -n $size.tg -t $Threads -ngl 99 -r $Reps -o csv 2>$null
                    $r = Parse-BenchCsv $raw
                    if ($r) { "sycl,$model,$($size.pp),$($size.tg),none,0,$Threads,99,$($r.pp),$($r.tg),$timestamp" | Out-File $csvFile -Append -Encoding utf8; Write-Host " pp=$($r.pp) tg=$($r.tg)" -ForegroundColor Green }
                    else { Write-Host " FAIL" -ForegroundColor Red }
                } else {
                    Stop-Server
                    if (Start-Server $SyclServerExe $modelPath 99 $specLabel $specNmax $port) {
                        $r = Bench-Server $port $size.pp $size.tg $Reps; Stop-Server
                        if ($r) { "sycl,$model,$($size.pp),$($size.tg),$specLabel,$specNmax,$Threads,99,$($r.pp),$($r.tg),$timestamp" | Out-File $csvFile -Append -Encoding utf8; Write-Host " pp=$($r.pp) tg=$($r.tg)" -ForegroundColor Green }
                        else { Write-Host " FAIL" -ForegroundColor Red }
                    } else { Stop-Server; Write-Host " TIMEOUT" -ForegroundColor Red }
                }
            }
        }
    }
}

Stop-Server
Write-Host ""; Write-Host "DONE: $csvFile" -ForegroundColor Cyan
