"""Color accessibility and centralized theme contract; no Qt imports needed."""
from __future__ import annotations

from psylex.ui.styles import PALETTES, DARK, LIGHT, stylesheet


def luminance(hex_color):
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    channels = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4
                for v in channels]
    return .2126 * channels[0] + .7152 * channels[1] + .0722 * channels[2]


def contrast(foreground, background):
    light, dark = sorted([luminance(foreground), luminance(background)], reverse=True)
    return (light + .05) / (dark + .05)


def test_text_and_status_contrast_exceeds_wcag_aa():
    for mode, colors in PALETTES.items():
        for foreground in ('text', 'muted', 'success', 'warning', 'danger'):
            assert contrast(colors[foreground], colors['surface']) >= 4.5, (mode, foreground)
        assert contrast(colors['on_primary'], colors['primary']) >= 4.5, mode
        assert contrast(colors['on_selection'], colors['selection']) >= 4.5, mode


def test_flat_single_source_palette_and_required_interaction_states():
    assert stylesheet('dark') == DARK
    assert stylesheet('light') == LIGHT
    assert 'qlineargradient' not in DARK.lower() + LIGHT.lower()
    for colors in PALETTES.values():
        for token in ('background', 'surface', 'border', 'text', 'muted', 'primary',
                      'success', 'warning', 'danger', 'focus', 'hover', 'active', 'disabled'):
            assert len(colors[token]) == 7 and colors[token].startswith('#'), token
    for sheet in (DARK, LIGHT):
        assert 'QLabel { background: transparent; border: none; }' in sheet
        assert 'QComboBox#modeSelector::drop-down' in sheet
        assert 'QPushButton:disabled' in sheet
        assert 'QMenu::item:selected' in sheet
