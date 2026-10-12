"""Human-readable terminology QA; flags are warnings, not proof of mistranslation."""
from __future__ import annotations
import re
from psylex.core.models import Evidence


def qa_checks(source: str, target: str, evidence: list[Evidence]) -> list[str]:
    warnings = []
    if not target.strip():
        return ['No translation was produced.']
    numbers_src = re.findall(r"\d+(?:[.,]\d+)?", source)
    numbers_dst = re.findall(r"\d+(?:[.,]\d+)?", target.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')))
    if sorted(numbers_src) != sorted(numbers_dst):
        warnings.append('Check numbers: numeric tokens differ between input and output.')
    if len(source) >= 30 and not re.search(r'[\u0600-\u06FF]', target):
        warnings.append('Output contains no Persian script; translation may be incomplete.')
    for e in evidence[:10]:
        if len(e.english.split()) >= 2 and e.english.casefold() in source.casefold():
            if e.persian and e.persian not in target:
                warnings.append(f"Review terminology: {e.english} → {e.persian}")
    return warnings[:12]


def heuristic_confidence(strategy: str, score: float | None = None) -> float | None:
    """Retrieval heuristic, deliberately not a calibrated model probability."""
    if strategy == 'human_correction':
        return 1.0  # exact user-approved memory match, NOT a correctness probability
    if strategy == 'exact_dictionary':
        return round(min(.98, max(.6, score or .7)), 2)
    return None  # No probabilistic confidence for open-ended LLM outputs.
