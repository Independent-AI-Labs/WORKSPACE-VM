@echo off
setlocal

set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%\..\..
set LLAMA_DIR=%PROJECT_ROOT%\projects\llama.cpp
set SERVER_EXE=%LLAMA_DIR%\build-cpu\bin\Release\llama-server.exe
set MODEL=%LLAMA_DIR%\models\Qwen3.6-35B-A3B-Q4_K_M.gguf
set LOG_FILE=%PROJECT_ROOT%\.llama-cpu-service.log
set ENV_FILE=%PROJECT_ROOT%\.env

if not exist "%SERVER_EXE%" (
    echo [%date% %time%] ERROR: Server binary not found >> "%LOG_FILE%"
    exit /b 1
)

if not exist "%MODEL%" (
    echo [%date% %time%] ERROR: Model not found >> "%LOG_FILE%"
    exit /b 1
)

set API_KEY=
if exist "%ENV_FILE%" (
    for /f "tokens=2 delims==" %%A in ('findstr /i "^LLAMA_API_KEY=" "%ENV_FILE%"') do set API_KEY=%%A
)

echo [%date% %time%] Starting llama-server CPU service... >> "%LOG_FILE%"

if defined API_KEY (
    "%SERVER_EXE%" -m "%MODEL%" --host 0.0.0.0 --port 8080 --api-key "%API_KEY%" -c 262144 -t 16 -fa on -np 1 --cache-ram -1 --no-cache-idle-slots --log-disable >> "%LOG_FILE%" 2>&1
) else (
    "%SERVER_EXE%" -m "%MODEL%" --host 0.0.0.0 --port 8080 -c 262144 -t 16 -fa on -np 1 --cache-ram -1 --no-cache-idle-slots --log-disable >> "%LOG_FILE%" 2>&1
)

echo [%date% %time%] Server exited with code %errorlevel% >> "%LOG_FILE%"
