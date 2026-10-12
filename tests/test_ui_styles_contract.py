"""Tests for the Windows black-label regression without requiring Qt to import."""
from __future__ import annotations

from pathlib import Path

from psylex.ui.styles import DARK, LIGHT, stylesheet


def test_no_opaque_label_bars_inside_cards():
    for sheet in (DARK, LIGHT):
        assert 'QLabel { background: transparent; border: none; }' in sheet
        assert 'QFrame#heroCard' in sheet
        assert 'QFrame#reviewPanel' in sheet
        assert 'QFrame#emptyState' in sheet


def test_themes_exist_and_system_has_fallback():
    assert stylesheet('dark') == DARK
    assert stylesheet('light') == LIGHT
    assert stylesheet('system') in (DARK, LIGHT)


def test_documents_layout_has_reviewer_empty_state_and_unsaved_guard():
    src = (Path(__file__).resolve().parents[1] / 'psylex/ui/main_window.py').read_text(encoding='utf-8')
    for feature in (
        'QStackedWidget()',
        'setChildrenCollapsible(False)',
        'doc_source',
        'doc_apply_btn',
        '_document_select(self)',
        "'Unsaved correction'",
        "'Send document pages to cloud OCR?'",
    ):
        assert feature in src
