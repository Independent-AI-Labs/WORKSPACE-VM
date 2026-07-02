@echo off
setlocal enabledelayedexpansion

rem Build llama.cpp with CPU-only backend using MSVC
rem Persists build to projects\llama.cpp\build-cpu\

rem Resolve paths
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%I in ("%SCRIPT_DIR%\..\..") do set "PROJECT_ROOT=%%~fI"
set "LLAMA_DIR=%PROJECT_ROOT%\projects\llama.cpp"
set "BUILD_DIR=%LLAMA_DIR%\build-cpu"

echo === Checking prerequisites ===
where cmake >nul 2>&1
if errorlevel 1 (
    echo ERROR: cmake not found. Install from https://cmake.org/download/
    exit /b 1
)
for /f "delims=" %%i in ('cmake -version 2^>^&1') do (
    set "cmake_line=%%i"
    goto :cmake_done
)
:cmake_done
echo   cmake: %cmake_line%
echo.

echo === Step 1: Preparing llama.cpp Source ===
if not exist "%LLAMA_DIR%\" (
    echo Cloning llama.cpp...
    git clone https://github.com/ggml-org/llama.cpp.git "%LLAMA_DIR%"
    if errorlevel 1 (
        echo ERROR: Failed to clone llama.cpp
        exit /b 1
    )
) else (
    echo llama.cpp exists, skipping clone
)

echo === Step 2: Configuring CMake (CPU) ===
cd /d "%LLAMA_DIR%"
cmake -B "%BUILD_DIR%" ^
    -G "Visual Studio 17 2022" ^
    -A x64 ^
    -DGGML_VULKAN=OFF ^
    -DGGML_SYCL=OFF ^
    -DCMAKE_BUILD_TYPE=Release
if errorlevel 1 (
    echo ERROR: CMake configuration failed
    exit /b 1
)

echo === Step 3: Building ===
cmake -build "%BUILD_DIR%" -config Release -j %NUMBER_OF_PROCESSORS%
if errorlevel 1 (
    echo ERROR: Build failed
    exit /b 1
)

echo ================================================================
echo  BUILD SUCCESSFUL!
echo  Binary: %BUILD_DIR%\bin\Release\llama-server.exe
echo ================================================================
