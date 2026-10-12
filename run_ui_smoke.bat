@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\ui_smoke_test.py
) else (
  py scripts\ui_smoke_test.py
)
if errorlevel 1 (
  echo UI smoke test failed. Review the printed error.
  exit /b 1
)
echo UI smoke test passed.
endlocal
