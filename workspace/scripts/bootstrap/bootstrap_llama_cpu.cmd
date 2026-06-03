@echo off
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%I in ("%SCRIPT_DIR%\..\..\..") do set "PROJECT_ROOT=%%~fI"

echo === llama.cpp (CPU) Bootstrap ===
call "%PROJECT_ROOT%\scripts\setup\build-llama-cpu.cmd"
