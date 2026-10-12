"""Non-sensitive per-user marker for first-launch local model setup."""
from __future__ import annotations

import json
from pathlib import Path

from psylex.core.config import data_dir

MARKER_FILE = "first_launch_local_model_setup.v1.json"


def marker_path(location: Path | None = None) -> Path:
    return (location if location is not None else data_dir()) / MARKER_FILE


def needs_model_setup(location: Path | None = None) -> bool:
    """Fresh user profiles get one optional setup prompt; no user DB changes."""
    return not marker_path(location).is_file()


def mark_model_setup_finished(outcome: str, location: Path | None = None) -> None:
    """Remember explicit setup or Skip; never persist credentials here."""
    if outcome not in {"configured", "skipped"}:
        raise ValueError("Unknown local model setup outcome")
    path = marker_path(location)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps({"version": 1, "outcome": outcome}, indent=2), encoding="utf-8")
    tmp.replace(path)
