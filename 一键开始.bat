@echo off
chcp 65001 >nul 2>nul
title MOOC ShuaKe Assistant
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"

echo ==================================================
echo    MOOC  ShuaKe  Assistant   v1.0
echo    (first run needs internet, about 1-3 minutes)
echo ==================================================
echo.

set "BASEPY="
where py >nul 2>nul
if not errorlevel 1 set "BASEPY=py -3"
if not defined BASEPY (
  where python >nul 2>nul
  if not errorlevel 1 set "BASEPY=python"
)
if not defined BASEPY (
  echo [ERROR] Python not found on this computer.
  echo.
  echo   1. Go to  https://www.python.org/downloads/
  echo   2. Download Python 3.10 - 3.13 for Windows
  echo   3. IMPORTANT: tick "Add python.exe to PATH" when installing
  echo   4. Run this file again
  echo.
  pause
  exit /b 1
)

echo [1/3] Python found: %BASEPY%
if not exist ".venv\Scripts\python.exe" (
  echo       creating local virtual environment ...
  %BASEPY% -m venv .venv
  if errorlevel 1 (
    echo [ERROR] failed to create venv
    pause
    exit /b 1
  )
)
set "PYEXE=%~dp0.venv\Scripts\python.exe"

"%PYEXE%" -c "import playwright" >nul 2>nul
if errorlevel 1 (
  echo [2/3] installing dependencies, please wait ...
  "%PYEXE%" -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple -q
  if errorlevel 1 (
    echo       mirror failed, retry with official source ...
    "%PYEXE%" -m pip install -r requirements.txt
  )
  "%PYEXE%" -c "import playwright" >nul 2>nul
  if errorlevel 1 (
    echo [ERROR] dependency install failed. Check network / proxy and retry.
    pause
    exit /b 1
  )
) else (
  echo [2/3] dependencies OK
)

if not exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" (
  if not exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" (
    echo [3/3] Edge not found, downloading a browser engine ...
    "%PYEXE%" -m playwright install chromium
  ) else (
    echo [3/3] Microsoft Edge detected
  )
) else (
  echo [3/3] Microsoft Edge detected
)

echo.
"%PYEXE%" main.py %*
set "RC=%errorlevel%"
echo.
if not "%RC%"=="0" echo [exit code %RC%] see logs folder for details.
echo ==================================================
pause
