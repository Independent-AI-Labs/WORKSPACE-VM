@echo off
setlocal enabledelayedexpansion

rem Build llama.cpp with Intel oneAPI SYCL backend (Arc, Flex, Max)
rem Persists build to projects\llama.cpp\build-sycl\

set "ONEAPI_VARS=C:\Program Files (x86)\Intel\oneAPI\setvars.bat"

rem Resolve paths
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%I in ("%SCRIPT_DIR%\..\..") do set "PROJECT_ROOT=%%~fI"
set "LLAMA_DIR=%PROJECT_ROOT%\projects\llama.cpp"
set "BUILD_DIR=%LLAMA_DIR%\build-sycl"

echo === Step 1: Checking oneAPI Environment ===
if not exist "%ONEAPI_VARS%" (
    echo ERROR: Intel oneAPI toolkit not found at %ONEAPI_VARS%
    exit /b 1
)

echo Sourcing Intel environment...
call "%ONEAPI_VARS%" intel64 -force >nul 2>&1
if errorlevel 1 (
    echo ERROR: Failed to source Intel oneAPI environment
    exit /b 1
)

echo === Step 2: Preparing llama.cpp Source ===
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

echo === Step 3: Configuring CMake (SYCL) ===
cd /d "%LLAMA_DIR%"
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
cmake -B "%BUILD_DIR%" ^
    -G "Visual Studio 17 2022" ^
    -A x64 ^
    -DGGML_SYCL=ON ^
    -DCMAKE_C_COMPILER=icx-cl ^
    -DCMAKE_CXX_COMPILER=icx-cl ^
    -DCMAKE_BUILD_TYPE=Release
if errorlevel 1 (
    echo ERROR: CMake configuration failed
    exit /b 1
)

echo === Step 4: Building ===
cmake -build "%BUILD_DIR%" -config Release -j %NUMBER_OF_PROCESSORS%
if errorlevel 1 (
    echo ERROR: Build failed
    exit /b 1
)

echo ================================================================
echo  BUILD SUCCESSFUL!
echo  Binary: %BUILD_DIR%\bin\Release\llama-server.exe
echo ================================================================
