"""Editable application settings, model connectivity, OCR, and UI preferences."""
from __future__ import annotations

from copy import deepcopy

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QFrame,
    QScrollArea,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from psylex.core.config import Settings
from psylex.core.ocr import ALL_OCR_ENGINES, ONLINE_OCR_ENGINES, engine_key_to_label, engine_label_to_key
from psylex.providers.models import LOCAL_URLS, PROVIDERS, test_connection
from psylex.providers.native_http import discover_local_servers


class ConnectionThread(QThread):
    done = Signal(str, bool)

    def __init__(self, cfg: Settings):
        super().__init__()
        self.cfg = deepcopy(cfg)

    def run(self) -> None:
        try:
            self.done.emit(test_connection(self.cfg), True)
        except Exception as exc:
            self.done.emit(str(exc), False)


class LocalDiscoveryThread(QThread):
    discovered = Signal(object)

    def __init__(self, configured_url: str):
        super().__init__()
        self.url = configured_url

    def run(self) -> None:
        self.discovered.emit(discover_local_servers(configured_url=self.url))


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.cfg = deepcopy(settings)
        self.thread: ConnectionThread | None = None
        self.discovery_thread: LocalDiscoveryThread | None = None
        self.setWindowTitle("Preferences • PsyLex Studio")
        self.resize(880, 720)
        layout = QVBoxLayout(self)
        info = QLabel("Configure language models, retrieval, OCR, feedback behavior, and interface preferences.")
        info.setObjectName("muted")
        info.setWordWrap(True)
        layout.addWidget(info)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self._model_tab()
        self._rag_tab()
        self._ocr_tab()
        self._prompt_tab()
        self._personalization_tab()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self._buttons = buttons
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _tab(self, label: str) -> QFormLayout:
        """Keep long provider forms scrollable at common laptop resolutions."""
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(4, 5, 4, 4)
        area = QScrollArea()
        area.setObjectName('settingsScroll')
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setWidgetResizable(True)
        content = QWidget()
        form = QFormLayout(content)
        form.setContentsMargins(12, 12, 12, 12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(12)
        area.setWidget(content)
        outer.addWidget(area)
        self.tabs.addTab(page, label)
        return form

    def _model_tab(self) -> None:
        form = self._tab("Models & API")
        self.backend = QComboBox()
        self.backend.addItem('Local model (on your computer)', 'local')
        self.backend.addItem('Online API provider', 'api')
        self.backend.setCurrentIndex(max(0, self.backend.findData(self.cfg.translation_backend)))
        self.backend.setAccessibleName('Translation backend')
        self.backend.currentIndexChanged.connect(self._backend_changed)
        form.addRow('Translation backend', self.backend)
        workflow_help = QLabel('Workspace mode is selected in the main window: Dictionary or Translation. '
                               'This setting controls how Translation calls a language model.')
        workflow_help.setWordWrap(True)
        form.addRow('', workflow_help)
        self.provider = QComboBox(); self.provider.addItems(list(PROVIDERS))
        preferred = next((k for k in PROVIDERS if k.lower() == self.cfg.provider.lower()), "Ollama")
        self.provider.setCurrentText(preferred); self.provider.currentTextChanged.connect(self._provider_changed)
        form.addRow("Provider", self.provider)
        self.model = QLineEdit(self.cfg.model); self.model.setPlaceholderText("e.g. ollama/qwen2.5:7b or openai/gpt-4.1-mini")
        form.addRow("Model ID", self.model)
        self.url = QLineEdit(self.cfg.base_url); self.url.setPlaceholderText("Optional custom base URL")
        form.addRow("Base URL", self.url)
        self.detect_button = QPushButton('Find running local servers and models')
        self.detect_button.setToolTip('Check localhost ports 11434, 1234, 8080 and 8000; no model prompt is sent.')
        self.detect_button.clicked.connect(self._detect_local)
        form.addRow('', self.detect_button)
        self.transport = QComboBox()
        self.transport.addItem('Direct HTTP (recommended)', 'native')
        self.transport.addItem('LiteLLM (compatibility)', 'litellm')
        self.transport.setCurrentIndex(max(0, self.transport.findData(self.cfg.transport)))
        form.addRow('Model connection method', self.transport)
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("Enter an API key, then Save")
        self.key.setAccessibleName('Provider API key')
        self.key.setToolTip('Saved securely to the OS keyring, never to settings.json.')
        self.key_toggle = QPushButton('Show')
        self.key_toggle.setCheckable(True)
        self.key_toggle.setAccessibleName('Show or hide API key')
        self.key_toggle.toggled.connect(self._toggle_key_visibility)
        self.key_remove = QPushButton('Forget')
        self.key_remove.setToolTip('Remove this provider key from Windows Credential Manager after Save.')
        self.key_remove.clicked.connect(self._forget_key)
        self.key.textChanged.connect(self._key_changed)
        self.key_row = QWidget()
        key_layout = QHBoxLayout(self.key_row)
        key_layout.setContentsMargins(0, 0, 0, 0)
        key_layout.setSpacing(6)
        key_layout.addWidget(self.key, 1)
        key_layout.addWidget(self.key_toggle)
        key_layout.addWidget(self.key_remove)
        form.addRow('API key (OS keyring)', self.key_row)
        self.key_status = QLabel()
        self.key_status.setWordWrap(True)
        self.key_status.setObjectName('muted')
        form.addRow('', self.key_status)
        self.key_env = QLineEdit(self.cfg.api_key_env); self.key_env.setPlaceholderText("Optional environment variable e.g. OPENAI_API_KEY")
        form.addRow("API key environment variable", self.key_env)
        self.temp = QDoubleSpinBox(); self.temp.setRange(0, 2); self.temp.setSingleStep(.05); self.temp.setValue(self.cfg.temperature)
        form.addRow("Temperature", self.temp)
        self.top_p = QDoubleSpinBox(); self.top_p.setRange(.01, 1); self.top_p.setSingleStep(.05); self.top_p.setValue(self.cfg.top_p)
        form.addRow("Top-p", self.top_p)
        self.tokens = QSpinBox(); self.tokens.setRange(32, 32768); self.tokens.setValue(self.cfg.max_tokens)
        form.addRow("Max tokens", self.tokens)
        self.seed = QSpinBox(); self.seed.setRange(-1, 2147483647); self.seed.setValue(self.cfg.seed)
        form.addRow("Seed (-1 disables)", self.seed)
        self.timeout = QSpinBox(); self.timeout.setRange(5, 600); self.timeout.setValue(self.cfg.timeout_seconds)
        form.addRow("Timeout (seconds)", self.timeout)
        self.retries = QSpinBox(); self.retries.setRange(0, 5); self.retries.setValue(self.cfg.retry_attempts)
        self.retries.setToolTip("Only transient network failures are retried; invalid keys are never retried.")
        form.addRow("Transient retries", self.retries)
        self.test_button = QPushButton("Test connection"); self.test_button.clicked.connect(self._test)
        form.addRow("", self.test_button)
        self.test_label = QLabel(""); self.test_label.setWordWrap(True)
        form.addRow("", self.test_label)
        self.connection_progress = QProgressBar()
        self.connection_progress.setRange(0, 0)
        self.connection_progress.setAccessibleName('Model connection test in progress')
        self.connection_progress.hide()
        form.addRow('', self.connection_progress)
        notice = QLabel('Local LLM servers and models are configured by the user; cloud providers require an API key. '
                        'Dictionary lookup needs neither.')
        notice.setWordWrap(True)
        form.addRow('', notice)
        # Keep provider-specific drafts in memory. Switching between local and
        # API must not overwrite a carefully configured model, URL or pending key.
        self._active_provider = self.provider.currentText()
        self._backend_preferred = {self.cfg.translation_backend: self._active_provider}
        # Long-lived drafts persist for both local and cloud provider choices.
        self._provider_drafts = {}
        # Only load a provider credential on first viewing that provider.
        # Subsequent switching restores unsaved edits, not an old keyring copy.
        self._provider_key_initialized: set[str] = set()
        self._key_baselines: dict[str, str] = {}
        self._pending_key_removals: set[str] = set()
        for provider, saved in self.cfg.provider_profiles.items():
            if provider in PROVIDERS and isinstance(saved, dict):
                self._provider_drafts[provider] = (
                    str(saved.get('model', PROVIDERS[provider])),
                    str(saved.get('base_url', LOCAL_URLS.get(provider, ''))),
                    str(saved.get('api_key_env', '')), '')
        self._provider_drafts[self._active_provider] = (
            self.model.text(), self.url.text(), self.key_env.text(), self.key.text())
        self._backend_changed(self.backend.currentIndex())
        self.key_env.textChanged.connect(lambda _value: self._update_key_status())

    def _remember_provider(self) -> None:
        if self._active_provider:
            key = self.key.text()
            if key:
                self._pending_key_removals.discard(self._active_provider)
            self._provider_drafts[self._active_provider] = (
                self.model.text(), self.url.text(), self.key_env.text(), key)

    def _restore_provider(self, provider: str) -> None:
        model, url, env, key = self._provider_drafts.get(
            provider, (PROVIDERS[provider], LOCAL_URLS.get(provider, ''), '', ''))
        if provider not in self._provider_key_initialized:
            saved = self.cfg.get_stored_key(provider)
            self._key_baselines[provider] = saved
            key = saved
            self._provider_key_initialized.add(provider)
            self._provider_drafts[provider] = (model, url, env, key)
        if provider in self._pending_key_removals:
            key = ''
        # Switch the active identity *before* changing the key field. Qt emits
        # textChanged synchronously; using the previous provider here could
        # accidentally undo that provider's pending Forget operation.
        self._active_provider = provider
        self.model.setText(model)
        self.url.setText(url)
        self.key_env.setText(env)
        self.key.blockSignals(True)
        try:
            self.key.setText(key)
        finally:
            self.key.blockSignals(False)
        self.key_toggle.setChecked(False)
        self._update_key_status()

    def _toggle_key_visibility(self, visible: bool) -> None:
        self.key.setEchoMode(QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password)
        self.key_toggle.setText('Hide' if visible else 'Show')

    def _key_changed(self, value: str) -> None:
        if not hasattr(self, '_active_provider'):
            return
        if value:
            self._pending_key_removals.discard(self._active_provider)
        self._update_key_status()

    def _update_key_status(self) -> None:
        provider = self._active_provider
        if provider in self._pending_key_removals:
            message = f'{provider} credential will be removed when you click Save.'
        elif self.key.text():
            if self.key.text() == self._key_baselines.get(provider, ''):
                message = (f'Saved {provider} API key found in Windows Credential Manager. '
                           'The field is masked; click Show only when necessary.')
            else:
                message = (f'{provider} API key changed in this dialog but not saved yet. '
                           'Click Save to store it securely.')
        elif self.key_env.text().strip():
            message = ('No key saved in the app. The configured environment variable '
                       'may supply credentials during translation.')
        else:
            message = f'No saved {provider} API key. Enter a key and click Save.'
        if self.key.text() and self.key_env.text().strip() and provider not in self._pending_key_removals:
            message += (' The named environment variable takes precedence over this saved key during '
                        'translation; clear that field to use the saved key.')
        self.key_status.setText(message)
        self.key_remove.setEnabled(bool(self.key.text()) or bool(self._key_baselines.get(provider)))

    def _forget_key(self) -> None:
        provider = self._active_provider
        choice = QMessageBox.question(
            self, 'Forget saved API key?',
            f'Remove the saved {provider} key from Windows Credential Manager on Save? '
            'This does not delete your provider model settings.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if choice == QMessageBox.StandardButton.Yes:
            self._pending_key_removals.add(provider)
            self.key.clear()
            self._remember_provider()
            self._update_key_status()

    def _backend_changed(self, _index: int) -> None:
        """Switch inference source while preserving each provider's edited form."""
        local_providers = {'Ollama', 'LM Studio', 'llama.cpp server', 'vLLM', 'GPT4All', 'Transformers'}
        self._remember_provider()
        old_backend = ('local' if self._active_provider in local_providers else 'api')
        if self._active_provider:
            self._backend_preferred[old_backend] = self._active_provider
        backend = self.backend.currentData()
        # Local runtime discovery is not relevant to a cloud account.
        self.detect_button.setVisible(backend == 'local')
        choices = [name for name in PROVIDERS if (name in local_providers) == (backend == 'local')]
        selected = self._backend_preferred.get(backend)
        if selected not in choices:
            selected = 'Ollama' if backend == 'local' else 'OpenAI'
        self.provider.blockSignals(True)
        self.provider.clear()
        self.provider.addItems(choices)
        self.provider.setCurrentText(selected)
        self.provider.blockSignals(False)
        self._restore_provider(selected)

    def _provider_changed(self, provider: str) -> None:
        if not provider or not hasattr(self, '_provider_drafts'):
            return
        self._remember_provider()
        self._restore_provider(provider)
        self._backend_preferred[self.backend.currentData()] = provider

    def _detect_local(self) -> None:
        if self.discovery_thread is not None and self.discovery_thread.isRunning():
            return
        self.detect_button.setEnabled(False)
        self.detect_button.setText('Searching running services…')
        self.discovery_thread = LocalDiscoveryThread(self.url.text().strip())
        self.discovery_thread.discovered.connect(self._local_discovered)
        self.discovery_thread.finished.connect(self._discovery_finished)
        self.discovery_thread.start()

    def _discovery_finished(self) -> None:
        self.detect_button.setEnabled(True)
        self.detect_button.setText('Find running local servers and models')

    def _local_discovered(self, servers: list) -> None:
        if not servers:
            QMessageBox.information(
                self, 'No running local inference server',
                'No model server responded on common localhost ports. '
                'For Ollama, start Ollama and run "ollama list". '
                'For LM Studio, load a model and start its Local Server. '
                'If using another address, configure the Base URL manually.')
            return
        options = [(f'{srv.provider} · {model} · {srv.url}', srv, model)
                   for srv in servers for model in srv.models]
        choice, ok = QInputDialog.getItem(self, 'Select a running local model',
                                         'Use which detected server/model?',
                                         [item[0] for item in options], 0, False)
        if not ok:
            return
        _, server, model = next(item for item in options if item[0] == choice)
        self.backend.setCurrentIndex(self.backend.findData('local'))
        self.provider.setCurrentText(server.provider)
        self.model.setText(model)
        self.url.setText(server.url)
        self._remember_provider()
        self.test_label.setText(
            f'Found {server.provider}: {model}. Click Test connection, then Save. '
            'No settings were changed on disk yet.')

    def _rag_tab(self) -> None:
        form = self._tab("RAG / Search")
        self.k = QSpinBox(); self.k.setRange(1, 30); self.k.setValue(self.cfg.retrieval_k)
        form.addRow("Evidence results", self.k)
        self.embed = QLineEdit(self.cfg.embedding_model)
        form.addRow("Local embedding model", self.embed)
        self.store = QComboBox(); self.store.addItems(["chroma"]); self.store.setCurrentText(self.cfg.vector_store)
        form.addRow("Vector database", self.store)
        self.vector = QCheckBox("Enable dense retrieval (requires prebuilt index)"); self.vector.setChecked(self.cfg.vector_enabled)
        form.addRow("", self.vector)
        self.bm25 = QDoubleSpinBox(); self.bm25.setRange(0, 1); self.bm25.setSingleStep(.05); self.bm25.setValue(self.cfg.bm25_weight)
        form.addRow("BM25 weight", self.bm25)
        self.fuzzy = QDoubleSpinBox(); self.fuzzy.setRange(0, 1); self.fuzzy.setSingleStep(.05); self.fuzzy.setValue(self.cfg.fuzzy_weight)
        form.addRow("Fuzzy weight", self.fuzzy)
        self.dense_weight = QDoubleSpinBox(); self.dense_weight.setRange(0, 1); self.dense_weight.setSingleStep(.05); self.dense_weight.setValue(self.cfg.vector_weight)
        form.addRow("Dense weight", self.dense_weight)
        self.reranker = QLineEdit(self.cfg.reranker_model); self.reranker.setPlaceholderText("Optional cross-encoder model ID")
        form.addRow("Reranker model", self.reranker)
        self.multi = QCheckBox("Enable multi-query expansion (experimental)"); self.multi.setChecked(self.cfg.multi_query)
        form.addRow("", self.multi)
        self.compress = QCheckBox("Compress evidence snippets in prompt"); self.compress.setChecked(self.cfg.compression)
        form.addRow("", self.compress)
        form.addRow("", QLabel("Dense index creation: python scripts/build_index.py"))

    def _ocr_tab(self) -> None:
        form = self._tab("Documents & OCR")
        self.ocr_engine = QComboBox(); self.ocr_engine.addItems(list(ALL_OCR_ENGINES.values()))
        self.ocr_engine.setCurrentText(engine_key_to_label(self.cfg.ocr_engine))
        form.addRow("Default OCR engine", self.ocr_engine)
        self.ocr_mode = QComboBox(); self.ocr_mode.addItems(["auto", "always", "never"]); self.ocr_mode.setCurrentText(self.cfg.ocr_mode)
        form.addRow("Default OCR mode", self.ocr_mode)
        self.ocr_language = QLineEdit(self.cfg.ocr_language); self.ocr_language.setPlaceholderText("eng")
        form.addRow("OCR language", self.ocr_language)
        self.ocrspace_api_key = QLineEdit(self.cfg.ocrspace_api_key); self.ocrspace_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("OCR.space API key", self.ocrspace_api_key)
        self.google_vision_api_key = QLineEdit(self.cfg.google_vision_api_key); self.google_vision_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Google Vision API key", self.google_vision_api_key)
        self.azure_document_endpoint = QLineEdit(self.cfg.azure_document_endpoint)
        form.addRow("Azure endpoint", self.azure_document_endpoint)
        self.azure_document_key = QLineEdit(self.cfg.azure_document_key); self.azure_document_key.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Azure key", self.azure_document_key)
        self.aws_region = QLineEdit(self.cfg.aws_region)
        form.addRow("AWS region", self.aws_region)
        self.mathpix_app_id = QLineEdit(self.cfg.mathpix_app_id)
        form.addRow("Mathpix app ID", self.mathpix_app_id)
        self.mathpix_app_key = QLineEdit(self.cfg.mathpix_app_key); self.mathpix_app_key.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Mathpix app key", self.mathpix_app_key)
        self.mistral_api_key = QLineEdit(self.cfg.mistral_api_key); self.mistral_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Mistral API key", self.mistral_api_key)
        self.mistral_model = QLineEdit(self.cfg.mistral_model)
        form.addRow("Mistral OCR model", self.mistral_model)
        notice = QLabel(
            "Offline recommendation: RapidOCR for the bundled experience. "
            "For the strongest local OCR quality, install the optional PaddleOCR stack and select it here. "
            "Cloud OCR providers send page images to an external service."
        )
        notice.setWordWrap(True)
        form.addRow("", notice)
        choices = QLabel("Cloud providers available in this build: " + ", ".join(ONLINE_OCR_ENGINES.values()))
        choices.setWordWrap(True)
        form.addRow("", choices)

    def _prompt_tab(self) -> None:
        form = self._tab("Prompt")
        self.prompt = QPlainTextEdit(self.cfg.prompt); self.prompt.setMinimumHeight(420)
        form.addRow("Translation prompt", self.prompt)
        form.addRow("", QLabel("Required placeholders: {text}, {context}, and {examples}."))

    def _personalization_tab(self) -> None:
        form = self._tab("Interface & Feedback")
        self.theme = QComboBox(); self.theme.addItems(["dark", "light", "system"]); self.theme.setCurrentText(self.cfg.theme)
        form.addRow("Theme", self.theme)
        self.density = QComboBox(); self.density.addItems(["comfortable", "compact"]); self.density.setCurrentText(self.cfg.ui_density)
        form.addRow("Interface density", self.density)
        self.startup_tab = QComboBox(); self.startup_tab.addItems(["translator", "documents"]); self.startup_tab.setCurrentText(self.cfg.startup_tab)
        form.addRow("Startup tab", self.startup_tab)
        self.feedback = QCheckBox("Save accepted and corrected translations"); self.feedback.setChecked(self.cfg.store_feedback)
        form.addRow("", self.feedback)
        self.examples = QSpinBox(); self.examples.setRange(0, 12); self.examples.setValue(self.cfg.feedback_examples)
        form.addRow("Few-shot feedback examples", self.examples)
        form.addRow("", QLabel("Feedback updates the local translation memory; model weights are not fine-tuned inside the app."))

    def _collect(self) -> None:
        c = self.cfg
        self._remember_provider()
        c.provider_profiles = {
            provider: {'model': draft[0], 'base_url': draft[1], 'api_key_env': draft[2]}
            for provider, draft in self._provider_drafts.items() if provider in PROVIDERS
        }
        c.transport = self.transport.currentData()
        c.translation_backend = self.backend.currentData()
        c.provider = self.provider.currentText()
        c.model = self.model.text().strip()
        c.base_url = self.url.text().strip()
        c.api_key_env = self.key_env.text().strip()
        c.temperature = self.temp.value()
        c.top_p = self.top_p.value()
        c.max_tokens = self.tokens.value()
        c.seed = self.seed.value()
        c.timeout_seconds = self.timeout.value()
        c.retry_attempts = self.retries.value()
        c.retrieval_k = self.k.value()
        c.embedding_model = self.embed.text().strip()
        c.vector_store = self.store.currentText()
        c.vector_enabled = self.vector.isChecked()
        c.bm25_weight = self.bm25.value()
        c.fuzzy_weight = self.fuzzy.value()
        c.vector_weight = self.dense_weight.value()
        c.reranker_model = self.reranker.text().strip()
        c.multi_query = self.multi.isChecked()
        c.compression = self.compress.isChecked()
        c.ocr_engine = engine_label_to_key(self.ocr_engine.currentText())
        c.ocr_mode = self.ocr_mode.currentText()
        c.ocr_language = self.ocr_language.text().strip() or "eng"
        c.ocrspace_api_key = self.ocrspace_api_key.text().strip()
        c.google_vision_api_key = self.google_vision_api_key.text().strip()
        c.azure_document_endpoint = self.azure_document_endpoint.text().strip()
        c.azure_document_key = self.azure_document_key.text().strip()
        c.aws_region = self.aws_region.text().strip() or "us-east-1"
        c.mathpix_app_id = self.mathpix_app_id.text().strip()
        c.mathpix_app_key = self.mathpix_app_key.text().strip()
        c.mistral_api_key = self.mistral_api_key.text().strip()
        c.mistral_model = self.mistral_model.text().strip() or "mistral-ocr-latest"
        c.prompt = self.prompt.toPlainText()
        c.theme = self.theme.currentText()
        c.ui_density = self.density.currentText()
        c.startup_tab = self.startup_tab.currentText()
        c.store_feedback = self.feedback.isChecked()
        c.feedback_examples = self.examples.value()
        c.validate()

    def _test(self) -> None:
        try:
            self._collect()
        except Exception as exc:
            QMessageBox.warning(self, "Invalid settings", str(exc))
            return
        # Use an ephemeral key for this test: Cancel must not store any secrets.
        self.cfg.session_api_key = self.key.text().strip()
        self.test_button.setEnabled(False)
        self._buttons.setEnabled(False)
        self.tabs.setEnabled(False)
        self.connection_progress.show()
        self.test_label.setText('Connecting to the configured model… You can review the result when it finishes.')
        self.thread = ConnectionThread(self.cfg)
        self.thread.done.connect(self._test_done)
        self.thread.finished.connect(self._test_finished)
        self.thread.start()

    def _test_done(self, message: str, ok: bool) -> None:
        self.test_label.setText(('✓ ' if ok else '✕ ') + message)

    def _test_finished(self) -> None:
        self.connection_progress.hide()
        self.test_button.setEnabled(True)
        self._buttons.setEnabled(True)
        self.tabs.setEnabled(True)

    def reject(self) -> None:
        if ((self.thread is not None and self.thread.isRunning()) or
            (self.discovery_thread is not None and self.discovery_thread.isRunning())):
            self.test_label.setText('Please wait for the connection test or local detection to finish before closing Settings.')
            return
        super().reject()

    def closeEvent(self, event) -> None:
        if ((self.thread is not None and self.thread.isRunning()) or
            (self.discovery_thread is not None and self.discovery_thread.isRunning())):
            event.ignore()
            self.test_label.setText('Please wait for the connection test to finish before closing Settings.')
            return
        super().closeEvent(event)

    def _save(self) -> None:
        try:
            self._collect()
            self._remember_provider()
            current_provider = self.cfg.provider
            # Store only changed secrets, including keys edited for providers
            # visited before switching tabs. Never write them to JSON.
            try:
                for provider, draft in self._provider_drafts.items():
                    key = draft[3].strip()
                    if provider in self._pending_key_removals:
                        self.cfg.provider = provider
                        self.cfg.set_key('')
                    elif key and key != self._key_baselines.get(provider, ''):
                        self.cfg.provider = provider
                        self.cfg.set_key(key)
            finally:
                self.cfg.provider = current_provider
            self.cfg.session_api_key = ''
            self.cfg.save()
            self.accept()
        except Exception as exc:
            QMessageBox.warning(self, "Could not save", str(exc))
