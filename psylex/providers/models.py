"""LiteLLM adapter, local inference backends, and connection diagnostics."""
from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Any
from psylex.core.config import Settings

PROVIDERS = {
    'OpenAI': 'openai/gpt-4.1-mini',
    'Azure OpenAI': 'azure/your-deployment',
    'Anthropic': 'anthropic/claude-sonnet-4-5',
    'Google Gemini': 'gemini/gemini-2.5-flash',
    'Google Vertex AI': 'vertex_ai/gemini-2.5-flash',
    'Mistral': 'mistral/mistral-small-latest',
    'Cohere': 'command-r-plus',
    'Groq': 'groq/llama-3.3-70b-versatile',
    'Together': 'together_ai/meta-llama/Llama-3.3-70B-Instruct-Turbo',
    'Fireworks': 'fireworks_ai/accounts/fireworks/models/llama-v3p3-70b-instruct',
    'OpenRouter': 'openrouter/openai/gpt-4.1-mini',
    'DeepSeek': 'deepseek/deepseek-chat',
    'xAI': 'xai/grok-3-mini',
    'Perplexity': 'perplexity/sonar',
    'Generic OpenAI endpoint': 'openai/your-model',
    'Ollama': 'ollama/qwen2.5:7b',
    'LM Studio': 'openai/local-model',
    'llama.cpp server': 'openai/local-model',
    'vLLM': 'openai/local-model',
    'GPT4All': 'gpt4all/your-model.gguf',
    'Transformers': 'transformers/your-local-model',
}

LOCAL_URLS = {
    'Ollama': 'http://localhost:11434',
    'LM Studio': 'http://localhost:1234/v1',
    'llama.cpp server': 'http://localhost:8080/v1',
    'vLLM': 'http://localhost:8000/v1',
}



import re
import time
from urllib.parse import urlsplit

LOCAL_PROVIDERS = frozenset({
    'Ollama', 'LM Studio', 'llama.cpp server', 'vLLM', 'GPT4All', 'Transformers',
})
KEYLESS_CLOUD_PROVIDERS = frozenset({'Google Vertex AI'})  # ADC / workload identity
TRANSIENT_HINTS = ('timeout', 'timed out', 'connection', 'rate limit', 'rate_limit',
                   'too many requests', 'overloaded', 'temporarily unavailable',
                   'service unavailable', 'gateway', '503', '502', '504', '429')
AUTH_HINTS = ('401', '403', 'unauthorized', 'invalid api key', 'invalid_api_key',
              'authentication', 'permission denied', 'forbidden')
MODEL_HINTS = ('404', 'model not found', 'model_not_found', 'not_found', 'unknown model')


class ModelConfigurationError(ValueError):
    """Local, actionable and safe configuration error."""


class ModelRequestError(RuntimeError):
    """Sanitized provider/network error suitable for display to the user."""


def _redact(message: str, secrets: tuple[str, ...] = ()) -> str:
    for secret in secrets:
        if secret:
            message = message.replace(secret, '[REDACTED]')
    # Guard against credentials embedded in third-party exceptions.
    message = re.sub(r'(?i)(bearer\s+)[^\s,;]+', r'\1[REDACTED]', message)
    message = re.sub(r'(?i)((?:api[_-]?key|authorization|token|password)[=:]\s*)[^\s,;]+',
                     r'\1[REDACTED]', message)
    message = re.sub(r'\bsk-[a-zA-Z0-9_-]{8,}\b', '[REDACTED]', message)
    return message[:350]


def _model_for_provider(cfg: Settings) -> str:
    model = cfg.model.strip()
    if not model:
        raise ModelConfigurationError('No model ID. Enter the installed/local or cloud model in Settings → Models & API.')
    if cfg.provider == 'Ollama' and not model.startswith('ollama/'):
        return 'ollama/' + model
    if cfg.provider in {'LM Studio', 'llama.cpp server', 'vLLM', 'Generic OpenAI endpoint'}:
        return model if model.startswith('openai/') else 'openai/' + model
    if cfg.provider == 'OpenAI':
        if model.startswith(('ollama/', 'openrouter/', 'gpt4all/', 'transformers/')):
            raise ModelConfigurationError('OpenAI provider is paired with a non-OpenAI model. Check model ID and provider.')
        return model if model.startswith('openai/') else 'openai/' + model
    if cfg.provider == 'OpenRouter':
        if model == 'openrouter/free':
            return 'openrouter/openrouter/free'
        return model if model.startswith('openrouter/') else 'openrouter/' + model
    return model


def _request_params(cfg: Settings) -> dict[str, Any]:
    """Build an explicit request; never leak a cloud credential into local inference."""
    cfg.validate()
    provider = cfg.provider
    local = cfg.translation_backend == 'local'
    if local and provider not in LOCAL_PROVIDERS:
        raise ModelConfigurationError(
            f'{provider} is not a local backend. Select a local provider in Settings → Models & API.')
    if not local and provider in LOCAL_PROVIDERS:
        raise ModelConfigurationError(
            f'{provider} is a local backend. Select Local model in Settings → Models & API.')
    model = _model_for_provider(cfg)
    url = cfg.base_url.strip()
    # Settings before v0.6.2 always defaulted to the Ollama localhost URL,
    # even after changing the backend to a cloud provider. Never dispatch an
    # OpenRouter/OpenAI credential to a stale local inference endpoint.
    if not local and provider != 'Generic OpenAI endpoint' and url.rstrip('/') in {
        value.rstrip('/') for value in LOCAL_URLS.values()
    }:
        url = ''
    if local and provider in LOCAL_URLS and not url:
        url = LOCAL_URLS[provider]
    if url:
        parts = urlsplit(url)
        if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
            raise ModelConfigurationError('Base URL must be a valid http(s) endpoint without embedded credentials.')
    if local and provider in LOCAL_URLS and not url:
        raise ModelConfigurationError(f'Set the {provider} local server URL in Settings.')
    # Credentials for the OpenRouter provider must never be forwarded to an
    # arbitrary custom HTTP server. For self-hosted endpoints use the explicit
    # Generic OpenAI endpoint provider instead.
    if provider == 'OpenRouter' and url:
        endpoint = urlsplit(url)
        if endpoint.scheme != 'https' or endpoint.hostname != 'openrouter.ai' or endpoint.port not in (None, 443):
            raise ModelConfigurationError(
                'OpenRouter API keys may only be sent to https://openrouter.ai/api/v1. '
                'Clear Base URL to use the official endpoint. For your own server, '
                'select Generic OpenAI endpoint.')
        if endpoint.query or endpoint.fragment or endpoint.path.rstrip('/') not in ('', '/api/v1'):
            raise ModelConfigurationError(
                'Use https://openrouter.ai/api/v1 as the OpenRouter Base URL, or leave it empty.')
    key = cfg.get_key() if not local else ''
    if not local and provider not in KEYLESS_CLOUD_PROVIDERS and not key:
        hint = (f'Environment variable {cfg.api_key_env!r} is empty or missing.'
                if cfg.api_key_env else
                f'Enter the {provider} API key in Settings, or configure its standard environment variable.')
        raise ModelConfigurationError(hint)
    params: dict[str, Any] = {
        'model': model,
        'temperature': cfg.temperature,
        'top_p': cfg.top_p,
        'max_tokens': cfg.max_tokens,
        'timeout': cfg.timeout_seconds,
    }
    if url:
        params['api_base'] = url.rstrip('/')
    if local and provider in {'LM Studio', 'llama.cpp server', 'vLLM'} and cfg.transport == 'litellm':
        params['api_key'] = 'not-required'  # Some OpenAI-compatible clients demand a nonempty value.
    if key:
        params['api_key'] = key
    # Many gateway/model combinations do not support seed. Do not forward globally.
    if cfg.seed >= 0 and cfg.provider == 'OpenAI' and model.startswith('openai/'):
        params['seed'] = cfg.seed
    return params


def _direct_local(prompt: str, cfg: Settings) -> str | None:
    """Optional in-process engines; weights must be installed separately."""
    if cfg.translation_backend != 'local':
        return None
    if cfg.provider == 'GPT4All':
        try:
            from gpt4all import GPT4All
        except ImportError:
            raise ModelConfigurationError('Install the optional gpt4all package for this local backend.') from None
        filename = cfg.model.removeprefix('gpt4all/')
        with GPT4All(filename, allow_download=False) as model:
            return str(model.generate(prompt, max_tokens=cfg.max_tokens, temp=cfg.temperature))
    if cfg.provider == 'Transformers':
        try:
            from transformers import pipeline
        except ImportError:
            raise ModelConfigurationError('Install torch and transformers for this local backend.') from None
        name = cfg.model.removeprefix('transformers/')
        generator = pipeline('text-generation', model=name, trust_remote_code=False)
        generated = generator(prompt, max_new_tokens=cfg.max_tokens, do_sample=cfg.temperature > 0,
                              **({'temperature': cfg.temperature} if cfg.temperature > 0 else {}))
        return str(generated[0]['generated_text'])[len(prompt):].strip()
    return None


def _category(exc: Exception) -> str:
    # Prefer class names/status codes if LiteLLM exposes these; avoid guessing from credentials.
    name = type(exc).__name__.lower()
    code = getattr(exc, 'status_code', None)
    raw = str(exc).lower()
    if code == 402 or 'insufficient credits' in raw or 'credit balance' in raw or 'code\":402' in raw:
        return 'quota'
    if ('10061' in raw or 'connection refused' in raw or 'actively refused' in raw or
        'errno 111' in raw or 'connection refused' in name):
        return 'server_unreachable'
    if code in (401, 403) or any(x in name or x in raw for x in AUTH_HINTS):
        return 'auth'
    if code == 404 or any(x in name or x in raw for x in MODEL_HINTS):
        return 'model'
    if code == 429 or code in (502, 503, 504) or any(x in name or x in raw for x in TRANSIENT_HINTS):
        return 'transient'
    return 'other'


def _safe_error(exc: Exception, cfg: Settings, secrets: tuple[str, ...]) -> ModelRequestError:
    reason = _redact(str(exc), secrets)
    kind = _category(exc)
    if kind == 'quota':
        if cfg.provider == 'OpenRouter':
            action = ('OpenRouter rejected the request (HTTP 402: insufficient credits). '
                      'Check https://openrouter.ai/settings/credits, any per-key spending limit, '
                      'and your selected model’s pricing. No app code can bypass an account credit limit.')
        else:
            action = (f'{cfg.provider} rejected the request because your account has insufficient '
                      'available credits or exceeded its spending limit. Check your provider billing settings.')
        return ModelRequestError(action)
    if kind == 'server_unreachable' and cfg.translation_backend == 'local':
        target = cfg.base_url.strip() or LOCAL_URLS.get(cfg.provider, 'the configured local address')
        return ModelRequestError(_redact(
            f'Cannot connect to {cfg.provider} at {target}. Start the local inference server '
            '(for Ollama: run "ollama serve"), verify the model is installed and test '
            'the URL/port in Settings. Windows error 10061 means the connection was refused.', secrets))
    if kind == 'auth':
        action = 'Authentication rejected. Check the provider, key, key environment variable and account permissions.'
    elif kind == 'model':
        action = f'Model unavailable. Check model ID {cfg.model!r} and its availability with {cfg.provider}.'
    elif kind == 'transient':
        action = ('Connection, timeout, server overload or rate limit. Verify the local server/URL or '
                  'provider status; retry after a short delay.')
    else:
        action = 'Review provider/model/base URL and the error details below.'
    return ModelRequestError(_redact(f'{cfg.provider} request failed. {action} Details: {reason}', secrets))


def generate(prompt: str, cfg: Settings) -> str:
    """Local or API translation; bounded transient retries and safe diagnostics."""
    if not prompt.strip():
        raise ModelConfigurationError('Cannot translate empty text.')
    params = _request_params(cfg)  # Preflight before importing a large dependency.
    model = params['model']
    secrets = tuple(k for k in (cfg.session_api_key, cfg.get_key() if cfg.translation_backend == 'api' else '') if k)
    try:
        direct = _direct_local(prompt, cfg)
        if direct is not None:
            if not direct.strip():
                raise ModelRequestError('Local model returned empty text.')
            return direct.strip()
    except (ModelConfigurationError, ModelRequestError):
        raise
    except Exception as exc:
        raise _safe_error(exc, cfg, secrets) from None
    if cfg.transport == "native" and cfg.provider in {
        "Ollama", "LM Studio", "llama.cpp server", "vLLM", "OpenRouter", "Generic OpenAI endpoint"
    }:
        from psylex.providers.native_http import native_generate
        for attempt in range(cfg.retry_attempts + 1):
            try:
                return native_generate(
                    prompt, provider=cfg.provider, model=model,
                    base_url=params.get("api_base", ""), api_key=params.get("api_key", ""),
                    timeout=cfg.timeout_seconds, temperature=cfg.temperature,
                    top_p=cfg.top_p, max_tokens=cfg.max_tokens,
                )
            except Exception as exc:
                if _category(exc) == "transient" and attempt < cfg.retry_attempts:
                    time.sleep(min(2 ** attempt, 3))
                    continue
                raise _safe_error(exc, cfg, secrets) from None
    try:
        from litellm import completion
    except ImportError:
        raise ModelConfigurationError('LiteLLM is missing. Install project dependencies in the active Python environment.') from None
    params['messages'] = [{'role': 'user', 'content': prompt}]
    for attempt in range(cfg.retry_attempts + 1):
        try:
            result = completion(**params)
            value = result.choices[0].message.content
            if not isinstance(value, str) or not value.strip():
                raise ModelRequestError(f'{cfg.provider} returned an empty response. Check the model output and token limit.')
            return value.strip()
        except ModelRequestError:
            raise
        except Exception as exc:
            if _category(exc) == 'transient' and attempt < cfg.retry_attempts:
                time.sleep(min(2 ** attempt, 3))
                continue
            raise _safe_error(exc, cfg, secrets) from None
    raise ModelRequestError(f'{cfg.provider} exhausted retry attempts for model {model}.')


def test_connection(cfg: Settings) -> str:
    result = generate('Return exactly OK.', cfg)
    return f'Connected to {cfg.provider} / {_model_for_provider(cfg)}; response: {result[:100]}'
