@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo ==================================================
  echo [TEST RUNNER] ERROR
  echo Missing venv Python: .venv\Scripts\python.exe
  echo ==================================================
  exit /b 1
)

echo ==================================================
echo [TEST RUNNER] START
echo Working dir : %CD%
echo Python      : .venv\Scripts\python.exe
echo Targets     : tests\test_unit.py tests\test_integration.py tests\test_cycle_tracker.py tests\test_failure.py
echo ==================================================

".venv\Scripts\python.exe" -m pytest tests\test_unit.py tests\test_integration.py tests\test_cycle_tracker.py tests\test_failure.py
set "TEST_EXIT=%ERRORLEVEL%"

echo.
if "%TEST_EXIT%"=="0" (
  echo ==================================================
  echo [TEST RUNNER] PASS - all targeted tests passed
  echo Exit code: %TEST_EXIT%
  echo ==================================================
) else (
  echo ==================================================
  echo [TEST RUNNER] FAIL - one or more tests failed
  echo Exit code: %TEST_EXIT%
  echo ==================================================
)

exit /b %TEST_EXIT%
