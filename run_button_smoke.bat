@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" scripts\ui_click_smoke_test.py
) else (
    py scripts\ui_click_smoke_test.py
)
if errorlevel 1 (
    echo ERROR: Button integration smoke test failed.
    exit /b 1
)
echo SUCCESS: Button smoke test passed.
endlocal
