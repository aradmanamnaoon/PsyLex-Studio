"""CER/WER evaluation of scanned-PDF or image OCR against human transcripts.

python -m scripts.evaluate_document_ocr samples/document_fixtures/ocr_gold.jsonl
Exit 1 when CER exceeds --max-cer. No accuracy claims without real-world gold data.
"""
from __future__ import annotations
import argparse
import json
import re
import unicodedata
from pathlib import Path
from psylex.core.documents import load_document


def distance(ref: list[str], hypothesis: list[str]) -> int:
    """Space-optimized Levenshtein distance; O(n*m) time and O(m) memory."""
    previous=list(range(len(hypothesis)+1))
    for i, token in enumerate(ref,1):
        current=[i]
        for j, item in enumerate(hypothesis,1):
            current.append(min(current[-1]+1,previous[j]+1,
                               previous[j-1]+(token!=item)))
        previous=current
    return previous[-1]


def normalize(text: str) -> str:
    return ' '.join(re.sub(r'\s+', ' ', unicodedata.normalize('NFKC',text)).lower().split())


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument('manifest',type=Path)
    parser.add_argument('--ocr-engine',choices=['rapidocr','paddle'],default='rapidocr')
    parser.add_argument('--require-native', action='store_true',
                        help='Fail rather than using a Tesseract fallback when RapidOCR is unavailable')
    parser.add_argument('--max-cer',type=float,default=0.10,
                        help='Exit nonzero if pooled character error rate exceeds this value')
    parser.add_argument('--report',type=Path,default=None)
    args=parser.parse_args()
    from importlib.util import find_spec
    has_rapidocr = find_spec('rapidocr_onnxruntime') is not None
    if args.require_native and args.ocr_engine == 'rapidocr' and not has_rapidocr:
        print('ERROR: rapidocr_onnxruntime is missing; install requirements first.')
        return 2
    total_chars=total_words=bad_chars=bad_words=0
    rows=[]
    for line in args.manifest.read_text(encoding='utf-8').splitlines():
        if not line.strip(): continue
        case=json.loads(line)
        path=(args.manifest.parent/case['file']).resolve()
        reference=normalize(case['reference'])
        document=load_document(path,ocr_engine=args.ocr_engine,ocr_mode='always')
        prediction=normalize(' '.join(block.text for block in document.blocks))
        ref_chars=list(reference);hyp_chars=list(prediction)
        ref_words=reference.split();hyp_words=prediction.split()
        char_errors=distance(ref_chars,hyp_chars)
        word_errors=distance(ref_words,hyp_words)
        total_chars+=len(ref_chars);total_words+=len(ref_words)
        bad_chars+=char_errors;bad_words+=word_errors
        rows.append({'file':str(path),'reference':reference,'prediction':prediction,
                     'cer':char_errors/max(1,len(ref_chars)),
                     'wer':word_errors/max(1,len(ref_words))})
    pooled={'cases':len(rows),'engine_requested':args.ocr_engine,
            'rapidocr_native_available':has_rapidocr,
            'fallback_used':args.ocr_engine=='rapidocr' and not has_rapidocr,
            'cer':bad_chars/max(1,total_chars),'wer':bad_words/max(1,total_words),
            'note':'Evaluate on representative real scans before making quality claims.', 'cases_detail':rows}
    print(json.dumps(pooled,ensure_ascii=False,indent=2))
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(pooled,ensure_ascii=False,indent=2),encoding='utf-8')
    return 1 if not rows or pooled['cer']>args.max_cer else 0


if __name__=='__main__':
    raise SystemExit(main())
