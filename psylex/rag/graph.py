"""LangGraph orchestration when available; pure-Python fallback is equivalent."""
from __future__ import annotations
from typing import Any, TypedDict
from psylex.core.config import Settings
from psylex.core.database import Database
from psylex.core.models import Evidence, Translation
from psylex.core.quality import heuristic_confidence, qa_checks
from psylex.providers.models import generate
from psylex.rag.retrieval import HybridRetriever


class GraphState(TypedDict, total=False):
    text: str
    match: str | None
    evidence: list[Evidence]
    target: str
    mode: str
    confidence: float | None
    warnings: list[str]


class TranslationPipeline:
    def __init__(self, db: Database, settings: Settings):
        self.db = db
        self.settings = settings
        self.retriever = HybridRetriever(db, settings)
        self.graph = self._compile()

    def _lookup(self, state: GraphState) -> dict[str, Any]:
        source = state['text'].strip()
        correction = self.db.correction(source)
        if correction:
            return {'match': 'human_correction', 'target': correction,
                    'evidence': [Evidence(source, correction, 'Human correction', 'translation memory',
                                          1.0, 'approved_correction')], 'confidence': 1.0}
        exact = self.db.exact(source, limit=10)
        if exact:
            best = exact[0]
            evidence = [Evidence(e.english, e.persian, e.source, e.location,
                                 e.quality, 'exact_dictionary') for e in exact]
            return {'match': 'exact_dictionary', 'target': best.persian,
                    'evidence': evidence, 'confidence': heuristic_confidence('exact_dictionary', best.quality)}
        return {'match': None, 'evidence': []}

    def _retrieve(self, state: GraphState) -> dict[str, Any]:
        text = state['text']
        if state.get('match'):
            return {}
        found = self.retriever.find_terms_in_text(text)
        # Single/short phrases also receive hybrid suggestions.
        if len(text.split()) <= 10:
            seen = {(e.english, e.persian) for e in found}
            for e in self.retriever.retrieve(text):
                if (e.english, e.persian) not in seen:
                    found.append(e)
        return {'evidence': found[:max(self.settings.retrieval_k, 8)]}

    def _translate(self, state: GraphState) -> dict[str, Any]:
        if state.get('match'):
            return {}
        text = state['text']
        evidence = state.get('evidence', [])
        if self.settings.mode == 'dictionary':
            # Fail closed: dictionary mode NEVER calls a language model, even
            # through programmatic uses of TranslationPipeline.
            return {'target': '', 'mode': 'dictionary', 'confidence': None,
                    'warnings': ['No exact dictionary entry or approved correction. '
                                 'Open Dictionary to review related entries, or switch '
                                 'to Translation for model-generated prose.']}
        context = '\n'.join(f'- {e.english} → {e.persian} [{e.source}, {e.location}]'
                            for e in evidence[:self.settings.retrieval_k])
        if self.settings.compression:
            context = context[:2400]
        examples = '\n'.join(f'{x} → {y}' for x, y in self.db.examples(text, self.settings.feedback_examples))
        prompt = self.settings.prompt.format(context=context or '(none)', examples=examples or '(none)', text=text)
        answer = generate(prompt, self.settings)
        return {'target': answer, 'mode': self.settings.translation_backend, 'confidence': None}

    def _check(self, state: GraphState) -> dict[str, Any]:
        warnings = state.get('warnings', []).copy()
        if state.get('target'):
            warnings.extend(qa_checks(state['text'], state['target'], state.get('evidence', [])))
        return {'warnings': warnings}

    def _compile(self):
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError:
            return None
        graph = StateGraph(GraphState)
        graph.add_node('lookup', self._lookup)
        graph.add_node('retrieve', self._retrieve)
        graph.add_node('translate', self._translate)
        graph.add_node('quality', self._check)
        graph.add_edge(START, 'lookup')
        graph.add_edge('lookup', 'retrieve')
        graph.add_edge('retrieve', 'translate')
        graph.add_edge('translate', 'quality')
        graph.add_edge('quality', END)
        return graph.compile()

    def translate(self, text: str, save: bool = True) -> Translation:
        text = text.strip()
        if not text:
            raise ValueError('Please enter English text to translate.')
        if len(text) > 15000:
            raise ValueError('Input exceeds 15,000 characters; use batch processing.')
        state: GraphState = {'text': text, 'mode': self.settings.mode, 'warnings': []}
        if self.graph is not None:
            state = self.graph.invoke(state)
        else:
            state.update(self._lookup(state))
            state.update(self._retrieve(state))
            state.update(self._translate(state))
            state.update(self._check(state))
        result = Translation(text, state.get('target', ''),
                             'dictionary' if state.get('match') or self.settings.mode == 'dictionary'
                             else self.settings.translation_backend,
                             state.get('confidence'), state.get('evidence', []), state.get('warnings', []))
        if save:
            result.id = self.db.save_translation(result)
        return result
