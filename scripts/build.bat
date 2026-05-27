@REM Copyright 2026 Syed Basim Ali
@REM
@REM Licensed under the Apache License, Version 2.0 (the "License");
@REM you may not use this file except in compliance with the License.
@REM You may obtain a copy of the License at
@REM
@REM     http://www.apache.org/licenses/LICENSE-2.0
@REM
@REM Unless required by applicable law or agreed to in writing, software
@REM distributed under the License is distributed on an "AS IS" BASIS,
@REM WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
@REM See the License for the specific language governing permissions and
@REM limitations under the License.

@echo off

REM --- Move to the parent folder of the batch file (the project root) ---
cd /d "%~dp0\.."

REM --- Setup ANSI Colors ---
for /f "tokens=1,2 delims=#" %%a in ('"prompt #$H#$E# & echo on & for %%b in (1) do rem"') do (
  set "DEL=%%a"
)
call :Color_Setup

echo.--- Verifying Environment ---

REM --- Create a temporary python script in the user's TEMP folder ---
echo import sys; sys.exit(0 if (sys.version_info ^>= (3,12,10) and sys.version_info ^< (3,13)) else 1) > "%TEMP%\check_version.py"
if not exist "%TEMP%\check_version.py" (
    echo.%red%Error: Failed to create temporary script for Python version check.%reset%
    echo.%red%Please check permissions for your %%TEMP%% directory.%reset%
    exit /b 1
)
python "%TEMP%\check_version.py"
set PY_VERSION_CHECK_ERRORLEVEL=%ERRORLEVEL%
REM --- Clean up the temporary script ---
del "%TEMP%\check_version.py"
if %PY_VERSION_CHECK_ERRORLEVEL% neq 0 (
    echo.%red%Error: Please install a Python version that is ^>= 3.12.10 and ^< 3.13%reset%
    exit /b 1
)
call :separator

REM --- Check if the project is installed in this environment ---
python -c "import importlib.metadata; importlib.metadata.distribution('project-sonus')" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo.%red%Error: Project metadata not found in this Python environment.%reset%
    echo.It looks like 'deps.bat' hasn't been run for this specific Python installation.
    exit /b 1
)

REM --- Check for the Patch Marker --- 
if not exist ".deps_ready" (
    echo.%red%Error: Patch marker '.deps_ready' missing.%reset%
    echo.Even if dependencies are installed, the patches haven't been applied.
    echo.Please run 'deps.bat'.
    exit /b 1
)

echo.%green%Environment and dependencies verified.%reset%
call :separator

echo.--- Checking if Nuitka is installed... ---
python -m pip show nuitka >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo.Nuitka not found. Installing...
    pip install nuitka
) else (
    echo.Nuitka already installed.
)
call :separator

echo.--- Starting Build Process for Project Sonus... ---
set MAIN_SCRIPT=main
set RESTARTER_SCRIPT=restarter
set /p FILE_VERSION=<version.txt
set DIST_DIR=./dist
set TMP_DIR=./tmp

REM --- Extract first two numbers for product version ---
for /f "tokens=1,2 delims=." %%a in ("%FILE_VERSION%") do (
    set PRODUCT_VERSION=%%a.%%b
)

echo.Using Options:
echo.MAIN_SCRIPT = %MAIN_SCRIPT%
echo.RESTARTER_SCRIPT = %RESTARTER_SCRIPT%
echo.FILE_VERSION = %FILE_VERSION%
echo.PRODUCT_VERSION = %PRODUCT_VERSION%
echo.DIST_DIR = %DIST_DIR%
echo.TMP_DIR = %TMP_DIR%
call :separator

if not exist "%DIST_DIR%" mkdir "%DIST_DIR%"
if not exist "%TMP_DIR%" mkdir "%TMP_DIR%"

echo.--- Building Project Sonus... [1/2] ---
python -m nuitka "./src/%MAIN_SCRIPT%.py" ^
  --standalone ^
  --reproducible=yes ^
  --include-windows-runtime-dlls=no ^
  --include-data-files="./src/Assets/*=./Assets/" ^
  --include-data-files="./src/_sonus_root.marker=./" ^
  --include-data-files="./scripts/_deployed.marker=./" ^
  --include-package-data=soundcard ^
  --include-module=wx._xml ^
  --include-module="winrt.windows.foundation" ^
  --include-module="winrt.windows.foundation.collections" ^
  --include-module="winrt.windows.data.xml.dom" ^
  --include-module="winrt.windows.ui.notifications" ^
  --windows-console-mode=attach ^
  --windows-icon-from-ico="./src/Assets/logo.ico" ^
  --output-dir="%DIST_DIR%" ^
  --file-version=%FILE_VERSION% ^
  --product-version=%PRODUCT_VERSION% ^
  --company-name="Syed Basim Ali" ^
  --output-filename="Project Sonus.exe" ^
  --file-description="Project Sonus - Protecting Ears" ^
  --copyright="Copyright (c) 2026 Syed Basim Ali. Licensed under Apache 2.0."
call :separator

echo.--- Building Project Sonus... [2/2] ---
python -m nuitka "./src/%RESTARTER_SCRIPT%.py" ^
  --standalone ^
  --reproducible=yes ^
  --include-windows-runtime-dlls=no ^
  --windows-console-mode=attach ^
  --windows-icon-from-ico="./src/Assets/logo.ico" ^
  --output-dir="%DIST_DIR%" ^
  --file-version=%FILE_VERSION% ^
  --product-version=%PRODUCT_VERSION% ^
  --company-name="Syed Basim Ali" ^
  --output-filename="Project Sonus Restarter.exe" ^
  --file-description="Restarting Project Sonus..." ^
  --copyright="Copyright (c) 2026 Syed Basim Ali. Licensed under Apache 2.0."
call :separator

echo.--- Preparing 'Project Sonus' folder... ---
pushd "%DIST_DIR%"
if exist "Project Sonus" (
    echo.Project Sonus folder already exists. Deleting...
    rmdir /S /Q "Project Sonus"
)
ren "%MAIN_SCRIPT%.dist" "Project Sonus"
move "%RESTARTER_SCRIPT%.dist\*" "Project Sonus\"
rmdir /S /Q "%RESTARTER_SCRIPT%.dist"
popd
call :separator

echo.--- Moving '%MAIN_SCRIPT%.build' folder to '%TMP_DIR%' for cleanup... ---
if exist "%TMP_DIR%/%MAIN_SCRIPT%.build" (
    rmdir /S /Q "%TMP_DIR%/%MAIN_SCRIPT%.build"
)
move "%DIST_DIR%\%MAIN_SCRIPT%.build" "%TMP_DIR%"
call :separator
echo.--- Moving '%RESTARTER_SCRIPT%.build' folder to '%TMP_DIR%' for cleanup... ---
if exist "%TMP_DIR%/%RESTARTER_SCRIPT%.build" (
    rmdir /S /Q "%TMP_DIR%/%RESTARTER_SCRIPT%.build"
)
move "%DIST_DIR%/%RESTARTER_SCRIPT%.build" "%TMP_DIR%"
call :separator

echo.%green%============= Build complete =============%reset%
echo.You can find output in "%DIST_DIR%/Project Sonus"
goto :end

REM --- Helper labels ---
:Color_Setup
set "ESC="
set "red=%ESC%[91m"
set "green=%ESC%[92m"
set "yellow=%ESC%[93m"
set "reset=%ESC%[0m"
goto :eof

:separator
echo ---------------------------------
goto :eof

:end