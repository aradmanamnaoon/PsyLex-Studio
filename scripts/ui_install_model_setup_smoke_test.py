r"""Exercise the actual Qt installation-time model picker without external servers.

Run on Windows:
    .\.venv\Scripts\python.exe scripts\ui_install_model_setup_smoke_test.py
This test never contacts a model server, modifies user settings, or installs data.
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from psylex.core.config import Settings
from psylex.providers.native_http import LocalServer


def wait_for_scan(app, dialog, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if dialog.worker and not dialog.worker.isRunning() and dialog.rescan.isEnabled():
            app.processEvents()
            return
        time.sleep(.025)
    raise AssertionError('Installation model scan did not finish in time')


def main() -> int:
    from PySide6.QtWidgets import QApplication, QDialog
    from psylex.ui.installation_models import InstallLocalModelDialog

    app = QApplication.instance() or QApplication(sys.argv)
    srv = LocalServer('Ollama', 'http://127.0.0.1:11434', ('smoke-model:latest',))
    original_save = Settings.save
    with tempfile.TemporaryDirectory(prefix='psylex-install-model-qa-') as tmp:
        dest = Path(tmp) / 'settings.json'
        with patch.object(Settings, 'load', return_value=Settings()), \
                patch.object(Settings, 'save', lambda settings, path=None: original_save(settings, dest)), \
                patch('psylex.ui.installation_models.discover_local_servers', return_value=[srv]):
            dialog = InstallLocalModelDialog()
            dialog.show()
            wait_for_scan(app, dialog)
            assert dialog.models.count() == 1
            assert dialog.use_model.isEnabled()
            dialog.use_model.click()
            assert dialog.result() == QDialog.DialogCode.Accepted
            import json
            payload = json.loads(dest.read_text(encoding='utf-8'))
            assert payload['provider'] == 'Ollama'
            assert payload['model'] == 'smoke-model:latest'
            assert payload['translation_backend'] == 'local'
        # No discovery -> no settings side effects.
        dest.unlink()
        with patch.object(Settings, 'load', return_value=Settings()), \
                patch.object(Settings, 'save', lambda settings, path=None: original_save(settings, dest)), \
                patch('psylex.ui.installation_models.discover_local_servers', return_value=[]):
            dialog = InstallLocalModelDialog()
            dialog.show()
            wait_for_scan(app, dialog)
            assert dialog.models.count() == 0
            assert not dialog.use_model.isEnabled()
            assert 'No running' in dialog.status.text()
            dialog.skip.click()
            assert dialog.result() == QDialog.DialogCode.Rejected
            assert not dest.exists()
    print('Installation model picker PASS: populated and empty state; explicit choice; no writes on skip.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
