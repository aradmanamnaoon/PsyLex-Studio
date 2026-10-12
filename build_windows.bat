@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    py -3.11 -m venv .venv
    if errorlevel 1 goto :fail
)
".venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" -m pip install -e ".[dev]"
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" scripts\release_gate.py --require-windows --require-gui --require-native-ocr
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" build_installer.py --clean
if errorlevel 1 goto :fail
if not exist "dist\PsyLexStudio\PsyLexStudio.exe" goto :fail
"dist\PsyLexStudio\PsyLexStudio.exe" --self-test-report "dist\package-self-test.json"
if errorlevel 1 goto :fail
echo.
echo Release candidate build completed with packaged OCR self-test PASS.
if exist "dist\installer\PsyLexStudio-Setup.exe" (
    echo Installer: dist\installer\PsyLexStudio-Setup.exe
) else (
    echo Inno Setup is not installed: no Setup.exe was created.
    echo You can distribute the full dist\PsyLexStudio directory or install Inno Setup and rebuild.
)
echo Check dist\package-self-test.json and test the installer on a clean PC.
pause
exit /b 0
:fail
echo.
echo ERROR: One or more release checks failed. Do not publish this build.
pause
exit /b 1
