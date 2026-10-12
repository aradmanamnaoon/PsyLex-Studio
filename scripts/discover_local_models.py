r"""Safely list responding localhost inference servers, without keys or prompts.

Windows:
    .\.venv\Scripts\python.exe scripts\discover_local_models.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from psylex.providers.native_http import discover_local_servers


def main() -> int:
    servers = discover_local_servers(timeout=1.0)
    print(json.dumps([
        {"provider": srv.provider, "base_url": srv.url, "models": list(srv.models)}
        for srv in servers
    ], ensure_ascii=False, indent=2))
    if not servers:
        print('No local HTTP inference server responded. This does NOT mean no models are installed.')
        print('Ollama: start its service and run `ollama list` and `ollama serve` if needed.')
        print('LM Studio: load a model and start the Developer / Local Server.')
        print('Other runtimes: configure the server URL in Settings manually.')
        return 1
    print('Select one matching provider, base URL and exact model ID in PsyLex Settings.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
