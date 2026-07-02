@echo off
setlocal enabledelayedexpansion

rem MTP Benchmark Script for llama.cpp
rem Benchmarks CPU and SYCL backends with MTP speculative decoding

set "BENCH_EXE=%~dp0..\..\build-cpu\bin\Release\llama-bench.exe"
set "SYCL_BENCH_EXE=%~dp0..\..\build-sycl\bin\Release\llama-bench.exe"
set "MODEL_DIR=%~dp0..\..\models"
set "RESULTS_DIR=%~dp0..\results"

if not exist "%RESULTS_DIR%" mkdir "%RESULTS_DIR%"

echo ================================================================
echo  MTP BENCHMARK SUITE
echo ================================================================
echo.

rem Models to benchmark
set "MODELS=Qwen3.6-35B-A3B-Q4_K_M.gguf Qwen3.6-35B-A3B-UD-IQ2_M.gguf Qwen3.6-35B-A3B-MTP-Q8_0.gguf"

rem Prompt/generation sizes
set "SIZES=512,128 1024,128"

rem MTP configs
set "MTP_CONFIGS=none 2 3"

rem Threads
set "THREADS=16"

set "TIMESTAMP=%date:~-4,4%%date:~-4,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
set "TIMESTAMP=%TIMESTAMP: =0%"
set "CSV_FILE=%RESULTS_DIR%\mtp-bench-%TIMESTAMP%.csv"

echo Results: %CSV_FILE%
echo.

rem Header
echo backend,model,pp,tg,pp_t/s,tg_t/s,spec_type,spec_n_max,threads,ngl,timestamp >> "%CSV_FILE%"

for %%M in (%MODELS%) do (
    echo ------------------------
    echo Model: %%M
    echo ------------------------

    for %%S in (%SIZES%) do (
        for /f "tokens=1,2 delims=," %%A in ("%%S") do (
            set "PP=%%A"
            set "TG=%%B"

            for %%C in (%MTP_CONFIGS%) do (
                if "%%C"=="none" (
                    set "SPEC_ARGS="
                    set "SPEC_LABEL=none"
                    set "SPEC_NMAX=0"
                ) else (
                    set "SPEC_ARGS=-spec-type draft-mtp -spec-draft-n-max %%C"
                    set "SPEC_LABEL=draft-mtp"
                    set "SPEC_NMAX=%%C"
                )

                rem CPU benchmark
                echo   CPU: pp=!PP! tg=!TG! spec=!SPEC_LABEL! nmax=!SPEC_NMAX!
                "%BENCH_EXE%" -m "%MODEL_DIR%\%%M" -p !PP! -n !TG! -t %THREADS% -ngl 0 -r 1 -o csv !SPEC_ARGS! 2>nul | findstr /v "^#" >> "%CSV_FILE%"

                rem SYCL benchmark (skip if model too large for VRAM)
                echo   SYCL: pp=!PP! tg=!TG! spec=!SPEC_LABEL! nmax=!SPEC_NMAX!
                "%SYCL_BENCH_EXE%" -m "%MODEL_DIR%\%%M" -p !PP! -n !TG! -t %THREADS% -ngl 99 -r 1 -o csv !SPEC_ARGS! 2>nul | findstr /v "^#" >> "%CSV_FILE%"

                echo.
            )
        )
    )
)

echo ================================================================
echo  BENCHMARK COMPLETE
echo  Results saved to: %CSV_FILE%
echo ================================================================
