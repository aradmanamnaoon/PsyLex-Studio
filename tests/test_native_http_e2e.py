"""Real loopback HTTP integration tests: no paid API keys, Ollama, or cloud access.

Unlike mocked LiteLLM calls these exercise JSON serialization, URL routing,
HTTP status handling, authentication headers, and end-to-end response parsing.
"""
from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from psylex.core.config import Settings
from psylex.providers.models import ModelRequestError, generate
from psylex.providers.native_http import discover_local_servers, native_generate


@contextmanager
def fake_server(*, fail_status=0, response_text='ترجمه درست'):
    received = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            received.append(('GET', self.path, {}, None))
            models = {'data': [{'id': 'loaded-local-model'}]}
            data = json.dumps(models).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])).decode('utf-8'))
            received.append(('POST', self.path, dict(self.headers), body))
            if fail_status:
                response = {'error': {'message': 'Insufficient credits' if fail_status == 402 else 'Invalid API key',
                                      'code': fail_status}}
            elif self.path.endswith('/api/chat'):
                response = {'message': {'content': response_text}}
            else:
                response = {'choices': [{'message': {'content': response_text}}]}
            data = json.dumps(response, ensure_ascii=False).encode()
            self.send_response(fail_status or 200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
    srv = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{srv.server_port}', received
    finally:
        srv.shutdown()
        thread.join(timeout=5)
        srv.server_close()


def test_ollama_native_end_to_end_and_prefix_cleanup():
    with fake_server() as (url, requests):
        cfg = Settings(mode='translation', translation_backend='local', provider='Ollama',
                       model='ollama/my-local:latest', base_url=url, transport='native')
        assert generate('Translate into Persian', cfg) == 'ترجمه درست'
        method, path, headers, body = requests[0]
        assert (method, path) == ('POST', '/api/chat')
        assert body['model'] == 'my-local:latest'
        assert body['stream'] is False
        assert 'temperature' in body['options']
        assert not headers.get('Authorization')
        assert body['messages'][0]['content'] == 'Translate into Persian'


def test_ollama_accepts_server_api_chat_url():
    with fake_server() as (url, requests):
        assert native_generate('text', provider='Ollama', model='ollama/my-model',
                               base_url=url+'/api/chat') == 'ترجمه درست'
        assert requests[0][1] == '/api/chat'


def test_local_openai_compatible_end_to_end_and_full_url():
    with fake_server() as (url, requests):
        cfg = Settings(mode='translation', translation_backend='local', provider='LM Studio',
                       model='loaded-local-model', base_url=url+'/v1', transport='native')
        assert generate('Translate text', cfg) == 'ترجمه درست'
        method, path, headers, body = requests[0]
        assert (method, path) == ('POST', '/v1/chat/completions')
        assert body['model'] == 'loaded-local-model'
        assert 'Authorization' not in headers
        assert native_generate('text', provider='LM Studio', model='loaded-local-model',
                               base_url=url+'/v1/chat/completions') == 'ترجمه درست'
        assert requests[-1][1] == '/v1/chat/completions'


def test_openrouter_native_wire_format_and_authentication():
    with fake_server() as (url, requests):
        assert native_generate('Translate', provider='OpenRouter', model='openrouter/openrouter/free',
                               base_url=url+'/api/v1', api_key='private-test-token') == 'ترجمه درست'
        method, path, headers, body = requests[0]
        assert path == '/api/v1/chat/completions'
        assert headers['Authorization'] == 'Bearer private-test-token'
        assert body['model'] == 'openrouter/free'
        assert body['messages'][0]['content'] == 'Translate'


def test_openrouter_402_is_not_retried_and_redacts_key(monkeypatch):
    with fake_server(fail_status=402) as (url, requests):
        from psylex.providers.native_http import NativeHTTPError
        with pytest.raises(NativeHTTPError, match='402'):
            native_generate('Translate', provider='OpenRouter', model='openrouter/openrouter/free',
                            base_url=url+'/api/v1', api_key='private-test-token')
        assert len(requests) == 1


def test_openrouter_401_is_not_retried(monkeypatch):
    with fake_server(fail_status=401) as (url, requests):
        from psylex.providers.native_http import NativeHTTPError
        with pytest.raises(NativeHTTPError, match='401'):
            native_generate('Translate', provider='OpenRouter', model='openrouter/openrouter/free',
                            base_url=url+'/api/v1', api_key='private-test-token')
        assert len(requests) == 1


def test_loopback_discovery_respects_configured_compatible_server():
    with fake_server() as (url, requests):
        found = discover_local_servers(configured_url=url+'/v1', timeout=.1)
        assert any('loaded-local-model' in s.models and s.url == url+'/v1' for s in found)
        assert any(p == '/v1/models' for method, p, _, _ in requests if method == 'GET')


def test_openrouter_key_cannot_be_sent_to_arbitrary_endpoint():
    from psylex.providers.models import ModelConfigurationError, _request_params
    cfg = Settings(mode='translation', translation_backend='api', provider='OpenRouter',
                   model='openrouter/free', base_url='http://localhost:11434/not-the-api',
                   session_api_key='very-private', transport='native')
    # Legacy localhost defaults are cleared rather than receiving a cloud key.
    with pytest.raises(ModelConfigurationError, match='only be sent'):
        _request_params(cfg)
    cfg.base_url = 'https://openrouter.ai/api/v1'
    assert _request_params(cfg)['api_base'] == 'https://openrouter.ai/api/v1'
    cfg.base_url = 'http://attacker.invalid/api/v1'
    with pytest.raises(ModelConfigurationError, match='only be sent'):
        _request_params(cfg)


def test_complete_translation_pipeline_to_real_loopback_server(tmp_path):
    """Exercise retrieval, prompt creation, native provider, QA and SQLite history."""
    from psylex.core.database import Database
    from psylex.rag.graph import TranslationPipeline
    from psylex.core.models import DictionaryEntry
    with fake_server(response_text='توانایی حافظهٔ کاری') as (url, requests):
        database = Database(tmp_path / 'pipeline.sqlite3')
        try:
            database.insert_entries([
                DictionaryEntry('working memory', 'حافظه کاری', 'Test glossary', 'line 1', .95)
            ])
            cfg = Settings(mode='translation', translation_backend='local', provider='LM Studio',
                           model='loaded-local-model', base_url=url+'/v1', transport='native')
            result = TranslationPipeline(database, cfg).translate(
                'The researchers assessed working memory in undergraduate participants.', save=True)
            assert result.target == 'توانایی حافظهٔ کاری'
            assert result.id is not None
            assert len(database.history()) == 1
            assert any('working memory' in req[3]['messages'][0]['content']
                       for req in requests if req[0] == 'POST')
        finally:
            database.close()
