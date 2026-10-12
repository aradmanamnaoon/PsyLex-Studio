@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
 echo Missing .venv. Run: py -3.11 -m venv .venv
 exit /b 2
)
echo Running automated Python suite...
.venv\Scripts\python.exe -m pytest -q
if errorlevel 1 exit /b 1
echo Creating reproducible PDF, Word and OCR test fixtures...
.venv\Scripts\python.exe -m scripts.make_document_fixtures
if errorlevel 1 exit /b 1
echo Scoring English OCR using the fixture ground truth...
.venv\Scripts\python.exe -m scripts.evaluate_document_ocr samples\document_fixtures\ocr_gold.jsonl --max-cer 0.10 --report reports\ocr_fixture_metrics.json
if errorlevel 1 exit /b 1
echo Document QA smoke test passed. Now perform manual Windows GUI/export tests.
