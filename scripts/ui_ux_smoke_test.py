r"""Real Qt lifecycle test for activity, cancellation, recovery and progress.

Windows: .\.venv\Scripts\python.exe scripts\ui_ux_smoke_test.py
This does not contact any cloud API, start Ollama or modify user data.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication
from psylex.core.config import Settings
from psylex.core.database import Database
from psylex.core.models import Translation
from psylex.ui.main_window import MainWindow
from psylex.ui.settings_dialog import SettingsDialog


def until(app, predicate, seconds=8.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        time.sleep(0.015)
    raise AssertionError('Timed out waiting for Qt worker / UI state')


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    with tempfile.TemporaryDirectory(prefix='psylex-ux-') as folder:
        db = Database(Path(folder) / 'ux.sqlite')
        cfg = Settings(mode='translation', translation_backend='local', provider='Ollama')
        with patch.object(MainWindow, '_load_seed', lambda self: None), \
             patch.object(Settings, 'save', lambda self, path=None: None):
            window = MainWindow(db, cfg)
            window.show()
            app.processEvents()
            assert window.translation_activity.isHidden()
            assert window.cancel_translation_btn.accessibleName() == 'Cancel current translation'

            # Cancellation suppresses results, even if an underlying network call
            # completes after the user has asked to cancel.
            def delayed(text, save=True):
                time.sleep(.35)
                return Translation(text, 'NEW SHOULD NOT APPEAR', 'local', None)
            window.pipeline.translate = delayed
            window.output.setPlainText('preserve old translation')
            window.input.setPlainText('novel scientific paragraph')
            before = len(db.history())
            window.translate_button.click()
            assert window.active_job is not None
            until(app, lambda: window.translation_activity.isVisible())
            assert window.translation_spinner.maximum() == 0
            assert not window.translate_button.isEnabled()
            window.cancel_translation_btn.click()
            assert window.active_job.stop_event.is_set()
            until(app, lambda: not window.active_job.isRunning())
            until(app, lambda: window.translation_activity.isHidden())
            assert window.output.toPlainText() == 'preserve old translation'
            assert len(db.history()) == before
            assert 'cancelled' in window.translation_notice.text().lower()

            # Success writes history once, shows status and re-enables controls.
            window.pipeline.translate = lambda text, save=True: Translation(text, 'ترجمهٔ آزمایشی', 'local', None)
            window.translate_button.click()
            until(app, lambda: not window.active_job.isRunning())
            until(app, lambda: window.translation_activity.isHidden())
            assert window.output.toPlainText() == 'ترجمهٔ آزمایشی'
            assert len(db.history()) == before + 1
            assert window.translate_button.isEnabled()
            assert 'completed' in window.translation_notice.text().lower()

            # Provider errors stay inline instead of opening an obstructive dialog.
            def fail(text, save=True):
                raise RuntimeError('simulated provider unavailable')
            window.pipeline.translate = fail
            window.translate_button.click()
            until(app, lambda: not window.active_job.isRunning())
            until(app, lambda: window.translation_activity.isHidden())
            assert 'simulated provider unavailable' in window.translation_notice.text()
            assert window.output.toPlainText() == 'ترجمهٔ آزمایشی'
            assert len(db.history()) == before + 1

            # Batch worker provides real completed-row counts and an exportable result.
            window.pipeline.translate = lambda text, save=True: Translation(text, 'ترجمه', 'local', None)
            window.batch_rows = ['one', 'two', 'three']
            window.batch_table.setRowCount(3)
            window._batch_translate()
            until(app, lambda: not window.active_job.isRunning())
            until(app, lambda: not window.batch_progress.isVisible())
            assert len(window.batch_results) == 3
            assert window.batch_progress.value() == 3
            assert 'Finished' in window.batch_activity.text()
            assert window.batch_cancel_btn.isEnabled() is False

            # Document progress is quantitative when segment/page count is known.
            window._document_progress(2, 5, 'Recognizing document page 2 of 5')
            assert window.doc_progress.maximum() == 5
            assert window.doc_progress.value() == 2
            assert '2 of 5' in window.doc_activity.text()

            # Settings connection test has feedback and cannot close mid-request.
            settings = SettingsDialog(cfg, window)
            settings.show()
            app.processEvents()
            with patch('psylex.ui.settings_dialog.test_connection',
                       side_effect=lambda _: (time.sleep(.3), 'Connected')[1]):
                settings._test()
                assert settings.connection_progress.isVisible()
                assert not settings.test_button.isEnabled()
                settings.reject()
                assert settings.isVisible(), 'Settings closed while its QThread was running'
                until(app, lambda: not settings.thread.isRunning())
                until(app, lambda: not settings.connection_progress.isVisible())
                assert settings.test_button.isEnabled()
            settings.reject()
            window.close()
            db.close()
    print('PASS: translation activity/cancel/success/failure, batch progress, document progress, Settings test lifecycle')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
