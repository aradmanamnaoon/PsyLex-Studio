r"""Run the actual PySide6 GUI without any cloud calls or persistent data changes.

Windows:
  .\.venv\Scripts\python.exe scripts\ui_click_smoke_test.py

Linux/CI:
  QT_QPA_PLATFORM=offscreen python scripts/ui_click_smoke_test.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

from psylex.core.config import Settings
from psylex.core.database import Database
from psylex.core.models import DictionaryEntry
from psylex.ui.main_window import MainWindow
from psylex.ui.settings_dialog import SettingsDialog


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    with tempfile.TemporaryDirectory(prefix='psylex-mode-test-') as folder:
        db = Database(Path(folder) / 'ui-test.sqlite')
        db.insert_entries([
            DictionaryEntry('working memory', 'حافظهٔ کاری', 'fixture.docx', 'table 1 row 1', .99),
            DictionaryEntry('working memory', 'حافظهٔ فعال', 'fixture.docx', 'table 1 row 2', .78),
        ])
        cfg = Settings(mode='dictionary')
        with patch.object(MainWindow, '_load_seed', lambda _self: None), patch.object(
            Settings, 'save', lambda _self, path=None: None
        ):
            window = MainWindow(db, cfg)
            window.show()
            app.processEvents()
            assert window.mode_selector.count() == 2
            assert window.tabs.currentWidget() is window.dictionary_tab
            assert window.mode_selector.currentData() == 'dictionary'
            assert window.dict_query is not None

            window.dict_query.setText('working memory')
            window._dict_search()
            assert window.dict_results.rowCount() == 2, 'Expected two grounded dictionary equivalents'
            assert window.dict_results.item(0, 1).text() == 'حافظهٔ کاری'
            assert 'fixture.docx' in window.dict_detail.toPlainText()
            window.dict_copy_btn.click()
            assert QApplication.clipboard().text() == 'حافظهٔ کاری'

            settings = SettingsDialog(cfg, window)
            assert settings.tabs.count() == 5
            assert settings.backend.count() == 2
            settings.backend.setCurrentIndex(settings.backend.findData('api'))
            assert settings.provider.currentText() == 'OpenAI'
            # Switching providers must not destroy a previously edited model,
            # base URL or pending key (the original UI did).
            settings.provider.setCurrentText('OpenRouter')
            settings.model.setText('openrouter/openrouter/free')
            settings.key.setText('unsaved-probe-key')
            settings.backend.setCurrentIndex(settings.backend.findData('local'))
            assert settings.provider.currentText() == 'Ollama'
            settings.backend.setCurrentIndex(settings.backend.findData('api'))
            assert settings.provider.currentText() == 'OpenRouter'
            assert settings.model.text() == 'openrouter/openrouter/free'
            assert settings.key.text() == 'unsaved-probe-key'
            # Test Connection must not touch OS credential storage until Save.
            seen = []
            with patch('psylex.ui.settings_dialog.test_connection',
                       side_effect=lambda c: (seen.append(c.session_api_key), 'Connected')[1]), \
                 patch.object(Settings, 'set_key', side_effect=AssertionError('premature secret save')):
                settings._test()
                assert settings.thread.wait(5000), 'Connection check thread stalled'
                app.processEvents()
                assert seen == ['unsaved-probe-key']
            settings.close()

            # Test the actual Settings button, including modal window construction.
            button = next((x for x in window.findChildren(QPushButton)
                           if x.accessibleName() == 'Open settings'), None)
            assert button is not None
            opened = []
            def close_dialog():
                modal = QApplication.activeModalWidget()
                opened.append(isinstance(modal, SettingsDialog))
                if modal is not None:
                    modal.reject()
            QTimer.singleShot(90, close_dialog)
            button.click()
            app.processEvents()
            assert opened == [True], 'Settings control failed to open dialog'

            window.mode_selector.setCurrentIndex(window.mode_selector.findData('translation'))
            app.processEvents()
            assert window.cfg.mode == 'translation'
            assert window.tabs.currentWidget() is window.translation_tab
            window.mode_selector.setCurrentIndex(window.mode_selector.findData('dictionary'))
            app.processEvents()
            assert window.cfg.mode == 'dictionary'
            assert window.tabs.currentWidget() is window.dictionary_tab

            # Translation mode uses the configured backend; this test never calls it.
            window.dict_results.selectRow(0)
            window._dict_to_translation()
            assert window.cfg.mode == 'translation'
            assert window.input.toPlainText() == 'working memory'
            window.translate_button.click()
            assert window.active_job is not None
            loop = QEventLoop()
            window.active_job.finished.connect(loop.quit)
            QTimer.singleShot(12000, loop.quit)
            if window.active_job.isRunning():
                loop.exec()
            app.processEvents()
            assert not window.active_job.isRunning(), 'Translation worker timed out'
            assert window.output.toPlainText() == 'حافظهٔ کاری'
            window._copy_translation()
            assert QApplication.clipboard().text() == 'حافظهٔ کاری'
            with patch.object(QMessageBox, 'information', return_value=QMessageBox.StandardButton.Ok):
                window.yes_btn.click()
            assert db.correction('working memory') == 'حافظهٔ کاری'
            window.close()
    print('PASS: dictionary lookup, provenance, copy, Settings, both modes, translation, and feedback.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
