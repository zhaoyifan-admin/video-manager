@echo off
setlocal
cd /d "%~dp0"

echo.
echo   Video Manager - one-click installer
echo   ------------------------------------------------------------
echo   Run from project root; all steps are idempotent.
echo.

py -3 -c "import sys" >nul 2>nul
if %errorlevel%==0 (
    py -3 setup.py %*
) else (
    python setup.py %*
)
set RC=%ERRORLEVEL%

echo.
if "%RC%"=="0" (
    echo   [DONE] Install finished. Start backend with: cd backend ^&^& venv\Scripts\python app.py
) else (
    echo   [FAILED] Installer exited with code %RC%. Fix the issue above and run again.
)
echo.
pause
