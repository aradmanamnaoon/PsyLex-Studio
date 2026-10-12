"""Offline lexical retrieval evaluation and optional RAGAS API evaluation.

Example: python scripts/evaluate.py --gold tests/gold.csv
Use --ragas only after configuring evaluator LLM + embeddings and installing
`pip install -e '.[eval]'`; this can incur external API costs.
"""
from __future__ import annotations
# Allow `python scripts/evaluate.py` from the project root.
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import csv
import json
from pathlib import Path
from psylex.core.config import Settings, data_dir, bundle_dir
from psylex.core.database import Database
from psylex.core.ingest import load_jsonl
from psylex.rag.graph import TranslationPipeline


def evaluate(gold_path: Path, use_ragas: bool = False) -> dict:
    db = Database(data_dir() / 'psylex.sqlite3')
    if not db.count_entries():
        db.insert_entries(load_jsonl(bundle_dir() / 'resources' / 'starter_glossary.jsonl'))
    cfg = Settings.load()
    cfg.mode = 'dictionary'  # deterministic retrieval baseline
    engine = TranslationPipeline(db, cfg)
    with gold_path.open(encoding='utf-8-sig', newline='') as f:
        gold = list(csv.DictReader(f))
    if not gold:
        raise ValueError('Gold CSV is empty')
    correct = 0
    recall = 0
    response_rows = []
    for row in gold:
        english, expected = row['english'].strip(), row['persian'].strip()
        result = engine.translate(english, save=False)
        correct += int(result.target.strip() == expected)
        recall += int(any(e.persian == expected for e in result.evidence))
        response_rows.append({'user_input': english, 'response': result.target,
                              'reference': expected,
                              'retrieved_contexts': [f'{e.english} = {e.persian}' for e in result.evidence]})
    metrics = {'cases': len(gold), 'exact_translation_accuracy': round(correct / len(gold), 4),
               'evidence_recall_at_k': round(recall / len(gold), 4)}
    if use_ragas:
        try:
            from ragas import evaluate
            from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
            from datasets import Dataset
            ragas_result = evaluate(Dataset.from_list(response_rows),
                metrics=[faithfulness, answer_relevancy, context_precision, context_recall])
            metrics['ragas'] = str(ragas_result)
        except Exception as exc:
            metrics['ragas_error'] = str(exc)
    db.close()
    return metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gold', type=Path, default=Path('tests/gold.csv'))
    parser.add_argument('--ragas', action='store_true')
    args = parser.parse_args()
    print(json.dumps(evaluate(args.gold, args.ragas), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
