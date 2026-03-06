@echo off
setlocal

cd /d "%~dp0"

set "MODE=%~1"
if "%MODE%"=="" set "MODE=update"

echo ==================================================
echo [CGI UPDATE] START
echo Mode: %MODE%
echo Repo: %CD%
echo ==================================================

if not exist "CGI\.git" (
  echo [ERROR] CGI submodule not found or not initialized.
  echo Run: git submodule update --init --recursive
  exit /b 1
)

for /f %%i in ('git -C CGI status --porcelain ^| find /c /v ""') do set "CHANGED=%%i"
if not "%CHANGED%"=="0" (
  echo [ERROR] CGI has local changes. Commit or stash inside CGI before updating.
  git -C CGI status -sb
  exit /b 2
)

if /I "%MODE%"=="check" (
  echo [CGI UPDATE] CGI is clean. No update executed.
  git -C CGI status -sb
  exit /b 0
)

if /I not "%MODE%"=="update" (
  echo [ERROR] Unknown mode: %MODE%
  echo Usage: Update-CGI.cmd [check^|update]
  exit /b 3
)

echo [CGI UPDATE] Fetching and fast-forwarding CGI...
git -C CGI fetch origin
if errorlevel 1 exit /b 4

git -C CGI pull --ff-only origin master
if errorlevel 1 exit /b 5

echo.
echo [CGI UPDATE] Submodule status:
git -C CGI status -sb

echo.
echo [CGI UPDATE] Parent repo status for CGI pointer:
git status -sb -- CGI

echo.
echo If CGI pointer changed, commit it in parent repo:
echo   git add CGI
echo   git commit -m "Update CGI submodule pointer"
echo   git push

echo ==================================================
echo [CGI UPDATE] DONE
echo ==================================================
exit /b 0
