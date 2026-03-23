@echo off
setlocal

cd /d "%~dp0"

echo [INFO] This repository now uses a single-repo layout.
echo [INFO] CGI is no longer managed as a git submodule.
echo [INFO] Update-CGI.cmd is deprecated and no action is required.
exit /b 0
