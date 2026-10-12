"""Installer selection rules and packaging checks (no Qt or live provider needed)."""
from pathlib import Path

import pytest

from psylex.core.config import Settings
from psylex.core.local_setup import configure_detected_model
from psylex.providers.native_http import LocalServer

ROOT = Path(__file__).resolve().parents[1]


def test_installation_selection_preserves_dictionary_and_cloud_config(tmp_path):
    cfg = Settings(mode='dictionary', theme='light', translation_backend='api',
                   provider='OpenRouter', model='google/gemma-4-31b-it:free',
                   base_url='', api_key_env='OPENROUTER_API_KEY',
                   provider_profiles={'Ollama': {'model': 'prior:latest',
                                                  'base_url': 'http://127.0.0.1:11434',
                                                  'api_key_env': ''}},
                   store_feedback=False)
    srv = LocalServer('LM Studio', 'http://127.0.0.1:1234/v1', ('loaded-model', 'other'))
    configured = configure_detected_model(cfg, srv, 'loaded-model')
    assert cfg.provider == 'OpenRouter'  # pure operation
    assert configured.translation_backend == 'local'
    assert configured.mode == 'dictionary'
    assert configured.theme == 'light'
    assert configured.store_feedback is False
    assert configured.model == 'loaded-model'
    assert configured.base_url == srv.url
    assert configured.transport == 'native'
    assert configured.provider_profiles['OpenRouter'] == {
        'model': cfg.model, 'base_url': '', 'api_key_env': cfg.api_key_env,
    }
    assert configured.provider_profiles['Ollama']['model'] == 'prior:latest'
    assert configured.provider_profiles['LM Studio']['model'] == 'loaded-model'
    destination = tmp_path / 'settings.json'
    configured.save(destination)
    loaded = Settings.load(destination)
    assert loaded.provider == 'LM Studio'
    assert loaded.provider_profiles['OpenRouter']['model'] == cfg.model


@pytest.mark.parametrize('provider,url,models,chosen', [
    ('OpenRouter', 'http://127.0.0.1:1234/v1', ('test-model',), 'test-model'),
    ('LM Studio', 'https://models.example.com/v1', ('test-model',), 'test-model'),
    ('LM Studio', 'http://user:pass@127.0.0.1:1234/v1', ('test-model',), 'test-model'),
    ('LM Studio', 'http://127.0.0.1:1234/v1', ('a',), 'wrong-model'),
    ('LM Studio', 'ftp://127.0.0.1:1234/v1', ('a',), 'a'),
    ('LM Studio', 'http://127.0.0.1/v1', ('a',), 'a'),
])
def test_installer_refuses_invalid_or_remote_selection(provider, url, models, chosen):
    cfg = Settings()
    with pytest.raises(ValueError):
        configure_detected_model(cfg, LocalServer(provider, url, models), chosen)
    assert cfg.provider == 'Ollama'


def test_installer_accepts_ollama_exact_model_name():
    srv = LocalServer('Ollama', 'http://127.0.0.1:11434', ('qwen2.5:7b',))
    cfg = configure_detected_model(Settings(), srv, 'qwen2.5:7b')
    assert cfg.provider == 'Ollama'
    assert cfg.model == 'qwen2.5:7b'
    assert cfg.base_url == 'http://127.0.0.1:11434'


def test_first_launch_is_wired_to_embedded_application_not_python():
    main = (ROOT / 'main.py').read_text(encoding='utf-8')
    assert 'offer_local_models_on_first_launch()' in main
    assert 'InstallLocalModelDialog' in main
    assert '--setup-local-models' in main
    assert 'model_setup_command()' in main
    assert 'sys.exit(main())' in main
    assert "if '--self-test-report' in sys.argv:" in main


def test_user_secrets_are_not_serialized_by_setup(tmp_path):
    cfg = Settings(provider='OpenRouter', model='openrouter/free',
                   session_api_key='temporary-secret', translation_backend='api')
    srv = LocalServer('Ollama', 'http://127.0.0.1:11434', ('a:latest',))
    path = tmp_path / 'settings.json'
    configure_detected_model(cfg, srv, 'a:latest').save(path)
    assert 'temporary-secret' not in path.read_text(encoding='utf-8')



def test_installer_discovery_with_real_loopback_http():
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from psylex.providers.native_http import discover_local_servers

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass
        def do_GET(self):
            assert self.path == '/v1/models'
            data = json.dumps({'data': [{'id': 'real-local-model'}]}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f'http://127.0.0.1:{server.server_port}/v1'
        found = discover_local_servers(timeout=.3, configured_url=url)
        assert any(s.provider == 'LM Studio' and s.url == url
                   and 'real-local-model' in s.models for s in found)
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
