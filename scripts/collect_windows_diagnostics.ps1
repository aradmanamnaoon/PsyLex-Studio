# Execute from project root: powershell -ExecutionPolicy Bypass -File scripts\collect_windows_diagnostics.ps1
# This does not print or collect API keys, environment values, or user documents.
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
$python = '.\.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Missing .venv Windows interpreter; create/install the venv first.' }
$folder = Join-Path $root 'reports\windows_diagnostics'
New-Item -ItemType Directory -Force -Path $folder | Out-Null
& $python --version *> (Join-Path $folder 'python_version.txt')
& $python -m pip show litellm PySide6 rapidocr-onnxruntime keyring *> (Join-Path $folder 'package_versions.txt')
& $python -m pytest -ra --tb=long *> (Join-Path $folder 'pytest_full.txt')
$pytestExit = $LASTEXITCODE
& $python scripts\release_gate.py --require-windows --require-gui --require-native-ocr --output (Join-Path $folder 'release_gate.json') *> (Join-Path $folder 'release_gate_console.txt')
$gateExit = $LASTEXITCODE
@("Pytest exit: $pytestExit", "Strict Windows gate exit: $gateExit") |
  Set-Content -Path (Join-Path $folder 'summary.txt') -Encoding UTF8
$zip = Join-Path $root 'reports\PsyLex_Windows_Diagnostics.zip'
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path (Join-Path $folder '*') -DestinationPath $zip
Write-Host "Diagnostics saved: $zip"
Write-Host "Pytest exit: $pytestExit | Windows release gate exit: $gateExit"
Write-Host 'Upload the ZIP for debugging. It does not include settings.json or API keys.'
if ($pytestExit -ne 0 -or $gateExit -ne 0) { exit 1 }
