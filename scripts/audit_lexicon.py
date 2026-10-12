"""Audit converted bilingual DOCX entries for suspicious OCR / alignment artifacts.

Does not change lexicon data; export and human-review candidates before release.
"""
from __future__ import annotations
import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def flags(entry: dict) -> list[str]:
    en = str(entry.get("english", ""))
    fa = str(entry.get("persian", ""))
    reasons = []
    if re.search(r"[A-Za-z]{3,}", fa):
        reasons.append("latin_word_in_persian")
    if re.search(r"[\u0600-\u06ff]", en):
        reasons.append("persian_in_english")
    if len(en.split()) > 7:
        reasons.append("long_english_headword")
    if re.search(r"[()\[\]]", en + fa) and (en.count("(") != en.count(")") or fa.count("(") != fa.count(")")):
        reasons.append("unbalanced_parentheses")
    if len(fa.strip()) < 3:
        reasons.append("short_translation")
    if float(entry.get("quality", 0)) < 0.75:
        reasons.append("low_extraction_score")
    return reasons

def audit(lexicon: Path, output: Path) -> dict:
    summary: Counter[str] = Counter()
    count = 0
    output.parent.mkdir(parents=True, exist_ok=True)
    with lexicon.open(encoding="utf-8") as f, output.open("w", encoding="utf-8-sig", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["english", "persian", "source", "location", "quality", "flags"])
        for line in f:
            row = json.loads(line)
            count += 1
            reasons = flags(row)
            if reasons:
                for r in reasons:
                    summary[r] += 1
                writer.writerow([row.get(k, "") for k in ("english", "persian", "source", "location", "quality")] + [";".join(reasons)])
    return {"entries": count, "flagged_by_rule": dict(summary), "csv": str(output)}

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lexicon", type=Path, default=ROOT / "resources" / "lexicon.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "build" / "lexicon_audit.csv")
    args = parser.parse_args()
    print(json.dumps(audit(args.lexicon, args.output), indent=2))

if __name__ == "__main__":
    main()
