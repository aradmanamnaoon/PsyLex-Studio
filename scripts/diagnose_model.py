"""Credential-safe local/API backend diagnostic, useful on Windows.

Dry run is offline. --live sends a SHORT prompt to the selected model and may
incur provider charges. Never pass actual API keys as command-line arguments.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from psylex.core.config import Settings
from psylex.providers.models import _request_params, test_connection


def safe_url(url: str) -> str:
    if not url:
        return ''
    try:
        parts = urlsplit(url)
        host = parts.hostname or '[invalid host]'
        if parts.port:
            host += f':{parts.port}'
        safe_path = parts.path if parts.path in ('', '/', '/v1', '/api/v1') else '/[path-redacted]'
        return urlunsplit((parts.scheme, host, safe_path, '', ''))
    except Exception:
        return '[invalid URL]'


def main() -> int:
    ap = argparse.ArgumentParser(description='No-secret model backend diagnostics')
    ap.add_argument('--backend', choices=['local', 'api'])
    ap.add_argument('--provider')
    ap.add_argument('--model')
    ap.add_argument('--base-url')
    ap.add_argument('--key-env', help='Environment VARIABLE NAME; never supply the secret itself')
    ap.add_argument('--live', action='store_true', help='Send a real test request; may incur charges')
    ap.add_argument('--report', type=Path, default=Path('reports/model_diagnostic.json'))
    args = ap.parse_args()
    cfg = Settings.load()
    for name, value in [('translation_backend', args.backend), ('provider', args.provider),
                        ('model', args.model), ('base_url', args.base_url),
                        ('api_key_env', args.key_env)]:
        if value is not None:
            setattr(cfg, name, value)
    report = {
        'backend': cfg.translation_backend, 'provider': cfg.provider, 'model': cfg.model,
        'base_url': safe_url(cfg.base_url), 'key_env_name': cfg.api_key_env,
        'credential_available': bool(cfg.get_key()) if cfg.translation_backend == 'api' else None,
        'live_test_requested': args.live,
    }
    try:
        kwargs = _request_params(cfg)
        report['normalized_model'] = kwargs['model']
        report['effective_base_url'] = safe_url(kwargs.get('api_base', ''))
        report['configured_timeout_seconds'] = kwargs['timeout']
        report['configured_retry_attempts'] = cfg.retry_attempts
        report['preflight'] = 'PASS'
        if args.live:
            report['connection'] = test_connection(cfg)
            report['result'] = 'PASS'
        else:
            report['connection'] = 'NOT_RUN (add --live for a real provider test)'
            report['result'] = 'PREFLIGHT_PASS'
    except Exception as exc:
        report['result'] = 'FAIL'
        report['error'] = f'{type(exc).__name__}: {exc}'  # sanitized by the provider adapter
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report['result'] == 'FAIL' else 0


if __name__ == '__main__':
    raise SystemExit(main())
