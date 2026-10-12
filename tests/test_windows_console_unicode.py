"""Regression for Windows cp1252 dictionaries failing the strict release gate.

These tests do not skip or relax any existing release checks.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def test_dictionary_smoke_prints_persian_even_if_child_inherits_cp1252():
    """Reproduce the real Windows crash: UnicodeEncodeError in print(hit.persian)."""
    env = {**os.environ, 'PYTHONIOENCODING': 'cp1252', 'PYTHONUTF8': '0'}
    result = subprocess.run(
        [sys.executable, 'scripts/dictionary_smoke.py'],
        cwd=ROOT, env=env, capture_output=True, timeout=60, check=False,
    )
    assert result.returncode == 0, result.stderr.decode('utf-8', errors='replace')
    output = result.stdout.decode('utf-8')
    assert 'PASS: offline dictionary works' in output
    assert 'توجه' in output


def test_release_gate_forces_unicode_for_every_child(monkeypatch):
    """The parent must configure child encoding, not just its own capture decoder."""
    from scripts import release_gate

    seen = []

    def fake_run(*args, **kwargs):
        seen.append(kwargs['env'])
        return SimpleNamespace(returncode=0, stdout='توجه', stderr='')

    monkeypatch.setattr(release_gate.subprocess, 'run', fake_run)
    monkeypatch.setenv('PYTHONIOENCODING', 'cp1252')
    result = release_gate.run_one('dictionary_smoke', [sys.executable, 'scripts/dictionary_smoke.py'])
    assert result['status'] == 'PASS'
    assert seen and seen[0]['PYTHONIOENCODING'].lower() == 'utf-8'
