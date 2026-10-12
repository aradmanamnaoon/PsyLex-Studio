r"""Offline Windows GUI verification of provider credential editing and persistence.

Run: .\.venv\Scripts\python.exe scripts\ui_credentials_smoke_test.py
No real OS secrets are read, edited, or written during this test.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication, QLineEdit, QMessageBox
from psylex.core.config import Settings
from psylex.ui.settings_dialog import SettingsDialog


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    saved = {'OpenRouter': 'saved-openrouter-secret'}
    with tempfile.TemporaryDirectory(prefix='psylex-safe-credentials-') as tmp:
        path = Path(tmp) / 'settings.json'
        original_save = Settings.save
        def set_key(settings, key):
            if key:
                saved[settings.provider] = key
            else:
                saved.pop(settings.provider, None)
        with patch.object(Settings, 'get_stored_key', lambda settings, provider=None: saved.get(provider or settings.provider, '')), \
             patch.object(Settings, 'set_key', set_key), \
             patch.object(Settings, 'save', lambda settings, path_arg=None: original_save(settings, path)):
            initial = Settings(provider='OpenRouter', translation_backend='api',
                               model='openrouter/free', base_url='')
            dialog = SettingsDialog(initial)
            assert dialog.provider.currentText() == 'OpenRouter'
            assert dialog.key.text() == 'saved-openrouter-secret', 'Stored key was not restored'
            assert dialog.key.echoMode() == QLineEdit.EchoMode.Password, 'Key must open masked'
            assert 'saved-openrouter-secret' not in dialog.key_status.text(), 'Secret leaked to status'
            dialog.key_env.setText('OPENROUTER_API_KEY')
            assert 'environment variable takes precedence' in dialog.key_status.text()
            dialog.key_env.clear()
            dialog.key_toggle.click()
            assert dialog.key.echoMode() == QLineEdit.EchoMode.Normal
            dialog.key_toggle.click()
            assert dialog.key.echoMode() == QLineEdit.EchoMode.Password
            dialog.key.setText('cancelled-unsaved-edit')
            dialog.reject()
            assert saved['OpenRouter'] == 'saved-openrouter-secret', 'Cancel overwrote stored key'

            dialog = SettingsDialog(initial)
            dialog.key.setText('updated-openrouter-secret')
            dialog.provider.setCurrentText('OpenAI')
            dialog.key.setText('new-openai-secret')
            dialog.provider.setCurrentText('OpenRouter')
            assert dialog.key.text() == 'updated-openrouter-secret', 'Switch discarded key draft'
            dialog._save()
            assert saved['OpenRouter'] == 'updated-openrouter-secret'
            assert saved['OpenAI'] == 'new-openai-secret'
            text = path.read_text(encoding='utf-8')
            assert not any(secret in text for secret in saved.values()), 'Credential leaked to JSON'

            reopened = SettingsDialog(Settings.load(path))
            assert reopened.key.text() == 'updated-openrouter-secret', 'Saved key not shown masked on reopen'
            assert reopened.key.echoMode() == QLineEdit.EchoMode.Password
            reopened.provider.setCurrentText('OpenAI')
            assert reopened.key.text() == 'new-openai-secret', 'Other provider credential lost'
            reopened.provider.setCurrentText('OpenRouter')
            # Qt extension types may not permit monkeypatching class methods.
            # Patch the dialog module's reference, not the QMessageBox type.
            fake_message_box = SimpleNamespace(
                StandardButton=QMessageBox.StandardButton,
                question=lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
                warning=QMessageBox.warning,
            )
            with patch('psylex.ui.settings_dialog.QMessageBox', fake_message_box):
                reopened.key_remove.click()
            assert 'OpenRouter' in reopened._pending_key_removals
            assert saved['OpenRouter'] == 'updated-openrouter-secret', 'Removal must wait for Save'
            # Switching to another provider after Forget must not undo the
            # pending removal, even when the other provider has a saved key.
            reopened.provider.setCurrentText('OpenAI')
            assert reopened.key.text() == 'new-openai-secret'
            assert 'OpenRouter' in reopened._pending_key_removals
            reopened.provider.setCurrentText('OpenRouter')
            assert not reopened.key.text()
            assert 'OpenRouter' in reopened._pending_key_removals
            reopened._save()
            assert 'OpenRouter' not in saved
            assert saved['OpenAI'] == 'new-openai-secret'
            empty = SettingsDialog(Settings.load(path))
            assert not empty.key.text(), 'Removed credential reappeared'
            empty.reject()
            app.processEvents()
    print('PASS: credential masking, show/hide, Save/Cancel, per-provider persistence, and Forget.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
