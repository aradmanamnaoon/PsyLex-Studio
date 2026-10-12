"""Backend contract tests use fake LiteLLM responses; no cloud charges or external models."""
from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import pytest

from psylex.core.config import Settings
from psylex.providers.models import (
    ModelConfigurationError, ModelRequestError, _request_params,
    generate, test_connection as check_connection,
)


def reply(text: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


def mock_litellm(monkeypatch, handler):
    monkeypatch.setitem(sys.modules, 'litellm', SimpleNamespace(completion=handler))


def test_default_local_provider_is_canonical():
    cfg = Settings(transport='litellm', mode='translation')
    assert cfg.provider == 'Ollama'
    assert _request_params(cfg)['model'] == 'ollama/qwen2.5:7b'


def test_legacy_provider_lowercase_is_migrated(tmp_path):
    path = tmp_path / 'settings.json'
    path.write_text(json.dumps({'provider': 'openrouter', 'mode': 'api',
                                'model': 'openrouter/free'}), encoding='utf-8')
    cfg = Settings.load(path)
    assert (cfg.provider, cfg.translation_backend) == ('OpenRouter', 'api')


def test_ollama_request_uses_local_base_without_remote_api_key(monkeypatch):
    seen = []
    mock_litellm(monkeypatch, lambda **kwargs: (seen.append(kwargs), reply('ترجمه'))[1])
    cfg = Settings(transport='litellm', mode='translation', translation_backend='local', provider='Ollama',
                   model='qwen2.5:7b', base_url='http://localhost:11434', session_api_key='SHOULD-NOT-SEND')
    assert generate('hi', cfg) == 'ترجمه'
    assert seen[0]['model'] == 'ollama/qwen2.5:7b'
    assert seen[0]['api_base'] == 'http://localhost:11434'
    assert 'api_key' not in seen[0]


def test_lm_studio_adds_compatible_prefix_and_dummy_nonsecret_key(monkeypatch):
    seen = []
    mock_litellm(monkeypatch, lambda **kwargs: (seen.append(kwargs), reply('سلام'))[1])
    cfg = Settings(transport='litellm', mode='translation', translation_backend='local', provider='LM Studio',
                   model='qwen/qwen-3', base_url='http://localhost:1234/v1')
    assert generate('hello', cfg) == 'سلام'
    assert seen[0]['model'] == 'openai/qwen/qwen-3'
    assert seen[0]['api_key'] == 'not-required'


def test_openrouter_env_key_and_prefix(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'unit-test-key')
    seen = []
    mock_litellm(monkeypatch, lambda **kwargs: (seen.append(kwargs), reply('OK'))[1])
    cfg = Settings(transport='litellm', mode='translation', translation_backend='api', provider='OpenRouter',
                   model='openrouter/free', seed=42)
    assert 'Connected' in check_connection(cfg)
    assert seen[0]['api_key'] == 'unit-test-key'
    assert seen[0]['model'] == 'openrouter/openrouter/free'
    assert 'seed' not in seen[0]  # provider does not guarantee seed support
    assert 'api_base' not in seen[0]  # do not send stale localhost URL


def test_session_key_takes_precedence_and_is_not_saved(monkeypatch, tmp_path):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'env-key')
    cfg = Settings(transport='litellm', mode='translation', translation_backend='api', provider='OpenRouter',
                   session_api_key='new-dialog-key', model='openrouter/free')
    assert _request_params(cfg)['api_key'] == 'new-dialog-key'
    path = tmp_path / 'settings.json'
    cfg.save(path)
    assert 'new-dialog-key' not in path.read_text(encoding='utf-8')
    assert Settings.load(path).session_api_key == ''


def test_explicit_missing_environment_is_actionable(monkeypatch):
    monkeypatch.delenv('PSYLEX_MISSING_KEY', raising=False)
    cfg = Settings(transport='litellm', translation_backend='api', provider='OpenRouter', model='openrouter/free',
                   api_key_env='PSYLEX_MISSING_KEY')
    with pytest.raises(ModelConfigurationError, match='PSYLEX_MISSING_KEY'):
        _request_params(cfg)


def test_wrong_provider_backend_and_bad_url_are_rejected():
    cfg = Settings(transport='litellm', translation_backend='local', provider='OpenRouter')
    with pytest.raises(ModelConfigurationError, match='not a local backend'):
        _request_params(cfg)
    cfg = Settings(transport='litellm', translation_backend='local', provider='Ollama', base_url='ftp://localhost')
    with pytest.raises(ModelConfigurationError, match='http'):
        _request_params(cfg)
    cfg.base_url = 'http://secret:pass@localhost:11434'
    with pytest.raises(ModelConfigurationError, match='without embedded credentials'):
        _request_params(cfg)


def test_auth_error_is_redacted_without_retries(monkeypatch):
    attempts = []
    def failing(**kwargs):
        attempts.append(kwargs)
        raise Exception('401 unauthorized; Authorization: Bearer session-secret-key; api_key=session-secret-key')
    mock_litellm(monkeypatch, failing)
    cfg = Settings(transport='litellm', translation_backend='api', provider='OpenRouter', model='openrouter/free',
                   session_api_key='session-secret-key', retry_attempts=5)
    with pytest.raises(ModelRequestError, match='Authentication rejected') as caught:
        generate('hello', cfg)
    assert 'session-secret-key' not in str(caught.value)
    assert len(attempts) == 1


def test_transient_error_retried_then_succeeds(monkeypatch):
    attempts = []
    monkeypatch.setattr('psylex.providers.models.time.sleep', lambda _: None)
    def handler(**kwargs):
        attempts.append(kwargs)
        if len(attempts) < 3:
            raise TimeoutError('Connection timed out')
        return reply('سلام')
    mock_litellm(monkeypatch, handler)
    cfg = Settings(transport='litellm', translation_backend='api', provider='OpenRouter', model='openrouter/free',
                   session_api_key='secret', retry_attempts=2)
    assert generate('hello', cfg) == 'سلام'
    assert len(attempts) == 3


def test_empty_provider_answer_is_actionable(monkeypatch):
    mock_litellm(monkeypatch, lambda **kwargs: reply(' '))
    cfg = Settings(transport='litellm', translation_backend='local', provider='Ollama')
    with pytest.raises(ModelRequestError, match='empty response'):
        generate('test', cfg)


def test_invalid_retry_count_rejected():
    cfg = Settings(transport='litellm', retry_attempts=6)
    with pytest.raises(ValueError, match='Retry attempts'):
        cfg.validate()


def test_openai_model_normalization_and_wrong_prefix():
    cfg = Settings(transport='litellm', translation_backend='api', provider='OpenAI', model='gpt-4.1-mini',
                   session_api_key='dummy')
    assert _request_params(cfg)['model'] == 'openai/gpt-4.1-mini'
    cfg.model = 'ollama/local-model'
    with pytest.raises(ModelConfigurationError, match='non-OpenAI'):
        _request_params(cfg)


def test_diagnostic_does_not_show_credentials_in_url():
    from scripts.diagnose_model import safe_url
    assert 'secret' not in safe_url('https://username:secret@example.org/v1?api_key=secret')
    assert safe_url('https://user:secret@example.org/v1') == 'https://example.org/v1'
    assert 'secret' not in safe_url('https://example.org/v1/secret')
