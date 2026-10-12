"""Public edition must not package private reference books or their extracted lexicon."""
from __future__ import annotations
import json
import hashlib
from pathlib import Path

from psylex.core.database import Database
from psylex.core.models import DictionaryEntry

ROOT = Path(__file__).resolve().parents[1]


def test_only_original_demo_glossary_is_distributed():
    assert not (ROOT / 'resources' / 'dictionaries').exists()
    assert not (ROOT / 'resources' / 'lexicon.jsonl').exists()
    entries = [json.loads(line) for line in (ROOT / 'resources' / 'starter_glossary.jsonl').read_text(encoding='utf-8').splitlines()]
    assert 12 <= len(entries) <= 100
    assert {entry['source'] for entry in entries} == {'PsyLex original starter glossary'}


def test_seed_refresh_never_removes_user_imported_reference(tmp_path: Path):
    db = Database(tmp_path / 'user_data.sqlite3')
    try:
        private = DictionaryEntry('private imported term', 'ترجمه خصوصی', 'imported_reference.docx', 'table 1', .95)
        db.insert_entries([private])
        built_in = [DictionaryEntry('attention', 'توجه', 'PsyLex original starter glossary', 'starter entry 1', .85)]
        fingerprint = hashlib.sha256(b'public-fixture-v1').hexdigest()
        assert db.refresh_bundled_entries(built_in, fingerprint) == 1
        assert db.refresh_bundled_entries(built_in, fingerprint) == 0
        assert db.exact('private imported term')[0].source == 'imported_reference.docx'
    finally:
        db.close()
