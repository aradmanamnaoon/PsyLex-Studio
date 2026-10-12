"""First-run marker, cloud-config preservation, and startup entrypoint tests."""
from pathlib import Path

import pytest

from psylex.core.config import Settings
from psylex.core.first_run import (MARKER_FILE, needs_model_setup,
                                  mark_model_setup_finished, marker_path)
from psylex.core.local_setup import configure_detected_model
from psylex.providers.native_http import LocalServer


def test_first_launch_only_once_per_user_location(tmp_path):
    assert marker_path(tmp_path) == tmp_path / MARKER_FILE
    assert needs_model_setup(tmp_path)
    mark_model_setup_finished('skipped', tmp_path)
    assert not needs_model_setup(tmp_path)
    assert 'skipped' in marker_path(tmp_path).read_text(encoding='utf-8')
    assert needs_model_setup(tmp_path / 'other-user')


def test_configured_marker_does_not_include_credentials(tmp_path):
    mark_model_setup_finished('configured', tmp_path)
    data = marker_path(tmp_path).read_text(encoding='utf-8')
    assert 'configured' in data
    assert 'api_key' not in data.lower()
    assert 'model' not in data.lower()
    with pytest.raises(ValueError):
        mark_model_setup_finished('unrecognized', tmp_path)


def test_existing_settings_survive_skip(tmp_path):
    saved = tmp_path / 'settings.json'
    cfg = Settings(translation_backend='api', provider='OpenRouter',
                   model='openrouter/free', base_url='', mode='translation')
    cfg.save(saved)
    initial = saved.read_bytes()
    mark_model_setup_finished('skipped', tmp_path)
    assert saved.read_bytes() == initial
    assert Settings.load(saved).provider == 'OpenRouter'


def test_local_setup_preserves_cloud_provider_profiles(tmp_path):
    saved = tmp_path / 'settings.json'
    cfg = Settings(translation_backend='api', provider='OpenRouter',
                   model='openrouter/free', base_url='',
                   provider_profiles={'OpenRouter': {'model': 'openrouter/free', 'base_url':'', 'api_key_env':''}})
    srv = LocalServer('Ollama', 'http://127.0.0.1:11434', ('qwen2.5:7b',))
    updated = configure_detected_model(cfg, srv, 'qwen2.5:7b')
    updated.save(saved)
    restored = Settings.load(saved)
    assert restored.provider == 'Ollama'
    assert restored.model == 'qwen2.5:7b'
    assert restored.mode == 'dictionary'
    assert restored.provider_profiles['OpenRouter']['model'] == 'openrouter/free'


def test_entry_point_does_not_trigger_setup_for_packaged_self_test():
    source = (Path(__file__).resolve().parents[1] / 'main.py').read_text(encoding='utf-8')
    assert "if '--setup-local-models' in sys.argv:" in source
    assert "if '--self-test-report' in sys.argv:" in source
    assert 'offer_local_models_on_first_launch()' in source
    assert source.index("if '--self-test-report' in sys.argv:") < source.index('sys.exit(main())')


def test_release_gate_executes_first_launch_smoke_on_windows():
    source = (Path(__file__).resolve().parents[1] / 'scripts/release_gate.py').read_text(encoding='utf-8')
    assert "'gui_first_launch_model_setup'" in source
    assert "'scripts/ui_install_model_setup_smoke_test.py'" in source
