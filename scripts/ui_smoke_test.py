"""Headless-friendly GUI smoke test for the PsyLex Studio layout.

Run on Windows after installing requirements:
    python scripts/ui_smoke_test.py

Run without a visible window where Qt's offscreen platform is available:
    set QT_QPA_PLATFORM=offscreen
    python scripts/ui_smoke_test.py

This exercises layout and theme only; it makes no network calls.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# Allow direct execution from scripts/ while preserving the project import root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from psylex.core.config import Settings
from psylex.core.database import Database
from psylex.core.documents import DocumentData, TextBlock, save_document


def main() -> int:
    from PySide6.QtWidgets import QApplication
    from psylex.ui.main_window import MainWindow
    from psylex.ui.styles import stylesheet

    app = QApplication.instance() or QApplication(sys.argv)
    original_seed = MainWindow._load_seed
    MainWindow._load_seed = lambda self: None  # no heavy dictionary import
    try:
        with tempfile.TemporaryDirectory(prefix='psylex-ui-') as folder:
            db = Database(Path(folder) / 'ui.sqlite3')
            try:
                original_save = Settings.save
                Settings.save = lambda _self, path=None: None
                window = MainWindow(db, Settings())
                window.show()
                for width, height in [(1280, 850), (1024, 720), (960, 650)]:
                    window.resize(width, height)
                    app.processEvents()
                    window.tabs.setCurrentWidget(window.document_tab)
                    app.processEvents()
                    assert window.doc_pages.currentIndex() == 0, 'Empty state not visible'
                    assert window.doc_pages.height() >= 160, 'Document content not visible'

                    sample = DocumentData('example.txt', '.txt', [
                        TextBlock('working memory', translated='حافظهٔ کاری'),
                        TextBlock('attentional bias', translated='سوگیری توجه'),
                    ])
                    window._document_loaded(sample)
                    app.processEvents()
                    assert window.doc_pages.currentIndex() == 1
                    assert window.doc_edit.height() >= 65, ('Review editor collapsed', window.doc_edit.height())
                    assert window.doc_table.height() >= 100, ('Table collapsed', window.doc_table.height())
                    assert window.doc_source.toPlainText() == 'working memory'
                    assert not window.doc_export_btn.isEnabled()
                    window._document_complete(sample)
                    assert window.doc_export_btn.isEnabled()
                    # Test actual Qt Persian PDF exporter under the Qt application.
                    pdf_path = Path(folder) / f'persian_{width}.pdf'
                    save_document(sample, pdf_path)
                    assert pdf_path.exists() and pdf_path.stat().st_size > 600
                    import fitz
                    with fitz.open(pdf_path) as exported_pdf:
                        assert exported_pdf.page_count >= 1
                    window.doc_pages.setCurrentIndex(0)
                for theme in ['light', 'dark', 'system']:
                    window.setStyleSheet(stylesheet(theme))
                    app.processEvents()
                window.close()
                print('UI smoke test PASS: empty state, review editor, PDF export, three sizes, three themes.')
            finally:
                Settings.save = original_save
                db.close()
    finally:
        MainWindow._load_seed = original_seed
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
