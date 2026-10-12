"""Typed, UI-independent translation entities."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Literal


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(slots=True)
class DictionaryEntry:
    english: str
    persian: str
    source: str
    location: str
    quality: float = 0.75
    context: str = ""
    id: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class Evidence:
    english: str
    persian: str
    source: str
    location: str
    score: float
    strategy: str
    context: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class Translation:
    source: str
    target: str
    mode: str
    confidence: float | None
    evidence: list[Evidence] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    id: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class Feedback:
    source: str
    proposed: str
    accepted: bool
    correction: str = ""
    created_at: str = field(default_factory=utc_now)


Mode = Literal["dictionary", "translation"]
