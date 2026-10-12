"""Offline English–Persian psychology dictionary search.

Dictionary is a first-class product workflow, *not* an LLM inference setting.
All displayed translations are grounded in imported source entries or user memory.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from psylex.core.database import Database, normalize
from psylex.core.models import DictionaryEntry

MatchKind = Literal['approved', 'exact', 'related']


@dataclass(frozen=True, slots=True)
class DictionaryHit:
    english: str
    persian: str
    source: str
    location: str
    quality: float | None
    kind: MatchKind

    @property
    def match_label(self) -> str:
        return {'approved': 'Personal correction', 'exact': 'Exact', 'related': 'Related'}[self.kind]


class DictionaryService:
    def __init__(self, db: Database):
        self.db = db

    def search(self, query: str, limit: int = 80) -> list[DictionaryHit]:
        """Search local dictionary with corrected > exact > related priority.

        The quality score is a source-extraction score, not linguistic confidence.
        """
        query = query.strip()
        if not query:
            return []
        if not 1 <= limit <= 500:
            raise ValueError('limit must be between 1 and 500')
        key = normalize(query)
        hits: list[DictionaryHit] = []
        seen: set[tuple[str, str]] = set()

        def append(english: str, persian: str, source: str, location: str,
                   quality: float | None, kind: MatchKind) -> None:
            pair = (normalize(english), persian)
            if pair not in seen:
                seen.add(pair)
                hits.append(DictionaryHit(english, persian, source, location, quality, kind))

        correction = self.db.correction(query)
        if correction:
            append(query, correction, 'Personal translation memory', 'Approved by user', None, 'approved')

        exact = self.db.exact(query, limit=100)
        for item in exact:
            append(item.english, item.persian, item.source, item.location, item.quality, 'exact')

        if len(hits) >= limit:
            return hits[:limit]

        candidates = self.db.search_rows(query, limit=400)
        # Fuzzy similarity is for suggestions only; never relabel a suggestion as exact.
        try:
            from rapidfuzz.fuzz import WRatio
        except ImportError:
            from difflib import SequenceMatcher
            similarity = lambda x: 100.0 * SequenceMatcher(None, key, normalize(x)).ratio()
        else:
            similarity = lambda x: float(WRatio(key, normalize(x)))
        scored = [(similarity(x.english), x) for x in candidates if normalize(x.english) != key]
        scored.sort(key=lambda pair: (-pair[0], -pair[1].quality, pair[1].english.casefold()))
        for score, item in scored:
            # Don't overwhelm a specialist dictionary with completely irrelevant fuzzy noise.
            if score < 45:
                continue
            append(item.english, item.persian, item.source, item.location, item.quality, 'related')
            if len(hits) >= limit:
                break
        return hits[:limit]
