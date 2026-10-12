"""Release assurance: file round trips, OCR providers, secrets, and no-cloud defaults.

All network tests are mocks: they do NOT validate vendor credentials or live APIs.
"""
from __future__ import annotations

import ast
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from psylex.core.config import Settings
from psylex.core.database import Database
from psylex.core.dictionary import DictionaryService
from psylex.core.documents import DocumentData, TextBlock, load_document, save_document, translate_document
from psylex.core.models import DictionaryEntry, Feedback
from psylex.core.ocr import OCRConfig, ALL_OCR_ENGINES, run_ocr
from psylex.rag.graph import TranslationPipeline


@pytest.fixture
def sample_image():
    return Image.new('RGB', (120, 45), '#ffffff')


class FakeTranslation:
    def __init__(self, text):
        self.target = f'ترجمه: {text}'
        self.warnings = []


class FakeTranslator:
    def translate(self, text, save=True):
        return FakeTranslation(text)


@pytest.mark.parametrize('ext', ['.txt', '.md', '.html', '.json', '.jsonl', '.csv', '.tsv', '.docx'])
def test_document_export_then_inspect(tmp_path, ext):
    source = tmp_path / 'original.txt'
    source.write_text('Psychology research\n\nWorking memory', encoding='utf-8')
    doc = load_document(source)
    result = translate_document(doc, FakeTranslator())
    dest = tmp_path / f'export{ext}'
    assert save_document(result, dest) == dest
    assert dest.stat().st_size > 0
    if ext == '.docx':
        from docx import Document
        assert any('ترجمه' in p.text for p in Document(dest).paragraphs)
    elif ext in {'.json', '.jsonl'}:
        serialized = dest.read_text(encoding='utf-8')
        assert 'ترجمه' in serialized
    else:
        assert 'ترجمه' in dest.read_text(encoding='utf-8-sig')
    # Existing source must never be overwritten.
    assert source.read_text(encoding='utf-8') == 'Psychology research\n\nWorking memory'


def test_source_overwrite_rejected_even_same_path(tmp_path):
    source = tmp_path / 'source.txt'
    source.write_text('Original', encoding='utf-8')
    doc = DocumentData(str(source), '.txt', [TextBlock('Original', translated='اصلی')])
    with pytest.raises(ValueError, match='overwrite'):
        save_document(doc, source)
    assert source.read_text(encoding='utf-8') == 'Original'


def test_dictionary_correction_survives_database_reopen(tmp_path):
    db_path = tmp_path / 'dict.db'
    db = Database(db_path)
    db.insert_entries([DictionaryEntry('attention', 'توجه', 'dictionary.docx', 'row 3', .98)])
    db.record_feedback(Feedback('attention', 'توجه', False, 'دقت'))
    db.close()
    reopened = Database(db_path)
    try:
        hits = DictionaryService(reopened).search('ATTENTION')
        assert hits[0].kind == 'approved'
        assert hits[0].persian == 'دقت'
        assert any(h.persian == 'توجه' and h.kind == 'exact' for h in hits)
    finally:
        reopened.close()


def test_dictionary_never_calls_cloud_model(tmp_path, monkeypatch):
    import psylex.rag.graph as graph
    monkeypatch.setattr(graph, 'generate', lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('cloud called')))
    db = Database(tmp_path / 'database.sqlite3')
    try:
        cfg = Settings(mode='dictionary')
        pipeline = TranslationPipeline(db, cfg)
        result = pipeline.translate('unknown niche term', save=False)
        assert result.target == ''
        assert result.warnings
    finally:
        db.close()


def test_ocr_api_key_not_written_in_settings_json(tmp_path, monkeypatch):
    import psylex.core.config as config
    stored = {}
    monkeypatch.setattr(config, '_keyring_store', lambda field, value: stored.__setitem__(field, value))
    monkeypatch.setattr(config, '_keyring_get', lambda field: stored.get(field, ''))
    p = tmp_path / 'prefs.json'
    cfg = Settings(ocrspace_api_key='test-key-SECRET-123', google_vision_api_key='another-SECRET')
    cfg.save(p)
    persisted = p.read_text(encoding='utf-8')
    assert 'SECRET' not in persisted
    assert 'ocrspace_api_key' not in persisted
    reopened = Settings.load(p)
    assert reopened.ocrspace_api_key == 'test-key-SECRET-123'
    assert reopened.google_vision_api_key == 'another-SECRET'


def test_legacy_cloud_key_migrates_on_save(tmp_path, monkeypatch):
    import psylex.core.config as config
    stored = {}
    monkeypatch.setattr(config, '_keyring_store', lambda field, value: stored.__setitem__(field, value))
    monkeypatch.setattr(config, '_keyring_get', lambda field: stored.get(field, ''))
    p = tmp_path / 'prefs.json'
    p.write_text(json.dumps({'mode': 'api', 'ocrspace_api_key': 'legacy-test-secret'}), encoding='utf-8')
    loaded = Settings.load(p)
    assert loaded.mode == 'translation'
    loaded.save(p)
    assert 'legacy-test-secret' not in p.read_text(encoding='utf-8')
    assert stored['ocrspace_api_key'] == 'legacy-test-secret'


def test_credential_save_fails_closed(tmp_path, monkeypatch):
    import psylex.core.config as config
    monkeypatch.setattr(config, '_keyring_store', lambda *args: (_ for _ in ()).throw(RuntimeError('no keyring')))
    p = tmp_path / 'prefs.json'
    p.write_text('SAFE ORIGINAL', encoding='utf-8')
    with pytest.raises(RuntimeError, match='no keyring'):
        Settings(ocrspace_api_key='SECRET').save(p)
    assert p.read_text(encoding='utf-8') == 'SAFE ORIGINAL'


def test_unconfigured_cloud_providers_fail_without_upload(sample_image, monkeypatch):
    import psylex.core.ocr as ocr
    monkeypatch.setattr(ocr, '_require_requests', lambda: (_ for _ in ()).throw(AssertionError('unexpected upload')))
    for engine in ('ocrspace', 'google_vision', 'azure_di', 'mathpix', 'mistral_ocr'):
        with pytest.raises(RuntimeError, match='Set '):
            run_ocr(sample_image, engine, OCRConfig())


def test_cloud_error_redacts_secret_in_exception(sample_image, monkeypatch):
    import psylex.core.ocr as ocr
    secret = 'test-secret-should-not-leak'
    def bad_request(*args, **kwargs):
        raise RuntimeError(f'Bad response from https://example.com/?key={secret}')
    monkeypatch.setattr(ocr, '_require_requests', lambda: SimpleNamespace(post=bad_request))
    with pytest.raises(RuntimeError) as exc:
        run_ocr(sample_image, 'google_vision', OCRConfig(google_vision_api_key=secret))
    assert secret not in str(exc.value)
    assert '[REDACTED]' in str(exc.value)


def test_ocrspace_response_parsing(sample_image, monkeypatch):
    import psylex.core.ocr as ocr
    calls = []
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'IsErroredOnProcessing': False, 'ParsedResults': [{'ParsedText': 'Working memory\n'}]}
    def send(*args, **kwargs):
        calls.append((args, kwargs))
        return Response()
    monkeypatch.setattr(ocr, '_require_requests', lambda: SimpleNamespace(post=send))
    assert run_ocr(sample_image, 'ocrspace', OCRConfig(ocrspace_api_key='mykey')) == 'Working memory'
    assert calls and calls[0][1]['timeout'] > 0


def test_google_vision_response_parsing(sample_image, monkeypatch):
    import psylex.core.ocr as ocr
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'responses': [{'fullTextAnnotation': {'text': 'Cognitive psychology\n'}}]}
    monkeypatch.setattr(ocr, '_require_requests', lambda: SimpleNamespace(post=lambda *a, **kw: Response()))
    assert run_ocr(sample_image, 'google_vision', OCRConfig(google_vision_api_key='key')) == 'Cognitive psychology'


def test_mistral_response_parsing(sample_image, monkeypatch):
    import psylex.core.ocr as ocr
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'pages': [{'markdown': 'Psychological assessment'}]}
    monkeypatch.setattr(ocr, '_require_requests', lambda: SimpleNamespace(post=lambda *a, **kw: Response()))
    assert run_ocr(sample_image, 'mistral_ocr', OCRConfig(mistral_api_key='key')) == 'Psychological assessment'


def test_pdf_mixed_embedded_text_and_ocr(tmp_path, monkeypatch):
    import fitz
    import psylex.core.documents as documents
    ocr_calls = []
    def pretend_ocr(image, engine, settings=None):
        ocr_calls.append(engine)
        return 'Working memory on scanned page'
    monkeypatch.setattr(documents, '_ocr_image', pretend_ocr)
    p = tmp_path / 'mixed.pdf'
    pdf = fitz.open()
    first = pdf.new_page()
    first.insert_text((70, 70), 'Psychology is a field of scientific research and practice.')
    second = pdf.new_page()
    pix = Image.new('RGB', (300, 100), 'white')
    buf = io.BytesIO(); pix.save(buf, format='PNG')
    second.insert_image(fitz.Rect(0, 0, 200, 80), stream=buf.getvalue())
    pdf.save(p); pdf.close()
    doc = load_document(p, ocr_engine='rapidocr', ocr_mode='auto')
    assert len(ocr_calls) == 1
    assert any(b.page == 1 and not b.ocr for b in doc.blocks)
    assert any(b.page == 2 and b.ocr for b in doc.blocks)


def test_empty_scanned_pdf_does_not_hallucinate(tmp_path, monkeypatch):
    import fitz
    import psylex.core.documents as documents
    monkeypatch.setattr(documents, '_ocr_image', lambda *a, **k: '')
    p = tmp_path / 'empty.pdf'
    pdf = fitz.open(); pdf.new_page(); pdf.save(p); pdf.close()
    with pytest.raises(ValueError, match='No readable text'):
        load_document(p, ocr_engine='rapidocr', ocr_mode='auto')


def test_ui_connected_signal_target_methods_exist():
    """Catches missing-method regressions without importing Qt on Linux."""
    root = Path(__file__).resolve().parents[1] / 'psylex/ui'
    for name in ('main_window.py', 'settings_dialog.py'):
        tree = ast.parse((root / name).read_text(encoding='utf-8'))
        classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
        cls = classes['MainWindow' if name == 'main_window.py' else 'SettingsDialog']
        methods = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
        # Connects using self._method must resolve to a method.
        for node in ast.walk(cls):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'connect':
                for arg in node.args:
                    if isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name) and arg.value.id == 'self':
                        if arg.attr.startswith('_'):
                            assert arg.attr in methods, f'{name}: missing {arg.attr}'


def test_failed_translation_preserves_previous_document_review_edits():
    class FailOnSecond:
        def __init__(self): self.count = 0
        def translate(self, text, save=False):
            self.count += 1
            if self.count == 2:
                raise RuntimeError('simulated provider failure')
            return SimpleNamespace(target='جدید', warnings=[])
    doc = DocumentData('a.txt', '.txt', [
        TextBlock('First', translated='ویرایش تایید شده'),
        TextBlock('Second', translated='ویرایش دوم'),
    ])
    with pytest.raises(RuntimeError, match='simulated provider failure'):
        translate_document(doc, FailOnSecond())
    assert [b.translated for b in doc.blocks] == ['ویرایش تایید شده', 'ویرایش دوم']


def test_cancelled_translation_preserves_previous_document_review_edits():
    class CancelAfterOne:
        def __init__(self): self.count=0
        def translate(self, text, save=False):
            self.count+=1
            return SimpleNamespace(target='ترجمه', warnings=[])
    backend=CancelAfterOne()
    doc = DocumentData('a.txt', '.txt', [TextBlock('one', translated='اول'), TextBlock('two', translated='دوم')])
    with pytest.raises(InterruptedError):
        translate_document(doc, backend, is_cancelled=lambda:backend.count>=1)
    assert [b.translated for b in doc.blocks] == ['اول', 'دوم']


def test_document_export_prompts_for_unapplied_edit():
    path = Path(__file__).resolve().parents[1] / 'psylex/ui/main_window.py'
    code = path.read_text(encoding='utf-8')
    body = code.split('def _document_export(self) -> None:', 1)[1].split('\n    def ', 1)[0]
    assert 'Unsaved document correction' in body
    assert 'self._document_apply_edit()' in body
    assert 'QMessageBox.StandardButton.Cancel' in body


def test_packaged_self_test_report_written_without_qt(tmp_path):
    from main import packaged_self_test
    report = tmp_path / 'package-check.json'
    result = packaged_self_test(report, require_native_ocr=False)
    payload = json.loads(report.read_text(encoding='utf-8'))
    assert result == 0
    assert payload['result'] == 'PASS'
    assert payload['checks']['lexicon_present']
    assert payload['checks']['dictionary_lookup']


def test_azure_response_polling(sample_image, monkeypatch):
    import psylex.core.ocr as ocr
    class Start:
        headers={'operation-location':'https://example.invalid/operation/1'}
        def raise_for_status(self): pass
    class Finished:
        def raise_for_status(self): pass
        def json(self): return {'status':'succeeded','analyzeResult':{'pages':[{'lines':[{'content':'Working memory'}]}]}}
    def fake_post(*args, **kwargs): return Start()
    def fake_get(*args, **kwargs): return Finished()
    monkeypatch.setattr(ocr, '_require_requests', lambda: SimpleNamespace(post=fake_post, get=fake_get))
    cfg = OCRConfig(azure_document_endpoint='https://fake.cognitiveservices.azure.com',azure_document_key='key')
    assert run_ocr(sample_image, 'azure_di', cfg) == 'Working memory'


def test_mathpix_ocr_response_parsing(sample_image, monkeypatch):
    import psylex.core.ocr as ocr
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'text':'Clinical intervention'}
    monkeypatch.setattr(ocr, '_require_requests', lambda: SimpleNamespace(post=lambda *a, **k: Response()))
    cfg = OCRConfig(mathpix_app_id='id', mathpix_app_key='key')
    assert run_ocr(sample_image, 'mathpix', cfg) == 'Clinical intervention'


def test_aws_textract_line_parsing(sample_image, monkeypatch):
    class Client:
        def detect_document_text(self, **kwargs):
            assert kwargs['Document']['Bytes']
            return {'Blocks':[{'BlockType':'LINE','Text':'Psychological assessment'},
                              {'BlockType':'WORD','Text':'ignored'}]}
    fake_boto3 = SimpleNamespace(client=lambda *a, **k: Client())
    monkeypatch.setitem(sys.modules, 'boto3', fake_boto3)
    assert run_ocr(sample_image, 'aws_textract', OCRConfig()) == 'Psychological assessment'


def test_rapidocr_model_result_parsing(sample_image, monkeypatch):
    import psylex.core.ocr as ocr
    class RapidOCR:
        def __call__(self, image):
            assert image[:8] == b'\x89PNG\r\n\x1a\n'
            return [[[[0, 0], [10, 0], [10, 20], [0, 20]], 'Cognitive therapy', .99]], 0.12
    if hasattr(ocr._rapidocr, '_engine'):
        monkeypatch.delattr(ocr._rapidocr, '_engine')
    monkeypatch.setitem(sys.modules, 'rapidocr_onnxruntime', SimpleNamespace(RapidOCR=RapidOCR))
    assert run_ocr(sample_image, 'rapidocr') == 'Cognitive therapy'
    if hasattr(ocr._rapidocr, '_engine'):
        monkeypatch.delattr(ocr._rapidocr, '_engine')


def test_ocr_catalog_has_documented_engines():
    assert {'rapidocr', 'paddle', 'ocrspace', 'google_vision', 'azure_di', 'aws_textract',
            'mathpix', 'mistral_ocr'} == set(ALL_OCR_ENGINES)


def test_manual_scoring_detects_missing_numeric_values():
    from scripts.score_manual_translation import analyze
    cases = [{'id': 'A', 'category': 'stats', 'input': 'Accuracy 71% then 83%.', 'review_notes': 'check numbers'}]
    good = analyze(cases, [{'id':'A','output':'دقت ابتدا 71% و سپس 83% بود.'}])
    bad = analyze(cases, [{'id':'A','output':'دقت ابتدا 71% بود.'}])
    assert good['results'][0]['missing_numeric_tokens'] == []
    assert bad['results'][0]['missing_numeric_tokens'] == ['83%']
    assert good['results'][0]['needs_human_semantic_review']
