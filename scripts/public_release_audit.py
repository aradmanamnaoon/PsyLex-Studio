"""Fail closed if the public-release tree contains private/source-derived dictionary files.

Only audits distributable source inputs. Does not purport to certify third-party
copyright, source authorship, or every possible secret in arbitrary text.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESOURCE_DIR = ROOT / 'resources'
SEED = RESOURCE_DIR / 'starter_glossary.jsonl'
ALLOWED_RESOURCES = {'starter_glossary.jsonl', 'sample_dictionary.docx'}
EXPECTED_SOURCE = 'PsyLex original starter glossary'
# The only document binaries intentionally included with public source are
# original, minimal demo fixtures. Never ship additional books by accident.
ALLOWED_DOCUMENTS = {
    'resources/sample_dictionary.docx',
    'samples/document_fixtures/sample.docx',
    'samples/document_fixtures/embedded_text.pdf',
    'samples/document_fixtures/scanned_text.pdf',
}


def main() -> int:
    issues: list[str] = []
    marker = ROOT / 'PUBLIC_RELEASE_MARKER.json'
    if not marker.is_file():
        issues.append('Public-release marker is missing; do not publish a private-source build')
    else:
        try:
            metadata = json.loads(marker.read_text(encoding='utf-8'))
            if metadata.get('edition') != 'public-no-third-party-books':
                issues.append('Public-release marker is not valid')
        except Exception:
            issues.append('Public-release marker cannot be parsed')
    if (RESOURCE_DIR / 'dictionaries').exists():
        issues.append('Original resources/dictionaries folder must NOT be distributed')
    if (RESOURCE_DIR / 'lexicon.jsonl').exists():
        issues.append('Original extracted lexicon.jsonl must NOT be distributed')
    for p in RESOURCE_DIR.rglob('*'):
        if p.is_file() and (len(p.relative_to(RESOURCE_DIR).parts) != 1 or p.name not in ALLOWED_RESOURCES):
            issues.append(f'Unexpected resource file {p.relative_to(ROOT)}')
    if not SEED.is_file():
        issues.append('Original demo starter glossary missing')
    else:
        rows = []
        try:
            rows = [json.loads(s) for s in SEED.read_text(encoding='utf-8').splitlines() if s.strip()]
            if len(rows) < 12 or len(rows) > 100:
                issues.append(f'Unexpected starter glossary size: {len(rows)}; expected 12-100 original demo terms')
            if any(r.get('source') != EXPECTED_SOURCE for r in rows):
                issues.append('Non-starter source appears inside the public glossary')
        except Exception as exc:
            issues.append(f'Cannot read starter glossary: {exc}')
    excluded_dirs = {'.venv', 'venv', 'env', '.git', 'dist', 'build', 'reports', '__pycache__', '.pytest_cache'}
    for file in ROOT.rglob('*'):
        if not file.is_file() or any(part in excluded_dirs for part in file.relative_to(ROOT).parts):
            continue
        relative = file.relative_to(ROOT).as_posix()
        if file.suffix.casefold() in {'.docx', '.doc', '.pdf', '.rtf', '.epub', '.odt'} and relative not in ALLOWED_DOCUMENTS:
            issues.append(f'Unexpected document in public source tree: {relative}')
        if file.is_symlink():
            issues.append(f'Unexpected file symlink in public source: {relative}')
    if not (ROOT / '.gitignore').is_file():
        issues.append('Missing .gitignore')
    for p in ROOT.glob('*.env*'):
        if p.name not in ('.env.example', '.env.template'):
            issues.append(f'Potential secret file in root: {p.name}')
    for p in [ROOT / 'dist', ROOT / 'build', ROOT / 'reports']:
        # reports/README.md is safe, and build/dist generated during release;
        # Git ignores them and only the bundled resources can enter the installer.
        if p.name == 'reports' and p.is_dir():
            continue
    if issues:
        for i in issues:
            print('FAIL:', i)
        return 1
    print(f'PASS: public source contains only {len(rows)} original starter entries and no source books/derived lexicon')
    print('NOTE: audit does not replace a human security/license review')
    return 0

if __name__ == '__main__':
    sys.exit(main())
