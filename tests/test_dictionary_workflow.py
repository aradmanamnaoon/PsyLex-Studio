"""Tests for dictionary lookup, backend separation, and backwards compatibility."""
import json

from psylex.core.config import Settings
from psylex.core.database import Database
from psylex.core.dictionary import DictionaryService
from psylex.core.models import DictionaryEntry, Feedback
from psylex.rag.graph import TranslationPipeline


def test_exact_dictionary_has_source_and_variants(tmp_path):
    db = Database(tmp_path / 'dictionary.db')
    try:
        db.insert_entries([
            DictionaryEntry('working memory', 'حافظهٔ کاری', 'a.docx', 'row 12', .99),
            DictionaryEntry('working memory', 'حافظهٔ فعال', 'b.docx', 'row 9', .81),
            DictionaryEntry('working model', 'مدل کاری', 'a.docx', 'row 13', .87),
        ])
        service = DictionaryService(db)
        hits = service.search('WORKING memory')
        assert len(hits) >= 2
        assert hits[0].persian == 'حافظهٔ کاری'
        assert hits[0].source == 'a.docx'
        assert hits[0].location == 'row 12'
        assert hits[0].kind == 'exact'
        assert hits[1].kind == 'exact'
        assert len([x for x in hits if x.kind == 'exact']) == 2
        assert not service.search(' ')
    finally:
        db.close()


def test_user_correction_overrides_without_deleting_source(tmp_path):
    db = Database(tmp_path / 'dictionary.db')
    try:
        db.insert_entries([DictionaryEntry('attention', 'توجه', 'a.docx', 'row 1', .95)])
        db.record_feedback(Feedback('attention', 'توجه', False, 'دقت'))
        hits = DictionaryService(db).search('attention')
        assert hits[0].kind == 'approved'
        assert hits[0].persian == 'دقت'
        assert any(hit.persian == 'توجه' and hit.kind == 'exact' for hit in hits)
    finally:
        db.close()


def test_config_migrates_old_modes(tmp_path):
    for old_mode in ('local', 'api'):
        path = tmp_path / 'settings.json'
        path.write_text(json.dumps({'mode': old_mode, 'provider': 'Ollama' if old_mode == 'local' else 'OpenAI',
                                    'model': 'custom/model'}), encoding='utf-8')
        cfg = Settings.load(path)
        assert cfg.mode == 'translation'
        assert cfg.translation_backend == old_mode
        assert cfg.model == 'custom/model'
        cfg.validate()
        cfg.save(path)
        reloaded = Settings.load(path)
        assert reloaded.translation_backend == old_mode
        assert reloaded.mode == 'translation'


def test_separate_modes_and_backend_settings():
    cfg = Settings()
    assert cfg.mode == 'dictionary'
    assert cfg.translation_backend == 'local'
    cfg.mode = 'translation'
    cfg.translation_backend = 'api'
    cfg.validate()


def test_translation_uses_configured_backend_with_mock_llm(tmp_path, monkeypatch):
    db = Database(tmp_path / 'translation.db')
    try:
        import psylex.rag.graph as graph
        output = []
        def fake_generate(prompt, cfg):
            output.append((prompt, cfg.translation_backend))
            return 'شرکت‌کنندگان بهبود یافتند.'
        monkeypatch.setattr(graph, 'generate', fake_generate)
        cfg = Settings(mode='translation', translation_backend='api')
        result = TranslationPipeline(db, cfg).translate('The participants improved.', save=False)
        assert result.target == 'شرکت‌کنندگان بهبود یافتند.'
        assert result.mode == 'api'
        assert len(output) == 1
        assert output[0][1] == 'api'
        assert 'The participants improved.' in output[0][0]
    finally:
        db.close()


def test_invalid_backend_and_mode_rejected():
    for kwargs in ({'mode': 'api'}, {'mode': 'local'}, {'translation_backend': 'dictionary'}):
        try:
            Settings(**kwargs).validate()
        except ValueError:
            pass
        else:
            raise AssertionError(f'Should reject {kwargs}')


def test_dictionary_mode_never_calls_a_language_model(tmp_path, monkeypatch):
    db = Database(tmp_path / 'no-network.db')
    try:
        import psylex.rag.graph as graph
        def forbidden(*_args, **_kwargs):
            raise AssertionError('Dictionary mode called a language model')
        monkeypatch.setattr(graph, 'generate', forbidden)
        cfg = Settings(mode='dictionary', translation_backend='api')
        result = TranslationPipeline(db, cfg).translate('entirely novel paragraph', save=False)
        assert result.target == ''
        assert result.mode == 'dictionary'
        assert 'No exact dictionary' in ' '.join(result.warnings)
    finally:
        db.close()
