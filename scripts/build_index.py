"""Optional local Chroma index; run after installing [rag] dependencies."""
from __future__ import annotations
# Allow `python scripts/build_index.py` from the project root.
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from psylex.core.config import Settings, bundle_dir, data_dir
from psylex.core.database import Database
from psylex.core.ingest import load_jsonl
from psylex.rag.retrieval import HybridRetriever


def main() -> None:
    db = Database(data_dir() / 'psylex.sqlite3')
    if not db.count_entries():
        db.insert_entries(load_jsonl(bundle_dir() / 'resources' / 'starter_glossary.jsonl'))
    cfg = Settings.load()
    print('Building dense index. First run may download a local embedding model.')
    print('Entries indexed:', HybridRetriever(db, cfg).build_vectors())
    db.close()


if __name__ == '__main__':
    main()
