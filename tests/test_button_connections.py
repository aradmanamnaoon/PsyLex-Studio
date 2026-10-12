"""Fast structural checks that catch unbound controls without Qt installed."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_settings_scroll_widgets_imported():
    path = ROOT / "psylex/ui/settings_dialog.py"
    module = ast.parse(path.read_text(encoding="utf-8"))
    imports = {alias.name for node in ast.walk(module)
               if isinstance(node, ast.ImportFrom) and node.module == "PySide6.QtWidgets"
               for alias in node.names}
    assert {"QScrollArea", "QFrame"} <= imports


def test_mode_is_a_real_two_workflow_control():
    source = (ROOT / 'psylex/ui/main_window.py').read_text(encoding='utf-8')
    widget = (ROOT / 'psylex/ui/widgets.py').read_text(encoding='utf-8')
    assert 'self.mode_selector = ModeSelector()' in source
    assert "self.mode_selector.addItem('Dictionary', 'dictionary')" in source
    assert "self.mode_selector.addItem('Translation', 'translation')" in source
    assert "self.mode_selector.addItem('Local LLM', 'local')" not in source
    assert "self.mode_selector.addItem('Cloud API', 'api')" not in source
    assert 'self.mode_selector.currentIndexChanged.connect(self._mode_changed)' in source
    assert 'class ModeSelector(QComboBox):' in widget
    assert 'class DropTextEdit(QPlainTextEdit):' in widget
    assert 'self.mode_selector.blockSignals(True)' in source
    assert 'self.mode_label = QLabel' not in source



def test_click_handlers_exist_and_are_connected():
    source = (ROOT / "psylex/ui/main_window.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    main = next(node for node in module.body if isinstance(node, ast.ClassDef)
                and node.name == "MainWindow")
    functions = {node.name for node in main.body if isinstance(node, ast.FunctionDef)}
    handlers = {
        "_settings", "_mode_changed", "_dict_search", "_dict_select", "_dict_copy",
        "_dict_correct", "_translate", "_favorite_current", "_feedback",
        "_copy_translation", "_choose_document", "_document_translate", "_document_export",
        "_batch_import", "_batch_translate", "_batch_export", "_export_feedback",
    }
    assert handlers <= functions
    assert "settings_btn.clicked.connect(self._settings)" in source
    assert "self.translate_button.clicked.connect(self._translate)" in source
    assert "self.doc_translate_button.clicked.connect(self._document_translate)" in source
    assert "self.doc_export_btn.clicked.connect(self._document_export)" in source
    assert "copy.clicked.connect(self._copy_translation)" in source


def test_can_compile_all_ui_modules():
    for name in ("settings_dialog.py", "main_window.py", "styles.py"):
        source = (ROOT / "psylex/ui" / name).read_text(encoding="utf-8")
        compile(source, name, "exec")
