"""Reusable custom widgets, isolated from window construction.

Keeping the mode selector in its own module prevents accidental edits to the
text editor class (the source of a past DropTextEdit startup regression).
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QComboBox, QPlainTextEdit

from psylex.core.documents import INPUT_FORMATS
from psylex.ui.styles import PALETTES


class ModeSelector(QComboBox):
    """Accessible two-option selector with a reliably visible chevron."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('modeSelector')
        self.setFixedWidth(190)
        self.setMinimumHeight(40)
        self.setAccessibleName('Workspace mode')
        self.setToolTip('Switch between dictionary lookup and model translation')

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Theme-appropriate high-contrast arrow independent of platform style.
        dark = self.property('uiDark') is not False
        pen = QPen(QColor(PALETTES['dark' if dark else 'light']['text' if self.isEnabled() else 'disabled']), 2.1)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        right = self.width() - 18
        mid = self.height() // 2
        painter.drawLine(right - 6, mid - 2, right, mid + 4)
        painter.drawLine(right, mid + 4, right + 6, mid - 2)
        painter.end()


class DropTextEdit(QPlainTextEdit):
    """Text editor that emits file paths for supported drag-and-drop formats."""

    file_dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls() if event.mimeData().hasUrls() else []
        if urls and any(Path(url.toLocalFile()).suffix.lower() in INPUT_FORMATS for url in urls):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            accepted = [url.toLocalFile() for url in event.mimeData().urls()
                        if Path(url.toLocalFile()).suffix.lower() in INPUT_FORMATS]
            if accepted:
                self.file_dropped.emit(accepted[0])
                event.acceptProposedAction()
                return
        super().dropEvent(event)
