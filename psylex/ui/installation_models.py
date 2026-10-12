"""Optional first-setup model selection, launched by the Windows installer.

It uses the already-bundled Qt runtime: end users do not need Python. Network
probes stay on loopback and never transmit prompts or credentials.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox,
    QProgressBar, QPushButton, QVBoxLayout,
)

from psylex.core.config import Settings
from psylex.core.local_setup import configure_detected_model
from psylex.providers.native_http import LocalServer, discover_local_servers


class _DiscoveryWorker(QThread):
    completed = Signal(object, str)

    def __init__(self, configured_url: str):
        super().__init__()
        self.configured_url = configured_url

    def run(self) -> None:
        try:
            servers = discover_local_servers(timeout=1.5, configured_url=self.configured_url)
            self.completed.emit(servers, '')
        except Exception as exc:
            self.completed.emit([], f'{type(exc).__name__}: {exc}')


class InstallLocalModelDialog(QDialog):
    """Run after installation; selection is an explicit, reversible choice."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg = Settings.load()
        self.worker: _DiscoveryWorker | None = None
        self._choices: list[tuple[LocalServer, str]] = []
        self.setWindowTitle('PsyLex Studio · Find local models')
        self.setMinimumSize(640, 420)
        self.resize(740, 490)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(14)
        headline = QLabel('Connect a local language model')
        headline.setObjectName('setupTitle')
        headline.setStyleSheet('font-size: 20px; font-weight: 700;')
        layout.addWidget(headline)
        explanation = QLabel(
            'PsyLex checks running inference servers on this computer (Ollama, '
            'LM Studio, llama.cpp and vLLM). It will not download models, '
            'start a service, or send any documents or API keys. '
            'You can skip this step and use Dictionary or OpenRouter instead.'
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        self.status = QLabel('Preparing local model discovery…')
        self.status.setWordWrap(True)
        self.status.setAccessibleName('Local model discovery status')
        layout.addWidget(self.status)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setAccessibleName('Scanning local model servers')
        layout.addWidget(self.progress)

        self.models = QListWidget()
        self.models.setAccessibleName('Detected local models')
        self.models.setToolTip('Select the model to use for local translation.')
        self.models.itemSelectionChanged.connect(self._selection_changed)
        layout.addWidget(self.models, 1)

        self.hint = QLabel('If no models appear, start Ollama or start the LM Studio local server, then click Scan again.')
        self.hint.setWordWrap(True)
        self.hint.setObjectName('muted')
        layout.addWidget(self.hint)
        buttons = QHBoxLayout()
        self.rescan = QPushButton('Scan again')
        self.rescan.setAccessibleName('Scan again for running local model servers')
        self.rescan.clicked.connect(self.start_scan)
        self.skip = QPushButton('Skip for now')
        self.skip.clicked.connect(self.reject)
        self.use_model = QPushButton('Use selected model')
        self.use_model.setDefault(True)
        self.use_model.clicked.connect(self._save_selection)
        buttons.addWidget(self.rescan)
        buttons.addStretch(1)
        buttons.addWidget(self.skip)
        buttons.addWidget(self.use_model)
        layout.addLayout(buttons)
        self._selection_changed()
        QTimer.singleShot(0, self.start_scan)

    def start_scan(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        self._choices.clear()
        self.models.clear()
        self.progress.show()
        self.rescan.setEnabled(False)
        self.use_model.setEnabled(False)
        self.status.setText('Looking for running local servers on localhost…')
        # Never probe a remote custom URL or send credentials.
        self.worker = _DiscoveryWorker(self.cfg.base_url)
        self.worker.completed.connect(self._scan_complete)
        self.worker.finished.connect(self._scan_finished)
        self.worker.start()

    def _scan_complete(self, servers: list[LocalServer], error: str) -> None:
        for server in servers:
            for model in server.models:
                idx = len(self._choices)
                self._choices.append((server, model))
                item = QListWidgetItem(f'{server.provider}  ·  {model}\n{server.url}')
                item.setData(Qt.ItemDataRole.UserRole, idx)
                item.setToolTip(f'{server.provider}: {model}  ({server.url})')
                self.models.addItem(item)
        if self._choices:
            self.models.setCurrentRow(0)
            self.status.setText(f'Found {len(self._choices)} available model(s). Choose one to configure translation.')
        elif error:
            self.status.setText('Local scan could not complete: ' + error)
        else:
            self.status.setText(
                'No running local model server detected. This does not mean you have no models installed. '
                'Start your inference server and Scan again, or Skip for now.'
            )
        self._selection_changed()

    def _scan_finished(self) -> None:
        self.progress.hide()
        self.rescan.setEnabled(True)
        self._selection_changed()

    def _selection_changed(self) -> None:
        self.use_model.setEnabled(self.models.currentItem() is not None
                                  and not (self.worker and self.worker.isRunning()))

    def _save_selection(self) -> None:
        selected = self.models.currentItem()
        if selected is None:
            return
        i = selected.data(Qt.ItemDataRole.UserRole)
        if not isinstance(i, int) or not (0 <= i < len(self._choices)):
            return
        server, model = self._choices[i]
        try:
            updated = configure_detected_model(self.cfg, server, model)
            updated.save()
        except Exception as exc:
            QMessageBox.warning(self, 'Could not configure the model',
                                'No settings were changed. ' + str(exc))
            return
        self.accept()

    def reject(self) -> None:
        if self.worker and self.worker.isRunning():
            self.status.setText('Please wait for the short local scan to finish before closing.')
            return
        super().reject()

    def closeEvent(self, event) -> None:
        if self.worker and self.worker.isRunning():
            event.ignore()
            self.status.setText('Finishing local scan; this should take only a few seconds…')
        else:
            super().closeEvent(event)


def run_installation_model_setup() -> int:
    """Entry point for Inno Setup; skip is success and does not edit settings."""
    import sys
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication
    from psylex.core.config import bundle_dir
    from psylex.ui.styles import stylesheet

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName('PsyLex Studio')
    icon_path = bundle_dir() / 'assets' / 'branding' / 'logo_icon.png'
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))
    cfg = Settings.load()
    app.setStyleSheet(stylesheet(cfg.theme))
    dialog = InstallLocalModelDialog()
    dialog.exec()
    return 0
