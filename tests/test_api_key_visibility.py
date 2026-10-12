"""Credential persistence regression tests; no real OS keyring or network used."""
from __future__ import annotations

import json
import sys
from types import SimpleNamespace

from psylex.core.config import SERVICE, Settings


def test_saved_provider_keys_are_independent_and_never_written_to_json(monkeypatch, tmp_path):
    store = {(SERVICE, 'OpenRouter'): 'unit-openrouter-secret',
             (SERVICE, 'OpenAI'): 'unit-openai-secret'}
    monkeypatch.setitem(sys.modules, 'keyring', SimpleNamespace(
        get_password=lambda service, name: store.get((service, name)),
        set_password=lambda service, name, value: store.__setitem__((service, name), value),
        delete_password=lambda service, name: store.pop((service, name), None)))
    cfg = Settings(provider='OpenRouter', translation_backend='api', model='openrouter/free')
    assert cfg.get_stored_key() == 'unit-openrouter-secret'
    assert cfg.get_stored_key('OpenAI') == 'unit-openai-secret'
    cfg.set_key('changed-secret')
    assert cfg.get_stored_key() == 'changed-secret'
    path = tmp_path / 'settings.json'
    cfg.save(path)
    raw = path.read_text(encoding='utf-8')
    assert 'changed-secret' not in raw
    assert 'unit-openai-secret' not in raw
    assert 'session_api_key' not in json.loads(raw)
    loaded = Settings.load(path)
    assert loaded.get_stored_key('OpenRouter') == 'changed-secret'
    assert loaded.get_stored_key('OpenAI') == 'unit-openai-secret'


def test_forget_key_removes_legacy_lowercase_alias(monkeypatch):
    store = {(SERVICE, 'openrouter'): 'legacy-lowercase-key'}
    monkeypatch.setitem(sys.modules, 'keyring', SimpleNamespace(
        get_password=lambda service, name: store.get((service, name)),
        set_password=lambda service, name, value: store.__setitem__((service, name), value),
        delete_password=lambda service, name: store.pop((service, name), None)))
    cfg = Settings(provider='OpenRouter')
    assert cfg.get_stored_key() == 'legacy-lowercase-key'
    cfg.set_key('')
    assert cfg.get_stored_key() == ''


def test_saved_key_and_explicit_environment_variable_keep_distinct_roles(monkeypatch):
    monkeypatch.setenv('PSYLEX_VISIBILITY_CHECK', 'environment-value')
    store = {(SERVICE, 'OpenRouter'): 'keyring-value'}
    monkeypatch.setitem(sys.modules, 'keyring', SimpleNamespace(
        get_password=lambda service, name: store.get((service, name))))
    cfg = Settings(provider='OpenRouter', api_key_env='PSYLEX_VISIBILITY_CHECK')
    assert cfg.get_key() == 'environment-value'
    assert cfg.get_stored_key() == 'keyring-value'
    monkeypatch.delenv('PSYLEX_VISIBILITY_CHECK')
    assert cfg.get_key() == ''  # named but missing env var does not fall back secretly
    assert cfg.get_stored_key() == 'keyring-value'
