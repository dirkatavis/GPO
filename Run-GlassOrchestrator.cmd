@echo off
setlocal

cd /d "%~dp0"

set "VENV_PY=.venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
  echo [BOOTSTRAP] Creating virtual environment in .venv ...
  where py >nul 2>&1
  if errorlevel 1 (
    python -m venv .venv
  ) else (
    py -3 -m venv .venv
  )

  if not exist "%VENV_PY%" (
    echo [ERROR] Failed to create virtual environment.
    exit /b 1
  )
)

echo [BOOTSTRAP] Installing/updating Python requirements ...
"%VENV_PY%" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo [ERROR] Failed to install requirements from requirements.txt
  exit /b 1
)

echo Running GlassOrchestrator with venv Python...
"%VENV_PY%" ".\GlassOrchestrator.py"

echo.
echo Exit code: %errorlevel%
exit /b %errorlevel%
