"""PsyLex Studio pre-release gate; no cloud API calls or user-data changes.

Windows full verification:
    python scripts/release_gate.py --require-windows --require-gui --require-native-ocr

Default development run executes core tests and terminology checks; optional
checks are explicitly marked SKIPPED, never silently counted as successful.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_one(label: str, command: list[str], *, timeout: int = 360) -> dict:
    try:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                encoding='utf-8', errors='replace', timeout=timeout,
                                env={**os.environ, 'PYTHONPATH': str(ROOT),
                                     'QT_QPA_PLATFORM': os.environ.get('QT_QPA_PLATFORM', 'offscreen'),
                                     # Always capture Persian/Unicode output as UTF-8.
                                     # subprocess.run(encoding=...) only decodes the parent side;
                                     # it does NOT configure child Python's stdout encoding.
                                     'PYTHONIOENCODING': 'utf-8'},
                                check=False)
        return {'name': label, 'status': 'PASS' if result.returncode == 0 else 'FAIL',
                'return_code': result.returncode, 'command': command,
                'output_tail': (result.stdout + '\n' + result.stderr)[-4500:]}
    except Exception as exc:
        return {'name': label, 'status': 'FAIL', 'command': command,
                'error': f'{type(exc).__name__}: {str(exc)[:250]}'}


def main() -> int:
    ap = argparse.ArgumentParser(description='Release checks (offline, no cloud billing)')
    ap.add_argument('--require-windows', action='store_true')
    ap.add_argument('--require-gui', action='store_true')
    ap.add_argument('--require-native-ocr', action='store_true')
    ap.add_argument('--output', type=Path, default=ROOT / 'reports/release_gate.json')
    options = ap.parse_args()
    python = sys.executable
    outcomes: list[dict] = []
    if options.require_windows:
        outcomes.append({'name': 'windows_environment',
                         'status': 'PASS' if sys.platform == 'win32' else 'FAIL',
                         'details': f'actual platform {sys.platform}'})
    outcomes.append(run_one('python_tests', [python, '-m', 'pytest', '-q'], timeout=240))
    outcomes.append(run_one('dictionary_smoke', [python, 'scripts/dictionary_smoke.py'], timeout=120))
    outcomes.append(run_one('public_glossary_quality',
                            [python, 'scripts/public_release_audit.py'], timeout=60))
    ocr = [python, 'scripts/evaluate_document_ocr.py',
           'samples/document_fixtures/ocr_gold.jsonl',
           '--report', str(ROOT / 'reports/release_ocr_smoke.json')]
    if options.require_native_ocr:
        ocr.append('--require-native')
    outcomes.append(run_one('ocr_fixture', ocr, timeout=150))
    qt_available = importlib.util.find_spec('PySide6') is not None
    if options.require_gui or qt_available:
        outcomes.append(run_one('gui_interactions', [python, 'scripts/ui_click_smoke_test.py'], timeout=100))
        outcomes.append(run_one('gui_layout', [python, 'scripts/ui_smoke_test.py'], timeout=100))
        outcomes.append(run_one('gui_activity_and_cancellation',
                                [python, 'scripts/ui_ux_smoke_test.py'], timeout=100))
        outcomes.append(run_one('gui_first_launch_model_setup',
                                [python, 'scripts/ui_install_model_setup_smoke_test.py'], timeout=100))
        outcomes.append(run_one('gui_credentials_persistence',
                                [python, 'scripts/ui_credentials_smoke_test.py'], timeout=100))
    else:
        outcomes.append({'name': 'gui_interactions', 'status': 'SKIPPED',
                         'reason': 'PySide6 unavailable in this environment'})
        outcomes.append({'name': 'gui_layout', 'status': 'SKIPPED',
                         'reason': 'PySide6 unavailable in this environment'})
        outcomes.append({'name': 'gui_activity_and_cancellation', 'status': 'SKIPPED',
                         'reason': 'PySide6 unavailable in this environment'})
        outcomes.append({'name': 'gui_first_launch_model_setup', 'status': 'SKIPPED',
                         'reason': 'PySide6 unavailable in this environment'})
        outcomes.append({'name': 'gui_credentials_persistence', 'status': 'SKIPPED',
                         'reason': 'PySide6 unavailable in this environment'})
    result = ('FAIL' if any(r['status'] == 'FAIL' for r in outcomes)
              else 'INCOMPLETE' if any(r['status'] == 'SKIPPED' for r in outcomes)
              else 'PASS')
    report = {'result': result, 'platform': platform.platform(),
              'python': sys.version.split()[0], 'checks': outcomes,
              'note': 'Live cloud OCR/LLM, semantic glossary accuracy, and Windows installer acceptance are separate tests.'}
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    for item in outcomes:
        print(f"{item['status']:10} {item['name']}")
        if item['status'] == 'FAIL':
            print((item.get('output_tail') or item.get('error') or '')[-650:])
    print(f'Overall: {result}. Report: {options.output}')
    return 1 if result == 'FAIL' else (2 if result == 'INCOMPLETE' else 0)


if __name__ == '__main__':
    raise SystemExit(main())
