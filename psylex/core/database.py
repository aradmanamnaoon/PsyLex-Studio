"""SQLite store with deterministic exact-match priority and FTS fallback."""
from __future__ import annotations
import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from psylex.core.models import DictionaryEntry, Evidence, Feedback, Translation, utc_now


def normalize(text: str) -> str:
    """Normalize ASCII term lookup without altering displayed Persian spelling."""
    normalized = " ".join(text.casefold().replace("’", "'").replace("–", "-").split())
    return normalized


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS entries (
  id INTEGER PRIMARY KEY, english TEXT NOT NULL, english_norm TEXT NOT NULL,
  persian TEXT NOT NULL, source TEXT NOT NULL, location TEXT NOT NULL,
  quality REAL NOT NULL, context TEXT DEFAULT '',
  UNIQUE(english_norm,persian,source,location)
);
CREATE INDEX IF NOT EXISTS idx_term ON entries(english_norm);
CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS corrections (
  english_norm TEXT PRIMARY KEY, english TEXT NOT NULL,
  persian TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS history (
  id INTEGER PRIMARY KEY, source TEXT NOT NULL, target TEXT NOT NULL,
  mode TEXT NOT NULL, confidence REAL, evidence_json TEXT NOT NULL,
  warnings_json TEXT NOT NULL, created_at TEXT NOT NULL, favorite INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_history_date ON history(created_at DESC);
CREATE TABLE IF NOT EXISTS feedback (
  id INTEGER PRIMARY KEY, source TEXT NOT NULL, proposed TEXT NOT NULL,
  accepted INTEGER NOT NULL, correction TEXT, created_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._fts = False
        try:
            self._conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS terms_fts USING fts5(english, persian, content='entries', content_rowid='id')")
            self._fts = True
        except sqlite3.OperationalError:
            pass
        self._conn.commit()

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def insert_entries(self, entries: list[DictionaryEntry]) -> int:
        if not entries:
            return 0
        with self.tx() as c:
            before = c.total_changes
            c.executemany("""INSERT OR IGNORE INTO entries
              (english,english_norm,persian,source,location,quality,context)
              VALUES(?,?,?,?,?,?,?)""", [
                (e.english, normalize(e.english), e.persian, e.source,
                 e.location, e.quality, e.context) for e in entries
            ])
            count = c.total_changes - before
            if self._fts and count:
                # Rebuild avoids duplicating content when imports are repeated.
                c.execute("INSERT INTO terms_fts(terms_fts) VALUES('rebuild')")
            return count

    def refresh_bundled_entries(self, entries: list[DictionaryEntry], fingerprint: str) -> int:
        """Atomically replace stale built-in terminology without losing personal data.

        Only the project's original starter glossary is refreshed. All user
        imported documents, feedback, history, and favorites are preserved.
        """
        if not fingerprint or not entries:
            raise ValueError('A nonempty bundled lexicon and fingerprint are required.')
        with self.tx() as c:
            marker = c.execute("SELECT value FROM app_meta WHERE key='bundled_lexicon_sha256'").fetchone()
            if marker is not None and marker[0] == fingerprint:
                count = c.execute("""SELECT COUNT(*) FROM entries
                                     WHERE source IN ('PsyLex original starter glossary')""").fetchone()[0]
                if count > 0:
                    return 0
            c.execute("DELETE FROM entries WHERE source IN ('PsyLex original starter glossary')")
            c.executemany("""INSERT OR IGNORE INTO entries
                (english,english_norm,persian,source,location,quality,context)
                VALUES(?,?,?,?,?,?,?)""", [
                    (e.english, normalize(e.english), e.persian, e.source,
                     e.location, e.quality, e.context) for e in entries
            ])
            if self._fts:
                c.execute("INSERT INTO terms_fts(terms_fts) VALUES('rebuild')")
            c.execute("""INSERT INTO app_meta(key,value) VALUES('bundled_lexicon_sha256', ?)
                         ON CONFLICT(key) DO UPDATE SET value=excluded.value""", (fingerprint,))
        return len(entries)

    def count_entries(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT count(*) FROM entries").fetchone()[0])

    def correction(self, english: str) -> str | None:
        with self._lock:
            row = self._conn.execute("SELECT persian FROM corrections WHERE english_norm=?",
                                     (normalize(english),)).fetchone()
            return str(row[0]) if row else None

    def exact(self, english: str, limit: int = 12) -> list[DictionaryEntry]:
        with self._lock:
            rows = self._conn.execute("""SELECT * FROM entries WHERE english_norm=?
                ORDER BY quality DESC, id ASC LIMIT ?""", (normalize(english), limit)).fetchall()
        return [DictionaryEntry(r['english'], r['persian'], r['source'],
                 r['location'], r['quality'], r['context'], r['id']) for r in rows]

    def search_rows(self, query: str, limit: int = 250) -> list[DictionaryEntry]:
        """Candidate generation via FTS or bounded LIKE; no SQL user text injection."""
        with self._lock:
            rows = []
            if self._fts:
                tokens = [t.replace('"', '') for t in normalize(query).split() if t]
                tokens = [t for t in tokens if any(c.isalnum() for c in t)]
                if tokens:
                    try:
                        term = ' OR '.join('"' + t + '"' for t in tokens[:10])
                        rows = self._conn.execute("""SELECT e.* FROM terms_fts f
                            JOIN entries e ON f.rowid=e.id WHERE terms_fts MATCH ?
                            LIMIT ?""", (term, limit)).fetchall()
                    except sqlite3.OperationalError:
                        pass
            if not rows:
                needle = normalize(query).split()
                prefix = (needle[0] if needle else '')[:40]
                prefix = prefix.replace('!', '!!').replace('%', '!%').replace('_', '!_')
                rows = self._conn.execute("""SELECT * FROM entries WHERE english_norm
                    LIKE ? ESCAPE '!' ORDER BY quality DESC LIMIT ?""",
                    (f'%{prefix}%', limit)).fetchall()
        return [DictionaryEntry(r['english'], r['persian'], r['source'],
                 r['location'], r['quality'], r['context'], r['id']) for r in rows]

    def all_entries(self) -> list[DictionaryEntry]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM entries").fetchall()
        return [DictionaryEntry(r['english'], r['persian'], r['source'],
                 r['location'], r['quality'], r['context'], r['id']) for r in rows]

    def save_translation(self, result: Translation) -> int:
        with self.tx() as c:
            cur = c.execute("""INSERT INTO history(source,target,mode,confidence,evidence_json,warnings_json,created_at)
                VALUES(?,?,?,?,?,?,?)""", (result.source, result.target, result.mode,
                result.confidence, json.dumps([e.to_dict() for e in result.evidence], ensure_ascii=False),
                json.dumps(result.warnings, ensure_ascii=False), result.created_at))
            return int(cur.lastrowid)

    def history(self, limit: int = 100, favorites_only: bool = False) -> list[dict]:
        sql = 'SELECT * FROM history'
        if favorites_only:
            sql += ' WHERE favorite=1'
        sql += ' ORDER BY id DESC LIMIT ?'
        with self._lock:
            rows = self._conn.execute(sql, (limit,)).fetchall()
        return [dict(r) for r in rows]

    def favorite(self, history_id: int, value: bool) -> None:
        with self.tx() as c:
            c.execute("UPDATE history SET favorite=? WHERE id=?", (int(value), history_id))

    def record_feedback(self, feedback: Feedback) -> None:
        with self.tx() as c:
            c.execute("""INSERT INTO feedback(source,proposed,accepted,correction,created_at)
                VALUES(?,?,?,?,?)""", (feedback.source, feedback.proposed, int(feedback.accepted),
                feedback.correction, feedback.created_at))
            approved = feedback.proposed if feedback.accepted else feedback.correction
            if approved.strip():
                c.execute("""INSERT INTO corrections(english_norm,english,persian,updated_at)
                    VALUES(?,?,?,?) ON CONFLICT(english_norm) DO UPDATE SET
                    english=excluded.english,persian=excluded.persian,updated_at=excluded.updated_at""",
                    (normalize(feedback.source), feedback.source, approved, utc_now()))

    def examples(self, query: str, limit: int = 4) -> list[tuple[str, str]]:
        with self._lock:
            rows = self._conn.execute("SELECT english,persian FROM corrections ORDER BY updated_at DESC LIMIT 250").fetchall()
        # Lightweight overlap; no access to external models required.
        q_tokens = set(normalize(query).split())
        ranked = sorted(rows, key=lambda r: len(q_tokens.intersection(set(normalize(r[0]).split()))), reverse=True)
        return [(r[0], r[1]) for r in ranked if r[0] and
                q_tokens.intersection(set(normalize(r[0]).split()))][:limit]

    def export_feedback(self, path: Path) -> int:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM feedback ORDER BY id").fetchall()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', encoding='utf-8') as out:
            for r in rows:
                data = {'prompt': r['source'], 'chosen': r['proposed'] if r['accepted'] else r['correction'],
                        'rejected': r['proposed'] if not r['accepted'] else None,
                        'timestamp': r['created_at']}
                out.write(json.dumps(data, ensure_ascii=False) + '\n')
        return len(rows)
