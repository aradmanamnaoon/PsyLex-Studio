"""PsyLex desktop theme — understated paper/graphite with forest-green actions.

Every color in the stylesheet comes from PALETTES. The functional tokens are
shared by dark/light modes and checked for text contrast in the test suite.
There are no gradients or decorative alpha-glass surfaces.
"""
from __future__ import annotations

from string import Template

PALETTES = {
    "light": {
        "background": "#F5F5F2", "surface": "#FFFFFF", "surface_alt": "#F0F3EE",
        "border": "#CED5CE", "text": "#19271F", "muted": "#526157",
        "primary": "#205D47", "on_primary": "#FFFFFF",
        "success": "#236444", "warning": "#825117", "danger": "#A33336",
        "focus": "#1C7057", "hover": "#EDF3EE", "active": "#DAE8DF",
        "disabled": "#657168", "disabled_bg": "#EFF1ED",
        "selection": "#D5E7DA", "on_selection": "#19271F",
    },
    "dark": {
        "background": "#141B18", "surface": "#202824", "surface_alt": "#26332C",
        "border": "#4B5A50", "text": "#F0F4EE", "muted": "#B3C0B7",
        "primary": "#92C6A9", "on_primary": "#10251A",
        "success": "#8AD3A1", "warning": "#E1BC7A", "danger": "#F2A1A1",
        "focus": "#A6D5BA", "hover": "#2E3B33", "active": "#374F40",
        "disabled": "#84938A", "disabled_bg": "#29312C",
        "selection": "#374F40", "on_selection": "#F0F4EE",
    },
}

# The explicit QLabel transparency rule avoids black rectangles on Windows.
_QSS = Template(r"""
QMainWindow, QDialog, QWidget#appRoot {
    background: $background;
    color: $text;
    font-family: 'Segoe UI';
    font-size: 10pt;
}
QWidget { color: $text; font-family: 'Segoe UI'; font-size: 10pt; }
QLabel { background: transparent; border: none; }
QLabel#emptyTitle { font-size: 16pt; font-weight: 650; }
QLabel#formatNote { color: $muted; font-weight: 600; }
QLabel#heading { font-size: 20pt; font-weight: 700; color: $text; }
QLabel#heroTitle { font-size: 16pt; font-weight: 700; color: $text; }
QLabel#sectionTitle { font-size: 11pt; font-weight: 700; color: $text; }
QLabel#muted { color: $muted; }
QLabel#statusSuccess { color: $success; font-weight: 600; }
QLabel#statusWarning { color: $warning; font-weight: 600; }
QLabel#statusDanger { color: $danger; font-weight: 600; }
QLabel#pillLine, QLabel#badgeLine, QLabel#statusPill, QLabel#modePill {
    background: $surface_alt;
    color: $text;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 6px 10px;
}
QFrame#activityPanel {
    background: $surface_alt;
    border: 1px solid $focus;
    border-radius: 8px;
}
QLabel#activityTitle { font-size: 10pt; font-weight: 700; color: $text; }
QProgressBar { padding: 1px; }
QProgressBar::chunk { background: $primary; }
QFrame#heroCard {
    background: $surface;
    border: 1px solid $border;
    border-radius: 10px;
}
QFrame#toolbarCard, QFrame#reviewPanel, QFrame#sectionCard {
    background: $surface;
    border: 1px solid $border;
    border-radius: 9px;
}
QFrame#emptyState {
    background: $surface_alt;
    border: 1px dashed $border;
    border-radius: 9px;
}
QFrame#feedbackBar { background: transparent; border-top: 1px solid $border; }
QSplitter::handle { background: $border; }
QSplitter::handle:hover { background: $focus; }
QTextEdit, QPlainTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
QListWidget, QTableWidget {
    background: $surface;
    color: $text;
    border: 1px solid $border;
    border-radius: 7px;
    padding: 7px 9px;
    selection-background-color: $selection;
    selection-color: $on_selection;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QTableWidget:focus {
    border: 2px solid $focus;
}
QLineEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled,
QSpinBox:disabled, QDoubleSpinBox:disabled, QTextEdit:disabled {
    background: $disabled_bg;
    color: $disabled;
}
QComboBox#modeSelector {
    background: $surface_alt;
    color: $text;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 7px 43px 7px 12px;
    font-weight: 650;
}
QComboBox#modeSelector:hover { background: $hover; border-color: $focus; }
QComboBox#modeSelector::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 34px;
    border-left: 1px solid $border;
}
QComboBox#modeSelector::down-arrow { image: none; width: 0px; height: 0px; }
QComboBox QAbstractItemView {
    background: $surface;
    color: $text;
    border: 1px solid $border;
    outline: none;
    selection-background-color: $selection;
    selection-color: $on_selection;
}
QPushButton {
    background: $surface_alt;
    color: $text;
    border: 1px solid $border;
    border-radius: 7px;
    padding: 8px 13px;
    font-weight: 600;
    min-height: 19px;
}
QPushButton:hover { background: $hover; border-color: $focus; }
QPushButton:pressed { background: $active; }
QPushButton:focus { border: 2px solid $focus; }
QPushButton#primary {
    background: $primary;
    color: $on_primary;
    border: 1px solid $primary;
    font-weight: 700;
}
QPushButton#primary:hover { background: $primary; border: 2px solid $focus; }
QPushButton#primary:pressed { background: $active; color: $text; }
QPushButton#danger { color: $danger; border: 1px solid $danger; }
QPushButton#danger:hover { background: $hover; }
QPushButton:disabled {
    background: $disabled_bg;
    color: $disabled;
    border-color: $border;
}
QTabWidget::pane {
    background: $surface;
    border: 1px solid $border;
    border-radius: 8px;
    margin-top: 4px;
}
QTabBar::tab {
    background: $surface_alt;
    color: $muted;
    border: 1px solid $border;
    padding: 9px 14px;
    margin-right: 3px;
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
    font-weight: 600;
}
QTabBar::tab:selected {
    background: $surface;
    color: $text;
    border-bottom: 2px solid $primary;
}
QTabBar::tab:hover { background: $hover; color: $text; }
QGroupBox {
    background: transparent;
    border: 1px solid $border;
    border-radius: 8px;
    margin-top: 18px;
    padding: 12px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    color: $text;
    background: $surface;
    padding: 0 6px;
}
QTableWidget::item:selected { background: $selection; color: $on_selection; }
QHeaderView::section {
    background: $surface_alt;
    color: $text;
    border: none;
    border-right: 1px solid $border;
    border-bottom: 1px solid $border;
    padding: 8px;
    font-weight: 650;
}
QProgressBar {
    background: $surface_alt;
    color: $text;
    border: 1px solid $border;
    border-radius: 6px;
    min-height: 18px;
    text-align: center;
}
QProgressBar::chunk { background: $primary; border-radius: 5px; }
QScrollArea#documentScroll, QScrollArea#settingsScroll {
    border: none;
    background: transparent;
}
QMenuBar, QMenu, QStatusBar {
    background: $surface;
    color: $text;
    border-color: $border;
}
QMenu::item:selected { background: $selection; color: $on_selection; }
QToolTip { background: $surface_alt; color: $text; border: 1px solid $border; }
QCheckBox, QRadioButton { background: transparent; color: $text; spacing: 8px; }
QCheckBox:disabled, QRadioButton:disabled { color: $disabled; }
""")

DARK = _QSS.substitute(PALETTES['dark'])
LIGHT = _QSS.substitute(PALETTES['light'])


def stylesheet(theme: str) -> str:
    if theme == 'system':
        try:
            from PySide6.QtGui import QGuiApplication
            theme = 'dark' if QGuiApplication.styleHints().colorScheme().name == 'Dark' else 'light'
        except Exception:
            theme = 'light'
    return LIGHT if theme == 'light' else DARK
