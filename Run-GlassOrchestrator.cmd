@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Missing venv Python: .venv\Scripts\python.exe
  pause
  exit /b 1
)

echo Running GlassOrchestrator with venv Python...
".venv\Scripts\python.exe" ".\GlassOrchestrator.py"

echo.
echo Exit code: %errorlevel%
pause
exit /b %errorlevel%
