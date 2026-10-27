@echo off
chcp 65001 >nul 2>nul
title MOOC ShuaKe Assistant
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "PIPOPT=--disable-pip-version-check --timeout 25 --retries 2 --prefer-binary"

rem mirrors are tried one by one: network conditions differ a lot between
rem campus / home / hotspot, so never rely on a single one.
set "MIRRORS=https://pypi.tuna.tsinghua.edu.cn/simple https://mirrors.aliyun.com/pypi/simple https://mirrors.cloud.tencent.com/pypi/simple https://mirrors.huaweicloud.com/repository/pypi/simple https://pypi.mirrors.ustc.edu.cn/simple https://pypi.org/simple"

echo ==================================================
echo    MOOC  ShuaKe  Assistant   v1.4
echo    (first run: about 1-3 minutes)
echo ==================================================
echo.

rem ======================================================
rem  1. locate a python interpreter that REALLY runs
rem
rem  v1.0 only checked whether the "py" command existed.
rem  If the py launcher pointed at a python.exe that had
rem  been removed or never finished installing, the check
rem  passed but "py -3 -m venv" died with
rem  "Unable to create process using ...".  v1.1 actually
rem  executes every candidate and keeps only a real,
rem  existing, non-Store interpreter.
rem ======================================================
call :find_python
if not defined PYEXE0 goto :no_python

set "PYLINE=%BASEPY%"

"%PYEXE0%" -c "import sys;print(sys.version_info[0]*100+sys.version_info[1])" > "%TEMP%\_moocnum.txt" 2>nul
set "PYNUM="
set /p PYNUM=<"%TEMP%\_moocnum.txt"
if not defined PYNUM goto :no_python
if %PYNUM% LSS 310 goto :old_python

"%PYEXE0%" -c "import sys;print(sys.version.split()[0])" > "%TEMP%\_moocver.txt" 2>nul
set "PYVER="
set /p PYVER=<"%TEMP%\_moocver.txt"
del "%TEMP%\_moocnum.txt" >nul 2>nul
del "%TEMP%\_moocver.txt" >nul 2>nul

echo [1/3] Python found : %PYLINE%  (version %PYVER%)
echo       location     : %PYEXE0%
if %PYNUM% GEQ 314 echo       NOTE: Python 3.14 is supported, but 3.12 is the best tested one.
echo.

rem ======================================================
rem  2. virtual environment (fallback: local 'libs' folder)
rem ======================================================
set "EXTRA_PATH="
if exist ".venv" (
    if not exist ".venv\Scripts\python.exe" (
        echo       removing broken .venv ...
        rd /s /q ".venv" >nul 2>nul
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo       creating local virtual environment ...
    "%PYEXE0%" -m venv .venv >nul 2>nul
)

if exist ".venv\Scripts\python.exe" (
    set "PYEXE=%~dp0.venv\Scripts\python.exe"
) else (
    echo.
    echo [WARN] Could not create a virtual environment on this computer.
    echo        Falling back to a local "libs" folder instead.
    echo.
    set "PYEXE=%PYEXE0%"
    set "EXTRA_PATH=%~dp0libs"
    if not exist "libs" mkdir "libs" >nul 2>nul
)
if defined EXTRA_PATH set "PYTHONPATH=%EXTRA_PATH%"

rem ======================================================
rem  3. dependencies
rem
rem  v1.4: the pip route is now layered, because the old
rem  "tsinghua mirror then pypi.org" pair left students on
rem  networks that block both (campus proxy, 360 / Defender
rem  blocking python.exe, mobile hotspot DNS) with
rem  "from versions: none".
rem    (a) wheels\ folder shipped in the zip -> no network
rem    (b) 6 mirrors in turn
rem    (c) official source with relaxed TLS check
rem ======================================================
"%PYEXE%" -c "import playwright" >nul 2>nul
if not errorlevel 1 goto :deps_ok

echo [2/3] installing dependencies, please wait ...
set "PIPEXTRA="
if defined EXTRA_PATH set PIPEXTRA=--target "%EXTRA_PATH%"
set "DEPSOK="

"%PYEXE%" -m pip --version >nul 2>nul
if errorlevel 1 (
    echo       pip is missing on this Python, bootstrapping it ...
    "%PYEXE%" -m ensurepip --upgrade >nul 2>nul
)

if exist "wheels\*.whl" call :install_offline
if defined DEPSOK goto :deps_ok

echo       offline package not usable, going online (needs internet) ...
for %%M in (%MIRRORS%) do if not defined DEPSOK call :install_mirror %%M
if defined DEPSOK goto :deps_ok

echo       all mirrors failed, last try with relaxed TLS check ...
echo       (the full pip error is shown below, please screenshot it)
"%PYEXE%" -m pip install %PIPEXTRA% -r requirements.txt -i https://pypi.org/simple %PIPOPT% --trusted-host pypi.org --trusted-host files.pythonhosted.org --trusted-host pypi.tuna.tsinghua.edu.cn --trusted-host mirrors.aliyun.com --trusted-host mirrors.cloud.tencent.com --trusted-host mirrors.huaweicloud.com --trusted-host pypi.mirrors.ustc.edu.cn
"%PYEXE%" -c "import playwright" >nul 2>nul
if errorlevel 1 goto :deps_failed
set "DEPSOK=1"

:deps_ok
echo [2/3] dependencies OK

rem ======================================================
rem  4. browser engine
rem ======================================================
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
exit /b %RC%


rem ======================================================
rem  subroutines
rem ======================================================
:install_offline
rem  install straight from the wheels\ folder next to this .bat.
rem  needs no network at all, so it works on any campus network.
"%PYEXE%" -m pip install %PIPEXTRA% -r requirements.txt --no-index --find-links "wheels" %PIPOPT% -q
if errorlevel 1 exit /b 0
"%PYEXE%" -c "import playwright" >nul 2>nul
if errorlevel 1 exit /b 0
echo       installed from the bundled offline package
set "DEPSOK=1"
exit /b 0

:install_mirror
echo       trying %~1
"%PYEXE%" -m pip install %PIPEXTRA% -r requirements.txt -i %~1 %PIPOPT% -q
if errorlevel 1 exit /b 0
"%PYEXE%" -c "import playwright" >nul 2>nul
if errorlevel 1 exit /b 0
set "DEPSOK=1"
exit /b 0

:find_python
set "BASEPY="
set "PYEXE0="
for %%C in ("py -3.12" "py -3.11" "py -3.13" "py -3.10" "py -3" "python3.12" "python3.11" "python3.13" "python3.10" "python3" "python") do (
    if not defined PYEXE0 call :probe %%~C
)
if defined PYEXE0 exit /b 0

for %%D in (
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%ProgramFiles%\Python312\python.exe"
    "%ProgramFiles%\Python311\python.exe"
    "%ProgramFiles%\Python313\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
) do (
    if not defined PYEXE0 if exist "%%~D" call :probe_exe "%%~D"
)
exit /b 0

:probe
rem  run the candidate (call so a .bat shim returns instead of taking over)
call %* -c "import sys" >nul 2>nul
if errorlevel 1 exit /b 0
set "TMPEXE="
for /f "delims=" %%P in ('call %* -c "import sys;print(sys.executable)" 2^>nul') do set "TMPEXE=%%P"
if not defined TMPEXE exit /b 0
call :accept "%TMPEXE%" "%*"
exit /b 0

:probe_exe
"%1" -c "import sys" >nul 2>nul
if errorlevel 1 exit /b 0
call :accept "%1" "%1"
exit /b 0

:accept
if not exist "%~1" exit /b 0
set "CANDE=%~1"
if not "%CANDE:WindowsApps=%"=="%CANDE%" exit /b 0
set "PYEXE0=%~1"
set "BASEPY=%~2"
exit /b 0


:no_python
echo [ERROR] No usable Python found on this computer.
echo.
echo   What happened:
echo     The "py" command may exist, but the python.exe behind it is
echo     missing (unfinished install, uninstalled Python still left in
echo     the launcher, or the Microsoft Store version). That is exactly
echo     what makes "py -3 -m venv .venv" fail with
echo     "Unable to create process using ...".
echo.
echo   How to fix (about 3 minutes):
echo     1. Go to   https://www.python.org/downloads/
echo     2. Download  "Windows installer (64-bit)"  for Python 3.12
echo     3. Run the installer and TICK  "Add python.exe to PATH"
echo     4. Close this window, then double-click this .bat again
echo.
echo   Please do NOT install Python from the Microsoft Store.
echo.
start "" https://www.python.org/downloads/
pause
exit /b 1


:old_python
echo [ERROR] Your Python is too old: %PYVER%
echo         This tool needs Python 3.10 or newer.
echo.
echo   Please install Python 3.12:  https://www.python.org/downloads/
echo.
start "" https://www.python.org/downloads/
pause
exit /b 1


:deps_failed
echo.
echo [ERROR] Could not install the Playwright package.
echo.
echo   This is a NETWORK problem, not a Python version problem.
echo   Python %PYVER% is fine - the download never reached any server.
echo.
echo   Fix it in this order:
echo     1. Turn off VPN / proxy, or turn one ON if you normally need it
echo     2. Close 360 / Huorong / Defender real-time protection for a
echo        minute - they often block a new python.exe from using the net
echo     3. Connect to a phone hotspot, then run this .bat again
echo     4. Make sure the folder is NOT inside a OneDrive / cloud folder
echo        and that the path has no Chinese-only characters
echo     5. Manual install in this window, then send me the output:
echo          "%PYEXE%" -m pip install playwright -i https://mirrors.aliyun.com/pypi/simple
echo.
echo   pip diagnostic:
"%PYEXE%" -m pip --version
echo   python used: %PYEXE%
echo   route check:
"%PYEXE%" _netcheck.py
echo.
pause
exit /b 1
