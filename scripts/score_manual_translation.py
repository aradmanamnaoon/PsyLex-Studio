"""Non-semantic QA for user-reviewed translation outputs.

Does NOT score correctness or clinical quality. Expert review is mandatory.
Usage: python scripts/score_manual_translation.py samples/evaluation/answers_template.jsonl
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

PERSIAN = re.compile(r'[\u0600-\u06ff]')
NUMBER = re.compile(r'(?<!\w)\d+(?:\.\d+)?%?(?!\w)')


def analyze(inputs: list[dict], answers: list[dict]) -> dict:
    indexed = {row['id']:row for row in answers}
    results=[]
    for case in inputs:
        response=indexed.get(case['id'], {})
        output=str(response.get('output','')).strip()
        required=NUMBER.findall(case['input'])
        observed=NUMBER.findall(output)
        missing=[]
        remainder=observed[:]
        for token in required:
            if token in remainder:
                remainder.remove(token)
            else:
                missing.append(token)
        results.append({'id':case['id'],'category':case['category'],
                        'has_output':bool(output), 'persian_present':bool(PERSIAN.search(output)),
                        'missing_numeric_tokens':missing,'review_notes':case['review_notes'],
                        'needs_human_semantic_review':True})
    return {'cases':len(results),'completed':sum(x['has_output'] for x in results),
            'number_preservation_checks_passed':sum(x['has_output'] and not x['missing_numeric_tokens'] for x in results),
            'note':'This is a deterministic formatting/numerical QA tool, NOT a translation accuracy grade.',
            'results':results}


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument('answers',type=Path)
    parser.add_argument('--cases',type=Path,default=Path(__file__).resolve().parents[1]/'samples/evaluation/manual_translation_cases.jsonl')
    parser.add_argument('--report',type=Path,default=None)
    args=parser.parse_args()
    cases=[json.loads(line) for line in args.cases.read_text(encoding='utf-8').splitlines() if line.strip()]
    answers=[json.loads(line) for line in args.answers.read_text(encoding='utf-8').splitlines() if line.strip()]
    report=analyze(cases,answers)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
