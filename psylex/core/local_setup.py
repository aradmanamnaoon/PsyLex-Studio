"""Installation-time selection of a *running* localhost model, without secrets.

The setup dialog only calls this function after explicit confirmation. No
model selection is persisted when setup is skipped, cancelled, or finds nothing.
"""
from __future__ import annotations

from copy import deepcopy
from urllib.parse import urlsplit

from psylex.core.config import Settings
from psylex.providers.native_http import LocalServer

SUPPORTED_LOCAL_PROVIDERS = frozenset({'Ollama', 'LM Studio', 'llama.cpp server', 'vLLM'})
LOOPBACK_HOSTS = frozenset({'localhost', '127.0.0.1', '::1'})


def configure_detected_model(settings: Settings, server: LocalServer, model: str) -> Settings:
    """Return a new configuration for a user-selected, verified local model.

    No storage happens here: the UI calls save() only after a successful
    validation and explicit confirmation. Cloud profiles and current workspace
    mode are preserved. This function cannot select a remote server.
    """
    if server.provider not in SUPPORTED_LOCAL_PROVIDERS:
        raise ValueError('Only known local inference servers can be selected during installation.')
    url = urlsplit(server.url)
    if url.scheme not in ('http', 'https') or url.hostname not in LOOPBACK_HOSTS or url.username or url.password:
        raise ValueError('Installation discovery accepts only local loopback model servers.')
    if not url.port:
        raise ValueError('The local inference server must have an explicit port.')
    if not model or model not in server.models:
        raise ValueError('Select a model reported by the responding local server.')

    updated = deepcopy(settings)
    profiles = deepcopy(settings.provider_profiles) if isinstance(settings.provider_profiles, dict) else {}
    # Persist the existing cloud/local profile *before* changing provider.
    if settings.provider and settings.model:
        profiles[settings.provider] = {
            'model': settings.model,
            'base_url': settings.base_url,
            'api_key_env': settings.api_key_env,
        }
    profiles[server.provider] = {
        'model': model,
        'base_url': server.url,
        'api_key_env': '',
    }
    updated.provider_profiles = profiles
    updated.translation_backend = 'local'
    updated.provider = server.provider
    updated.model = model
    updated.base_url = server.url
    updated.api_key_env = ''
    updated.transport = 'native'
    updated.session_api_key = ''
    # Deliberately DO NOT change mode (Dictionary vs Translation), theme,
    # prompt, OCR, feedback, or saved cloud secrets.
    updated.validate()
    return updated
