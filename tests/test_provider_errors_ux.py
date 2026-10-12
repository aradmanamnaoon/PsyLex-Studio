"""Exact previously-reported provider failures must be useful and non-retryable."""
from __future__ import annotations
import sys
from types import SimpleNamespace
import pytest
from psylex.core.config import Settings
from psylex.providers.models import ModelRequestError, generate


class ProviderFailure(Exception):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


def test_openrouter_http402_reports_billing_without_retry(monkeypatch):
    calls = []
    def request(**params):
        calls.append(params)
        raise ProviderFailure('{"error":{"message":"Insufficient credits", "code":402}}', 402)
    monkeypatch.setitem(sys.modules, 'litellm', SimpleNamespace(completion=request))
    cfg = Settings(transport='litellm', mode='translation', translation_backend='api', provider='OpenRouter',
                   model='openrouter/free', session_api_key='secret-value', retry_attempts=3)
    with pytest.raises(ModelRequestError) as info:
        generate('test', cfg)
    msg = str(info.value)
    assert '402' in msg and 'credits' in msg.lower()
    assert 'openrouter.ai/settings/credits' in msg
    assert 'secret-value' not in msg
    assert len(calls) == 1


def test_ollama_windows10061_reports_server_startup_without_retry(monkeypatch):
    calls = []
    def request(**params):
        calls.append(params)
        raise ProviderFailure('[WinError 10061] No connection could be made because target machine actively refused it')
    monkeypatch.setitem(sys.modules, 'litellm', SimpleNamespace(completion=request))
    cfg = Settings(transport='litellm', mode='translation', translation_backend='local', provider='Ollama',
                   base_url='http://localhost:11434', retry_attempts=4)
    with pytest.raises(ModelRequestError) as info:
        generate('test', cfg)
    msg = str(info.value)
    assert '11434' in msg and 'ollama serve' in msg
    assert 'refused' in msg.lower()
    assert len(calls) == 1


def test_cloud_credit_error_without_provider_key_remains_configuration_error():
    from psylex.providers.models import _request_params, ModelConfigurationError
    cfg = Settings(transport='litellm', mode='translation', translation_backend='api', provider='OpenRouter',
                   model='openrouter/free', api_key_env='PSYLEX_UNKNOWN_KEY_FOR_TEST')
    with pytest.raises(ModelConfigurationError, match='PSYLEX_UNKNOWN_KEY_FOR_TEST'):
        _request_params(cfg)
