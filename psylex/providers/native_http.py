"""Minimal direct HTTP transports for Ollama and OpenAI-compatible inference.

No hidden provider inference, model rewriting, global SDK settings, or network
side effects beyond one explicitly configured endpoint.
"""
from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, ProxyHandler, build_opener, urlopen


class NativeHTTPError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class LocalServer:
    provider: str
    url: str
    models: tuple[str, ...]


def _request_json(url: str, *, payload: dict | None = None, api_key: str = '',
                  timeout: float = 8, bypass_proxy: bool = False) -> dict:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode('utf-8')
    headers = {'Accept': 'application/json'}
    if body is not None:
        headers['Content-Type'] = 'application/json'
    if api_key:
        headers['Authorization'] = 'Bearer ' + api_key
    req = Request(url, data=body, headers=headers, method='POST' if body is not None else 'GET')
    try:
        opener = build_opener(ProxyHandler({})) if bypass_proxy else None
        with (opener.open(req, timeout=timeout) if opener else urlopen(req, timeout=timeout)) as response:
            raw = response.read(2 * 1024 * 1024)
        data = json.loads(raw.decode('utf-8'))
        if not isinstance(data, dict):
            raise NativeHTTPError('The model server returned an unexpected JSON response.')
        return data
    except HTTPError as exc:
        try:
            data = json.loads(exc.read(4096).decode('utf-8', errors='replace'))
            reason = data.get('error', data)
            if isinstance(reason, dict):
                reason = reason.get('message', reason.get('code', 'Request rejected'))
            message = str(reason)
        except (ValueError, UnicodeError):
            message = exc.reason or f'HTTP {exc.code}'
        raise NativeHTTPError(f'HTTP {exc.code}: {message}', status_code=exc.code) from None
    except (URLError, TimeoutError, socket.timeout, OSError) as exc:
        raise NativeHTTPError(f'Could not connect to {urlsplit(url).hostname or "model server"}: {exc}') from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise NativeHTTPError('The model server returned invalid JSON.') from None


def _model_id(model: str, provider: str) -> str:
    model = model.strip()
    if provider == 'Ollama':
        return model.removeprefix('ollama/')
    if provider == 'OpenRouter':
        return model.removeprefix('openrouter/')
    if provider in ('LM Studio', 'llama.cpp server', 'vLLM', 'Generic OpenAI endpoint'):
        return model.removeprefix('openai/')
    return model


def native_generate(prompt: str, *, provider: str, model: str, base_url: str,
                    api_key: str = '', timeout: int = 120, temperature: float = 0.1,
                    top_p: float = 1.0, max_tokens: int = 2048) -> str:
    """Call the actual provider wire protocol; return an unmodified text response."""
    if provider == 'Ollama':
        base = base_url.rstrip('/')
        if base.endswith('/api/chat'):
            base = base[:-9]
        if base.endswith('/api'):
            base = base[:-4]
        body = {
            'model': _model_id(model, provider),
            'messages': [{'role': 'user', 'content': prompt}],
            'stream': False,
            'options': {'temperature': temperature, 'top_p': top_p, 'num_predict': max_tokens},
        }
        response = _request_json(base + '/api/chat', payload=body, timeout=timeout, bypass_proxy=True)
        value = response.get('message', {})
        text = value.get('content') if isinstance(value, dict) else None
    else:
        if provider == 'OpenRouter':
            base = base_url.rstrip('/') if base_url else 'https://openrouter.ai/api/v1'
        else:
            base = base_url.rstrip('/')
        if not base:
            raise NativeHTTPError('Missing server Base URL.')
        if base.endswith('/chat/completions'):
            base = base[:-17]
        if not base.endswith('/v1') and not base.endswith('/api/v1') and provider != 'OpenRouter':
            base += '/v1'
        body = {
            'model': _model_id(model, provider),
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': temperature, 'top_p': top_p, 'max_tokens': max_tokens,
        }
        response = _request_json(base + '/chat/completions', payload=body,
                                 api_key=api_key, timeout=timeout,
                                 bypass_proxy=provider != 'OpenRouter')
        choices = response.get('choices') or []
        first = choices[0] if choices else {}
        message = first.get('message', {}) if isinstance(first, dict) else {}
        text = message.get('content') if isinstance(message, dict) else None
    if not isinstance(text, str) or not text.strip():
        raise NativeHTTPError(f'{provider} returned an empty translation. Verify model capacity and output limits.')
    return text.strip()


def discover_local_servers(timeout: float = 1.0, configured_url: str = '') -> list[LocalServer]:
    """Probe loopback services only; never send local prompts or credentials."""
    candidates = [
        ('Ollama', 'http://127.0.0.1:11434'),
        ('LM Studio', 'http://127.0.0.1:1234/v1'),
        ('llama.cpp server', 'http://127.0.0.1:8080/v1'),
        ('vLLM', 'http://127.0.0.1:8000/v1'),
    ]
    if configured_url:
        url = urlsplit(configured_url)
        if url.hostname in ('localhost', '127.0.0.1', '::1') and url.scheme in ('http', 'https'):
            candidates.insert(0, ('Configured server', configured_url.rstrip('/')))
    found: list[LocalServer] = []
    visited: set[str] = set()
    for provider, url in candidates:
        host = url.rstrip('/').replace('localhost', '127.0.0.1')
        if host in visited:
            continue
        visited.add(host)
        is_ollama = url.endswith(':11434') or url.endswith(':11434/')
        route = '/api/tags' if is_ollama else '/models'
        try:
            result = _request_json(host + route, timeout=timeout, bypass_proxy=True)
        except (NativeHTTPError, ValueError):
            continue
        values = result.get('models', []) if is_ollama else result.get('data', [])
        if not isinstance(values, list):
            continue
        models = tuple(dict.fromkeys(str(row.get('name' if is_ollama else 'id', '')).strip()
                                    for row in values if isinstance(row, dict)
                                    and row.get('name' if is_ollama else 'id')))
        if models:
            found.append(LocalServer('Ollama' if is_ollama else
                                     (provider if provider != 'Configured server' else 'LM Studio'),
                                     url, models))
    return found
