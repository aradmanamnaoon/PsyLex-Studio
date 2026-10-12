"""Run a real dictionary lookup using the original public starter glossary.

Does not touch persistent user data, requires no Qt or model provider.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from psylex.core.database import Database
from psylex.core.dictionary import DictionaryService
from psylex.core.ingest import load_jsonl


def configure_unicode_output() -> None:
    """Use UTF-8 when printing Persian terms on Windows legacy consoles.

    Windows Python processes may inherit cp1252 or another legacy encoding.
    A source-backed Persian lookup must never fail simply while reporting it.
    """
    stream = getattr(sys, 'stdout', None)
    if stream is not None and hasattr(stream, 'reconfigure'):
        stream.reconfigure(encoding='utf-8', errors='backslashreplace')


def main() -> int:
    configure_unicode_output()
    lexicon = ROOT / 'resources' / 'starter_glossary.jsonl'
    if not lexicon.exists():
        print('FAIL: resources/starter_glossary.jsonl is missing')
        return 1
    with tempfile.TemporaryDirectory(prefix='psylex-dict-') as folder:
        db = Database(Path(folder) / 'test.sqlite3')
        try:
            count = db.insert_entries(load_jsonl(lexicon))
            print(f'Imported {count:,} original starter glossary entries')
            assert count >= 16, 'Public starter glossary entries are missing'
            term = 'attention'
            hits = DictionaryService(db).search(term)
            print(f'Search: {term} -> {len(hits)} results')
            for hit in hits[:4]:
                print(f'  {hit.kind}: {hit.english} -> {hit.persian} [{hit.source} / {hit.location}]')
            assert any(h.kind == 'exact' and h.persian for h in hits), 'No exact dictionary match found'
            print('PASS: offline dictionary works without Python inference model or cloud API')
        finally:
            db.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
