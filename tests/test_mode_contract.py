"""Structural guardrails against the actual UI regressions seen in prior releases."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_two_modes_only_and_usable_dictionary():
    main = (ROOT / 'psylex/ui/main_window.py').read_text(encoding='utf-8')
    assert "self.mode_selector.addItem('Dictionary', 'dictionary')" in main
    assert "self.mode_selector.addItem('Translation', 'translation')" in main
    assert "self.mode_selector.addItem('Local LLM', 'local')" not in main
    assert "self.mode_selector.addItem('Cloud API', 'api')" not in main
    assert 'self.dictionary_service.search(query, limit=80)' in main
    for handler in ('_dict_search', '_dict_select', '_dict_copy', '_dict_correct',
                    '_dict_to_translation', '_set_workspace_mode'):
        assert f'def {handler}(' in main
    assert 'self.tabs.setCurrentWidget(target)' in main


def test_drag_drop_widget_independent_of_mode_selector():
    src = (ROOT / 'psylex/ui/widgets.py').read_text(encoding='utf-8')
    assert 'class DropTextEdit(QPlainTextEdit):' in src
    assert 'class ModeSelector(QComboBox):' in src
    assert 'def paintEvent(self, event)' in src
    assert 'self.file_dropped.emit(accepted[0])' in src


def test_settings_backend_is_separate_from_workspace_mode():
    source = (ROOT / 'psylex/ui/settings_dialog.py').read_text(encoding='utf-8')
    assert "self.backend.addItem('Local model (on your computer)', 'local')" in source
    assert "self.backend.addItem('Online API provider', 'api')" in source
    assert 'c.translation_backend = self.backend.currentData()' in source
    assert 'c.mode = self.mode.currentText()' not in source
    assert 'self._backend_changed(self.backend.currentIndex())' in source


def test_ui_modules_compile_and_known_missing_imports_present():
    widgets = (ROOT / 'psylex/ui/widgets.py').read_text(encoding='utf-8')
    settings = (ROOT / 'psylex/ui/settings_dialog.py').read_text(encoding='utf-8')
    for name in ['main_window.py', 'settings_dialog.py', 'widgets.py', 'styles.py']:
        path = ROOT / 'psylex/ui' / name
        compile(path.read_text(encoding='utf-8'), str(path), 'exec')
    assert 'QScrollArea' in settings and 'QFrame' in settings
    assert 'from PySide6.QtGui import QColor, QPainter, QPen' in widgets
