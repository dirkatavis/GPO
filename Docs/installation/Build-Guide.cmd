@echo off
setlocal EnableExtensions

cd /d "%~dp0"

echo ==============================================
echo Building SETUP_GUIDE.pdf from SETUP_GUIDE.md

echo ==============================================

where py >nul 2>nul
if "%ERRORLEVEL%"=="0" (
  py -3 build_guide.py
) else (
  python build_guide.py
)

set "CODE=%ERRORLEVEL%"
exit /b %CODE%
