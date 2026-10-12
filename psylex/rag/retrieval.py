"""Deterministic exact-first hybrid term retrieval with optional dense index."""
from __future__ import annotations
import math
import re
from collections import Counter
from pathlib import Path
from typing import Iterable
from psylex.core.config import Settings, data_dir
from psylex.core.database import Database, normalize
from psylex.core.models import DictionaryEntry, Evidence

WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*(?:\s+[A-Za-z][A-Za-z'’-]*)*")


def lexical_tokens(s: str) -> list[str]:
    return re.findall(r"[a-z]+(?:'[a-z]+)?", normalize(s))


class HybridRetriever:
    """Merge lexical, fuzzy, and optional dense results by reciprocal rank.

    Exact matches and reviewed corrections are handled before this component.
    Vector indexing is explicitly opt-in because initial model downloads may be
    large and require user consent/network access.
    """
    def __init__(self, db: Database, settings: Settings):
        self.db = db
        self.settings = settings
        self._vector = None
        self._reranker = None

    def _sparse(self, query: str, candidates: list[DictionaryEntry]) -> list[tuple[DictionaryEntry, float]]:
        terms = lexical_tokens(query)
        if not terms or not candidates:
            return []
        docs = [lexical_tokens(e.english) for e in candidates]
        try:
            from rank_bm25 import BM25Okapi
            bm25 = BM25Okapi(docs)
            scores = bm25.get_scores(terms)
            return sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
        except ImportError:
            n = len(docs)
            df = Counter(t for row in docs for t in set(row))
            result = []
            for e, tokens in zip(candidates, docs):
                tf = Counter(tokens)
                score = sum(tf[t] * math.log(1 + n / (1 + df[t])) for t in terms)
                result.append((e, score))
            return sorted(result, key=lambda x: x[1], reverse=True)

    def _fuzzy(self, query: str, candidates: list[DictionaryEntry]) -> list[tuple[DictionaryEntry, float]]:
        try:
            from rapidfuzz.fuzz import WRatio
            score = lambda s: WRatio(query.casefold(), s.casefold()) / 100
        except ImportError:
            from difflib import SequenceMatcher
            score = lambda s: SequenceMatcher(None, query.casefold(), s.casefold()).ratio()
        return sorted(((e, score(e.english)) for e in candidates), key=lambda x: x[1], reverse=True)

    def build_vectors(self, entries: list[DictionaryEntry] | None = None) -> int:
        """Build Chroma persistently using installed sentence-transformers model.

        Optional dependency; use a multilingual model for English-Persian data.
        """
        try:
            from langchain_chroma import Chroma
            from langchain_huggingface import HuggingFaceEmbeddings
            from langchain_core.documents import Document
        except ImportError as exc:
            raise RuntimeError("Install pip install -e '.[rag]' to enable vector search.") from exc
        entries = entries or self.db.all_entries()
        if not entries:
            return 0
        embeddings = HuggingFaceEmbeddings(model_name=self.settings.embedding_model)
        directory = data_dir() / 'vectors'
        directory.mkdir(parents=True, exist_ok=True)
        store = Chroma(collection_name='psylex', embedding_function=embeddings,
                       persist_directory=str(directory))
        # Deterministic ids permit repeat imports without duplicating rows.
        import hashlib
        batch_size = 128
        for i in range(0, len(entries), batch_size):
            chunk = entries[i:i+batch_size]
            docs = [Document(page_content=f"{e.english} = {e.persian}",
                             metadata={'english': e.english, 'persian': e.persian,
                                       'source': e.source, 'location': e.location}) for e in chunk]
            ids = [hashlib.sha256(f"{e.english}|{e.persian}|{e.source}|{e.location}".encode()).hexdigest()
                   for e in chunk]
            store.add_documents(docs, ids=ids)
        self._vector = store
        return len(entries)

    def _dense(self, query: str, k: int) -> list[Evidence]:
        if not self.settings.vector_enabled:
            return []
        if self._vector is None:
            try:
                from langchain_chroma import Chroma
                from langchain_huggingface import HuggingFaceEmbeddings
                if not (data_dir() / 'vectors' / 'chroma.sqlite3').exists():
                    return []
                emb = HuggingFaceEmbeddings(model_name=self.settings.embedding_model)
                self._vector = Chroma(collection_name='psylex', embedding_function=emb,
                                      persist_directory=str(data_dir() / 'vectors'))
            except (ImportError, OSError):
                return []
        rows = self._vector.similarity_search_with_relevance_scores(query, k=k)
        return [Evidence(str(d.metadata.get('english', '')), str(d.metadata.get('persian', '')),
                         str(d.metadata.get('source', '')), str(d.metadata.get('location', '')),
                         max(0.0, min(float(score), 1.0)), 'vector') for d, score in rows]

    def retrieve(self, query: str, k: int | None = None) -> list[Evidence]:
        k = k or self.settings.retrieval_k
        exact = self.db.exact(query, limit=k)
        if exact:
            return [Evidence(e.english, e.persian, e.source, e.location,
                             e.quality, 'exact_dictionary', e.context) for e in exact]
        candidates = self.db.search_rows(query, limit=350)
        if self.settings.multi_query:
            # Deterministic spelling/number variants; no unexpected model calls.
            variants = {query.replace('-', ' '), query.replace(' ', '-'),
                        query.removesuffix('s'), query.replace('behavioral', 'behavioural'),
                        query.replace('behavioural', 'behavioral')}
            seen_candidates = {(e.english, e.persian, e.location) for e in candidates}
            for variant in variants - {query}:
                if not variant.strip():
                    continue
                for item in self.db.search_rows(variant, limit=100):
                    key = (item.english, item.persian, item.location)
                    if key not in seen_candidates:
                        candidates.append(item)
                        seen_candidates.add(key)
        if not candidates and not self.settings.vector_enabled:
            return []
        rankings: dict[tuple[str, str, str], dict] = {}
        weights = {'bm25': self.settings.bm25_weight, 'fuzzy': self.settings.fuzzy_weight,
                   'vector': self.settings.vector_weight}
        for strategy, ranked in [('bm25', self._sparse(query, candidates)),
                                 ('fuzzy', self._fuzzy(query, candidates))]:
            for rank, (entry, score) in enumerate(ranked[:60], 1):
                if strategy == 'bm25' and score <= 0:
                    continue
                if strategy == 'fuzzy' and score < .35:
                    continue
                key = (entry.english, entry.persian, entry.location)
                item = rankings.setdefault(key, {'entry': entry, 'rrf': 0., 'raw': 0., 'methods': set()})
                item['rrf'] += weights[strategy] / (40 + rank)
                item['raw'] = max(item['raw'], float(min(score / 8, 1)) if strategy == 'bm25' else float(score))
                item['methods'].add(strategy)
        try:
            dense = self._dense(query, k * 2)
        except Exception:
            dense = []  # A missing/corrupt index must not disable dictionary lookup.
        for rank, e in enumerate(dense, 1):
            key = (e.english, e.persian, e.location)
            item = rankings.setdefault(key, {'entry': DictionaryEntry(e.english, e.persian, e.source,
                                             e.location, e.score), 'rrf': 0., 'raw': 0., 'methods': set()})
            item['rrf'] += weights['vector'] / (40 + rank)
            item['raw'] = max(item['raw'], e.score)
            item['methods'].add('vector')
        ordered = sorted(rankings.values(), key=lambda v: v['rrf'], reverse=True)
        results = [Evidence(v['entry'].english, v['entry'].persian, v['entry'].source,
                            v['entry'].location, round(max(0., min(v['raw'] * v['entry'].quality, 1.)), 3),
                            '+'.join(sorted(v['methods'])), v['entry'].context) for v in ordered[:max(k, 10)]]
        if self.settings.reranker_model and results:
            try:
                from sentence_transformers import CrossEncoder
                if self._reranker is None:
                    self._reranker = CrossEncoder(self.settings.reranker_model)
                pairs = [[query, e.english + ' = ' + e.persian] for e in results]
                scores = self._reranker.predict(pairs)
                results = [e for _, e in sorted(zip(scores, results), key=lambda v: v[0], reverse=True)]
            except Exception:
                pass
        return results[:k]

    def find_terms_in_text(self, text: str, max_terms: int = 20) -> list[Evidence]:
        """Longest-match scan; useful for consistent terminology in paragraphs."""
        words = list(re.finditer(r"[A-Za-z][A-Za-z'-]*", text))
        matches: list[Evidence] = []
        occupied: set[int] = set()
        for width in range(min(7, len(words)), 0, -1):
            for i in range(len(words) - width + 1):
                if any(j in occupied for j in range(i, i + width)):
                    continue
                first, last = words[i], words[i + width - 1]
                phrase = text[first.start():last.end()]
                exact = self.db.exact(phrase, 1)
                if exact:
                    e = exact[0]
                    correction = self.db.correction(phrase)
                    matches.append(Evidence(e.english, correction or e.persian, e.source if not correction
                                            else 'Human correction', e.location, 1.0 if correction else e.quality,
                                            'correction' if correction else 'exact_dictionary'))
                    occupied.update(range(i, i + width))
                    if len(matches) >= max_terms:
                        return matches
        return matches
