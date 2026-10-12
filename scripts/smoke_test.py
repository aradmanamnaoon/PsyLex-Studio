"""Offline smoke check for an unpacked source distribution (no GUI required)."""
from __future__ import annotations
# Allow `python scripts/smoke_test.py` from the project root.
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pathlib import Path
from tempfile import TemporaryDirectory
from psylex.core.config import Settings
from psylex.core.database import Database
from psylex.core.ingest import load_jsonl
from psylex.rag.graph import TranslationPipeline

ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    lexicon = ROOT / 'resources' / 'starter_glossary.jsonl'
    if not lexicon.exists():
        raise FileNotFoundError(lexicon)
    with TemporaryDirectory() as directory:
        db = Database(Path(directory) / 'test.sqlite3')
        count = db.insert_entries(load_jsonl(lexicon))
        if count < 16:
            raise AssertionError(f'Too few terms imported: {count}')
        result = TranslationPipeline(db, Settings(mode='dictionary')).translate('working memory', save=False)
        assert result.target and result.evidence and result.evidence[0].source
        correction = db.correction('working memory')
        assert correction is None
        print(f'OK: {count:,} entries; working memory → {result.target}; citation: {result.evidence[0].location}')
        db.close()
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
