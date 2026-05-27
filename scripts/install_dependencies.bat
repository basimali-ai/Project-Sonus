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

REM --- Move to the parent folder of the batch file ---
cd /d "%~dp0\.."

REM --- Setup ANSI Colors ---
for /f "tokens=1,2 delims=#" %%a in ('"prompt #$H#$E# & echo on & for %%b in (1) do rem"') do (
  set "DEL=%%a"
)
call :Color_Setup

echo.--- Installing Dependencies via Pip ---
python -m pip install -e .[dev]
if %ERRORLEVEL% neq 0 (
    echo.Error: Pip failed to install dependencies.
    pause
    exit /b 1
)
call :separator

echo.--- Patching dependency files ---
python "./scripts/apply_patch.py"
call :separator

REM --- Create the marker file --- 
echo %DATE% %TIME% > .deps_ready

echo.%green%============= Dependency installation complete =============
echo.Now you can run module by typing 'sonus' or 'python src/main.py'
echo.as well as work on files.%reset%
goto :end

REM --- helper labels ---
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