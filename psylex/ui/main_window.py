"""PySide6 desktop: translator, evidence, feedback, history, favorites, batch, imports."""
from __future__ import annotations
import csv
import json
import re
import time
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal, QTimer
import threading
from PySide6.QtGui import QAction, QFont, QKeySequence, QTextOption, QPixmap, QIcon
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QDialog, QInputDialog,
    QFileDialog, QFormLayout, QFrame, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QListWidget, QMainWindow, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QComboBox, QSplitter, QStatusBar, QTabWidget, QTableWidget,
    QStackedWidget, QSizePolicy, QScrollArea,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget)
from psylex.core.config import Settings, bundle_dir, data_dir
from psylex.core.database import Database
from psylex.core.dictionary import DictionaryService, DictionaryHit
from psylex.core.ingest import load_jsonl, parse_docx
from psylex.core.models import Feedback, Translation
from psylex.core.documents import (DocumentData, INPUT_FORMATS, OUTPUT_FORMATS, load_document,
                                   translate_document, save_document)
from psylex.core.ocr import ONLINE_OCR_ENGINES
from psylex.rag.graph import TranslationPipeline
from psylex.ui.settings_dialog import SettingsDialog
from psylex.ui.widgets import DropTextEdit, ModeSelector
from psylex.ui.styles import stylesheet, DARK
from psylex.core.ocr import available_engine_labels, engine_label_to_key, engine_key_to_label


class BackgroundJob(QThread):
    """Worker with cooperative result suppression on cancellation.

    Provider SDK calls may block until their configured timeout; cancelling
    never force-terminates the thread or its network stack.
    """
    result = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, fn, *args):
        super().__init__()
        self.fn, self.args = fn, args
        self.stop_event = threading.Event()

    def run(self) -> None:
        try:
            value = self.fn(*self.args)
            if self.stop_event.is_set():
                self.cancelled.emit()
            else:
                self.result.emit(value)
        except Exception as exc:
            if self.stop_event.is_set():
                self.cancelled.emit()
            else:
                self.failed.emit(f'{type(exc).__name__}: {exc}')


class BatchJob(QThread):
    """Process one row at a time, publishing truthful progress and partial results."""
    result = Signal(object)
    cancelled = Signal(object)
    failed = Signal(str)
    progress_update = Signal(int, int)

    def __init__(self, rows: list[str], pipeline: TranslationPipeline):
        super().__init__()
        self.rows, self.pipeline = list(rows), pipeline
        self.stop_event = threading.Event()

    def run(self) -> None:
        output: list[tuple[str, str, str]] = []
        try:
            for text in self.rows:
                if self.stop_event.is_set():
                    self.cancelled.emit(output)
                    return
                try:
                    translation = self.pipeline.translate(text, save=True)
                    output.append((text, translation.target,
                                   'OK' if translation.target else 'No exact dictionary entry'))
                except Exception as exc:
                    output.append((text, '', f'Error: {str(exc)[:140]}'))
                self.progress_update.emit(len(output), len(self.rows))
            self.result.emit(output)
        except Exception as exc:
            self.failed.emit(f'{type(exc).__name__}: {exc}')


class DocumentLoadJob(QThread):
    """Document parsing and OCR are worker-thread operations, with cancellation."""
    result = Signal(object)
    failed = Signal(str)
    cancelled = Signal()
    progress_update = Signal(int, int, str)

    def __init__(self, path: Path, engine: str, mode: str, settings: Settings):
        super().__init__()
        self.path, self.engine, self.mode = path, engine, mode
        self.settings = settings
        self.stop_event = threading.Event()

    def run(self) -> None:
        try:
            document = load_document(self.path, ocr_engine=self.engine, ocr_mode=self.mode,
                on_progress=lambda index,total,message: self.progress_update.emit(index,total,message),
                is_cancelled=self.stop_event.is_set, settings=self.settings)
            self.result.emit(document)
        except InterruptedError:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(f'{type(exc).__name__}: {exc}')


class DocumentJob(QThread):
    """Progress-aware document translator with cooperative cancellation."""
    result = Signal(object)
    failed = Signal(str)
    cancelled = Signal()
    progress_update = Signal(int, int, str)

    def __init__(self, document: DocumentData, pipeline: TranslationPipeline):
        super().__init__()
        self.document, self.pipeline = document, pipeline
        self.stop_event = threading.Event()

    def run(self) -> None:
        try:
            result = translate_document(
                self.document, self.pipeline,
                on_progress=lambda current,total,msg: self.progress_update.emit(current,total,msg),
                is_cancelled=self.stop_event.is_set,
            )
            self.result.emit(result)
        except InterruptedError:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(f'{type(exc).__name__}: {exc}')


class MainWindow(QMainWindow):
    def __init__(self, db: Database, cfg: Settings):
        super().__init__()
        self.db = db
        self.cfg = cfg
        self.pipeline = TranslationPipeline(db, cfg)
        self.dictionary_service = DictionaryService(db)
        self.active_job = None
        self.jobs = []
        self._busy_kind = ''
        self._busy_started = 0.0
        self.current: Translation | None = None
        self.batch_rows: list[str] = []
        self.batch_results: list[tuple[str, str, str]] = []
        self.document_data: DocumentData | None = None
        self.document_job: DocumentJob | None = None
        self.doc_load_job: DocumentLoadJob | None = None
        self._review_row = -1
        self._dictionary_hits: list[DictionaryHit] = []
        self.setWindowTitle('PsyLex Studio • Psychology Translation Workspace')
        self.resize(1260, 820)
        self.setMinimumSize(920, 620)
        self.setAcceptDrops(True)
        icon_path = bundle_dir() / 'assets' / 'branding' / 'logo_icon.png'
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))
        self._build()
        self._menu()
        self.setStyleSheet(stylesheet(cfg.theme))
        self.mode_selector.setProperty('uiDark', stylesheet(self.cfg.theme) == DARK)
        self._refresh_history()
        # Always check bundled lexicon version: older installations may still
        # have the unsafe cross-column pairs stored in their existing SQLite DB.
        self._load_seed()

    def _status(self, message: str) -> None:
        self.statusBar().showMessage(message, 10000)

    def _build(self) -> None:
        root = QWidget()
        root.setObjectName('appRoot')
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 12, 16, 10)
        layout.setSpacing(10)

        # Compact identity header: the brand is readable, without occupying
        # a quarter of the screen or forcing text to compete with the logo.
        hero = QFrame()
        hero.setObjectName('heroCard')
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(16, 12, 16, 12)
        hero_layout.setSpacing(13)

        logo_label = QLabel()
        logo_label.setObjectName('brandIcon')
        icon_path = bundle_dir() / 'assets' / 'branding' / 'logo_icon_64.png'
        if icon_path.exists():
            logo_label.setPixmap(QPixmap(str(icon_path)).scaled(
                45, 45, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        logo_label.setFixedSize(48, 48)
        hero_layout.addWidget(logo_label, 0, Qt.AlignmentFlag.AlignVCenter)

        identity = QVBoxLayout()
        identity.setSpacing(2)
        title = QLabel('PsyLex Studio')
        title.setObjectName('heroTitle')
        identity.addWidget(title)
        subtitle = QLabel('Psychology terminology  /  English → Persian')
        subtitle.setObjectName('muted')
        identity.addWidget(subtitle)
        hero_layout.addLayout(identity, 1)

        # Dictionary and Translation are workflows. Provider is configured in Settings.
        self.mode_selector = ModeSelector()
        self.mode_selector.addItem('Dictionary', 'dictionary')
        self.mode_selector.addItem('Translation', 'translation')
        self.mode_selector.setCurrentIndex(max(0, self.mode_selector.findData(self.cfg.mode)))
        self.mode_selector.currentIndexChanged.connect(self._mode_changed)
        hero_layout.addWidget(self.mode_selector, 0, Qt.AlignmentFlag.AlignVCenter)
        settings_btn = QPushButton('Settings')
        settings_btn.setAccessibleName('Open settings')
        settings_btn.setToolTip('Model, OCR, appearance, and feedback preferences (Ctrl+,)')
        settings_btn.clicked.connect(self._settings)
        hero_layout.addWidget(settings_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(hero)

        self.tabs = QTabWidget()
        self.tabs.setObjectName('workspaceTabs')
        self.tabs.setDocumentMode(True)
        self.tabs.setUsesScrollButtons(True)
        layout.addWidget(self.tabs, stretch=1)
        self._translator_tab()
        self._dictionary_tab()
        self._history_tab()
        self._favorites_tab()
        self._batch_tab()
        self._documents_tab()
        self._library_tab()
        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar(self))
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setMaximumWidth(120)
        self.progress.hide()
        self.statusBar().addPermanentWidget(self.progress)
        self._activity_timer = QTimer(self)
        self._activity_timer.setInterval(1000)
        self._activity_timer.timeout.connect(self._update_activity_elapsed)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        if self.cfg.startup_tab == 'documents':
            self.tabs.setCurrentWidget(self.document_tab)
        else:
            self.tabs.setCurrentWidget(
                self.dictionary_tab if self.cfg.mode == 'dictionary' else self.translation_tab
            )

    def _translator_tab(self) -> None:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)
        panes = QSplitter(Qt.Orientation.Horizontal)
        panes.setChildrenCollapsible(False)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.addWidget(QLabel('English input'))
        self.input = DropTextEdit()
        self.input.setPlaceholderText('Enter a psychology term, sentence, or paragraph…\n\nExamples:\n• cognitive behavioral therapy\n• working memory\n• The participants exhibited reduced attentional bias.\n\nDrop a document here to open the Documents workflow.')
        self.input.file_dropped.connect(self._open_document)
        self.input.setMinimumHeight(140)
        ll.addWidget(self.input, 1)
        actions = QHBoxLayout()
        self.translate_button = QPushButton('Translate  Ctrl+Enter')
        self.translate_button.setObjectName('primary')
        self.translate_button.clicked.connect(self._translate)
        actions.addWidget(self.translate_button)
        clip = QPushButton('Paste')
        clip.clicked.connect(lambda: self.input.setPlainText(QApplication.clipboard().text()))
        actions.addWidget(clip)
        clear = QPushButton('Clear')
        clear.clicked.connect(lambda: self.input.clear())
        actions.addWidget(clear)
        ll.addLayout(actions)
        # Inline activity is impossible to miss, unlike a narrow status-bar spinner.
        self.translation_activity = QFrame()
        self.translation_activity.setObjectName('activityPanel')
        activity_row = QHBoxLayout(self.translation_activity)
        activity_row.setContentsMargins(11, 9, 11, 9)
        activity_row.setSpacing(10)
        self.translation_spinner = QProgressBar()
        self.translation_spinner.setRange(0, 0)
        self.translation_spinner.setFixedWidth(90)
        self.translation_spinner.setAccessibleName('Translation in progress')
        activity_row.addWidget(self.translation_spinner)
        activity_texts = QVBoxLayout()
        self.translation_activity_title = QLabel('Translating…')
        self.translation_activity_title.setObjectName('activityTitle')
        activity_texts.addWidget(self.translation_activity_title)
        self.translation_activity_detail = QLabel('Contacting the configured translation model…')
        self.translation_activity_detail.setObjectName('muted')
        self.translation_activity_detail.setWordWrap(True)
        activity_texts.addWidget(self.translation_activity_detail)
        activity_row.addLayout(activity_texts, 1)
        self.cancel_translation_btn = QPushButton('Cancel')
        self.cancel_translation_btn.setAccessibleName('Cancel current translation')
        self.cancel_translation_btn.clicked.connect(self._cancel_translation)
        activity_row.addWidget(self.cancel_translation_btn)
        ll.addWidget(self.translation_activity)
        self.translation_activity.hide()
        self.translation_notice = QLabel('Ready · Choose Translation mode, then enter a term or passage.')
        self.translation_notice.setObjectName('muted')
        self.translation_notice.setAccessibleName('Translation status and errors')
        self.translation_notice.setWordWrap(True)
        ll.addWidget(self.translation_notice)
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.addWidget(QLabel('Persian translation'))
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.output.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        font = QFont('Segoe UI', 12)
        self.output.setFont(font)
        self.output.setPlaceholderText('نتیجهٔ ترجمه در اینجا نمایش داده می‌شود')
        self.output.setMinimumHeight(145)
        rl.addWidget(self.output, 1)
        meta = QHBoxLayout()
        self.confidence_label = QLabel('Confidence: —')
        self.confidence_label.setObjectName('muted')
        meta.addWidget(self.confidence_label)
        meta.addStretch()
        copy = QPushButton('Copy result')
        copy.clicked.connect(self._copy_translation)
        meta.addWidget(copy)
        self.favorite_btn = QPushButton('☆ Save')
        self.favorite_btn.clicked.connect(self._favorite_current)
        meta.addWidget(self.favorite_btn)
        rl.addLayout(meta)
        feedback = QFrame()
        feedback.setObjectName('feedbackBar')
        fl = QHBoxLayout(feedback)
        fl.setContentsMargins(10, 5, 10, 5)
        fl.setSpacing(8)
        fl.addWidget(QLabel('Was this translation correct?'))
        fl.addStretch()
        self.yes_btn = QPushButton('Approve')
        self.yes_btn.clicked.connect(lambda: self._feedback(True))
        fl.addWidget(self.yes_btn)
        self.no_btn = QPushButton('Suggest correction')
        self.no_btn.clicked.connect(lambda: self._feedback(False))
        fl.addWidget(self.no_btn)
        rl.addWidget(feedback)
        panes.addWidget(left)
        panes.addWidget(right)
        panes.setSizes([530, 530])
        outer.addWidget(panes, stretch=4)
        lower = QSplitter(Qt.Orientation.Horizontal)
        lower.setChildrenCollapsible(False)
        evidence_box = QGroupBox('Dictionary evidence / related terms')
        evl = QVBoxLayout(evidence_box)
        self.evidence = QTableWidget(0, 4)
        self.evidence.setHorizontalHeaderLabels(['English term', 'Persian', 'Source position', 'Match'])
        self.evidence.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.evidence.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.evidence.itemDoubleClicked.connect(self._use_evidence)
        evl.addWidget(self.evidence)
        lower.addWidget(evidence_box)
        warnings = QGroupBox('Translation QA / Notices')
        wl = QVBoxLayout(warnings)
        self.warnings = QPlainTextEdit()
        self.warnings.setReadOnly(True)
        self.warnings.setPlaceholderText('Quality checks and model notices appear here.')
        wl.addWidget(self.warnings)
        lower.addWidget(warnings)
        lower.setSizes([700, 350])
        outer.addWidget(lower, stretch=2)
        self.translation_tab = page
        self.tabs.addTab(page, 'Translation')

    def _dictionary_tab(self) -> None:
        """Real offline dictionary browser: no LLM generation, no guessed meanings."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)
        heading = QLabel('Psychology dictionary')
        heading.setObjectName('sectionTitle')
        layout.addWidget(heading)
        desc = QLabel('Find English headwords and browse Persian equivalents from the imported dictionaries. '
                      'Searches run locally. Source locations and personal corrections are shown.')
        desc.setObjectName('muted')
        desc.setWordWrap(True)
        layout.addWidget(desc)
        lookup_row = QHBoxLayout()
        self.dict_query = QLineEdit()
        self.dict_query.setAccessibleName('Search psychology dictionary')
        self.dict_query.setPlaceholderText('Search: working memory, dissociation, reinforcement…')
        self.dict_query.returnPressed.connect(self._dict_search)
        lookup_row.addWidget(self.dict_query, 1)
        search_button = QPushButton('Search dictionary')
        search_button.setObjectName('primary')
        search_button.clicked.connect(self._dict_search)
        lookup_row.addWidget(search_button)
        clear_button = QPushButton('Clear')
        clear_button.clicked.connect(self._dict_clear)
        lookup_row.addWidget(clear_button)
        layout.addLayout(lookup_row)
        self.dict_count = QLabel('Enter an English psychology term to search the local dictionary.')
        self.dict_count.setObjectName('muted')
        layout.addWidget(self.dict_count)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        self.dict_results = QTableWidget(0, 4)
        self.dict_results.setHorizontalHeaderLabels(['English term', 'Persian equivalent', 'Source', 'Type'])
        self.dict_results.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.dict_results.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.dict_results.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.dict_results.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.dict_results.setMinimumHeight(190)
        self.dict_results.itemSelectionChanged.connect(self._dict_select)
        self.dict_results.itemDoubleClicked.connect(lambda item: self._dict_copy())
        splitter.addWidget(self.dict_results)
        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(2, 8, 2, 0)
        bottom_layout.addWidget(QLabel('Selected entry • source evidence'))
        self.dict_detail = QPlainTextEdit()
        self.dict_detail.setReadOnly(True)
        self.dict_detail.setPlaceholderText('Select an entry to inspect its Persian translation and source location.')
        self.dict_detail.setMinimumHeight(95)
        bottom_layout.addWidget(self.dict_detail)
        row = QHBoxLayout()
        self.dict_copy_btn = QPushButton('Copy Persian')
        self.dict_copy_btn.clicked.connect(self._dict_copy)
        self.dict_copy_btn.setEnabled(False)
        row.addWidget(self.dict_copy_btn)
        self.dict_correct_btn = QPushButton('Correct / approve')
        self.dict_correct_btn.clicked.connect(self._dict_correct)
        self.dict_correct_btn.setEnabled(False)
        row.addWidget(self.dict_correct_btn)
        use_btn = QPushButton('Open in Translation')
        use_btn.clicked.connect(self._dict_to_translation)
        row.addWidget(use_btn)
        row.addStretch()
        bottom_layout.addLayout(row)
        splitter.addWidget(bottom)
        splitter.setSizes([430, 175])
        layout.addWidget(splitter, 1)
        self._dict_timer = QTimer(self)
        self._dict_timer.setSingleShot(True)
        self._dict_timer.setInterval(240)
        self._dict_timer.timeout.connect(self._dict_search)
        self.dict_query.textChanged.connect(lambda _text: self._dict_timer.start())
        self.dictionary_tab = tab
        self.tabs.addTab(tab, 'Dictionary')

    def _dict_clear(self) -> None:
        self._dict_timer.stop()
        self.dict_query.blockSignals(True)
        self.dict_query.clear()
        self.dict_query.blockSignals(False)
        self._dictionary_hits.clear()
        self.dict_results.setRowCount(0)
        self.dict_detail.clear()
        self.dict_count.setText('Enter a term to search the local dictionary.')
        self.dict_copy_btn.setEnabled(False)
        self.dict_correct_btn.setEnabled(False)

    def _dict_search(self) -> None:
        self._dict_timer.stop()
        query = self.dict_query.text().strip()
        if not query:
            self._dict_clear()
            return
        try:
            self._dictionary_hits = self.dictionary_service.search(query, limit=80)
        except Exception as exc:
            self._status(f'Dictionary lookup failed: {exc}')
            return
        self.dict_results.blockSignals(True)
        self.dict_results.setRowCount(len(self._dictionary_hits))
        for i, hit in enumerate(self._dictionary_hits):
            values = [hit.english, hit.persian, hit.source, hit.match_label]
            for j, value in enumerate(values):
                self.dict_results.setItem(i, j, QTableWidgetItem(value))
        self.dict_results.blockSignals(False)
        exact = sum(hit.kind != 'related' for hit in self._dictionary_hits)
        self.dict_count.setText(f'{len(self._dictionary_hits)} results · {exact} exact/approved · '
                                f'{len(self._dictionary_hits) - exact} related suggestions')
        if self._dictionary_hits:
            self.dict_results.selectRow(0)
            self._dict_select()
        else:
            self.dict_detail.setPlainText('No term found. Try a shorter term or import another dictionary.')
            self.dict_copy_btn.setEnabled(False)
            self.dict_correct_btn.setEnabled(False)

    def _dict_selected_hit(self) -> DictionaryHit | None:
        row = self.dict_results.currentRow()
        return self._dictionary_hits[row] if 0 <= row < len(self._dictionary_hits) else None

    def _dict_select(self) -> None:
        hit = self._dict_selected_hit()
        self.dict_copy_btn.setEnabled(hit is not None)
        self.dict_correct_btn.setEnabled(hit is not None)
        if not hit:
            self.dict_detail.clear()
            return
        confidence = ('Source-extraction quality: ' + f'{hit.quality:.2f}'
                      if hit.quality is not None else 'Approved by a user; no calibrated confidence')
        self.dict_detail.setPlainText(f'English: {hit.english}\nPersian: {hit.persian}\n'
                                      f'Status: {hit.match_label}\nSource: {hit.source}\n'
                                      f'Location: {hit.location}\n{confidence}\n\n'
                                      'This dictionary does not invent definitions; review ambiguous terms in context.')

    def _dict_copy(self) -> None:
        hit = self._dict_selected_hit()
        if not hit:
            self._status('Select a dictionary entry before copying.')
            return
        QApplication.clipboard().setText(hit.persian)
        self._status(f'Copied Persian equivalent for {hit.english}.')

    def _dict_correct(self) -> None:
        hit = self._dict_selected_hit()
        if not hit:
            self._status('Select a dictionary entry to correct.')
            return
        if not self.cfg.store_feedback:
            self._status('Enable feedback storage in Settings to save corrections.')
            return
        corrected, ok = QInputDialog.getMultiLineText(
            self, 'Approve or correct entry', f'Preferred Persian for {hit.english}:', hit.persian
        )
        if not ok:
            return
        corrected = corrected.strip()
        if not corrected:
            QMessageBox.warning(self, 'Invalid correction', 'The Persian translation cannot be empty.')
            return
        self.db.record_feedback(Feedback(hit.english, hit.persian,
                                         corrected == hit.persian,
                                         '' if corrected == hit.persian else corrected))
        self.dict_query.setText(hit.english)
        self._dict_search()
        self._status('Saved to local translation memory; approved equivalent now appears first.')

    def _dict_to_translation(self) -> None:
        hit = self._dict_selected_hit()
        if hit:
            self.input.setPlainText(hit.english)
            self._set_workspace_mode('translation', show_page=True)
            self.input.setFocus()
        else:
            self._status('Select a dictionary entry first.')

    def _history_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        controls = QHBoxLayout()
        controls.addWidget(QLabel('Recent translations'))
        controls.addStretch()
        refresh = QPushButton('Refresh')
        refresh.clicked.connect(self._refresh_history)
        controls.addWidget(refresh)
        layout.addLayout(controls)
        self.history_table = QTableWidget(0, 4)
        self.history_table.setHorizontalHeaderLabels(['ID', 'English', 'Persian', 'Mode'])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.cellDoubleClicked.connect(self._open_history)
        layout.addWidget(self.history_table)
        self.tabs.addTab(tab, 'History')

    def _favorites_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel('Saved and starred translations (double-click to open)'))
        self.favorites = QListWidget()
        self.favorites.itemDoubleClicked.connect(self._open_favorite)
        layout.addWidget(self.favorites)
        button = QPushButton('Refresh favorites')
        button.clicked.connect(self._refresh_history)
        layout.addWidget(button)
        self.tabs.addTab(tab, 'Favorites')

    def _batch_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        label = QLabel('Translate a .txt (one term per line) or .csv (column named english or first column).')
        label.setWordWrap(True)
        layout.addWidget(label)
        controls = QHBoxLayout()
        choose = QPushButton('Import CSV / TXT')
        choose.clicked.connect(self._batch_import)
        controls.addWidget(choose)
        process = QPushButton('Translate batch')
        process.setObjectName('primary')
        process.clicked.connect(self._batch_translate)
        controls.addWidget(process)
        self.batch_button = process
        self.batch_cancel_btn = QPushButton('Cancel batch')
        self.batch_cancel_btn.setEnabled(False)
        self.batch_cancel_btn.clicked.connect(self._batch_cancel)
        controls.addWidget(self.batch_cancel_btn)
        export = QPushButton('Export CSV')
        export.clicked.connect(self._batch_export)
        controls.addWidget(export)
        layout.addLayout(controls)
        self.batch_activity = QLabel('Import a CSV or TXT list to begin.')
        self.batch_activity.setObjectName('muted')
        self.batch_activity.setAccessibleName('Batch translation progress')
        layout.addWidget(self.batch_activity)
        self.batch_progress = QProgressBar()
        self.batch_progress.setRange(0, 100)
        self.batch_progress.setValue(0)
        self.batch_progress.setAccessibleName('Batch rows completed')
        self.batch_progress.hide()
        layout.addWidget(self.batch_progress)
        self.batch_table = QTableWidget(0, 3)
        self.batch_table.setHorizontalHeaderLabels(['English', 'Persian', 'Status'])
        self.batch_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.batch_table)
        self.tabs.addTab(tab, 'Batch')

    def _documents_tab(self) -> None:
        """Compact, review-first document workspace with an intentional empty state."""
        tab = QWidget()
        panel = QVBoxLayout(tab)
        panel.setContentsMargins(12, 12, 12, 10)
        panel.setSpacing(9)

        # The toolbar remains visible while a file is being processed.
        toolbar = QFrame()
        toolbar.setObjectName('toolbarCard')
        controls = QHBoxLayout(toolbar)
        controls.setContentsMargins(12, 9, 12, 9)
        controls.setSpacing(10)
        open_btn = QPushButton('Open document…')
        open_btn.setObjectName('primary')
        open_btn.setAccessibleName('Open a Word, PDF, or other supported document')
        open_btn.clicked.connect(self._choose_document)
        controls.addWidget(open_btn)
        controls.addWidget(QLabel('OCR provider'))
        self.ocr_choice = QComboBox()
        self.ocr_choice.addItems(available_engine_labels())
        self.ocr_choice.setCurrentText(engine_key_to_label(self.cfg.ocr_engine))
        self.ocr_choice.setAccessibleName('OCR provider')
        self.ocr_choice.setMinimumWidth(210)
        self.ocr_choice.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        controls.addWidget(self.ocr_choice, 1)
        controls.addWidget(QLabel('Mode'))
        self.ocr_mode = QComboBox()
        self.ocr_mode.addItems(['Auto (recommended)', 'Always OCR', 'Never OCR'])
        self.ocr_mode.setCurrentIndex({'auto': 0, 'always': 1, 'never': 2}.get(self.cfg.ocr_mode, 0))
        self.ocr_mode.setAccessibleName('When to use OCR')
        self.ocr_mode.setMinimumWidth(165)
        controls.addWidget(self.ocr_mode)
        panel.addWidget(toolbar)

        self.doc_pages = QStackedWidget()
        self.doc_pages.setObjectName('documentPages')
        self.doc_pages.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # No visually collapsed editor before the user has loaded a file.
        empty = QFrame()
        empty.setObjectName('emptyState')
        empty_layout = QVBoxLayout(empty)
        empty_layout.setContentsMargins(26, 22, 26, 22)
        empty_layout.setSpacing(12)
        empty_layout.addStretch(1)
        empty_title = QLabel('Translate a document')
        empty_title.setObjectName('emptyTitle')
        empty_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        empty_layout.addWidget(empty_title)
        empty_copy = QLabel('Open a Word file, PDF, scanned document, or image.\n'
                            'Review the extracted text, translate with your chosen model, then export.')
        empty_copy.setObjectName('muted')
        empty_copy.setWordWrap(True)
        empty_copy.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_copy)
        empty_formats = QLabel('DOCX  ·  PDF  ·  PNG/JPG  ·  TXT  ·  MD  ·  CSV  ·  JSON  ·  HTML  ·  ODT  ·  EPUB')
        empty_formats.setObjectName('formatNote')
        empty_formats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_formats.setWordWrap(True)
        empty_layout.addWidget(empty_formats)
        example_btn = QPushButton('Choose a file  →')
        example_btn.setObjectName('primary')
        example_btn.clicked.connect(self._choose_document)
        empty_layout.addWidget(example_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        privacy = QLabel('Offline OCR stays on your device. Cloud OCR uploads pages only after confirmation.')
        privacy.setObjectName('muted')
        privacy.setAlignment(Qt.AlignmentFlag.AlignCenter)
        privacy.setWordWrap(True)
        empty_layout.addWidget(privacy)
        empty_layout.addStretch(1)
        self.doc_pages.addWidget(empty)

        workspace = QWidget()
        work_layout = QVBoxLayout(workspace)
        work_layout.setContentsMargins(0, 0, 0, 0)
        work_layout.setSpacing(6)
        self.doc_name = QLabel('No file loaded')
        self.doc_name.setObjectName('sectionTitle')
        self.doc_name.setWordWrap(True)
        work_layout.addWidget(self.doc_name)
        self.doc_warnings = QLabel('Review source text before translating.')
        self.doc_warnings.setObjectName('muted')
        self.doc_warnings.setWordWrap(True)
        self.doc_warnings.setMaximumHeight(42)
        work_layout.addWidget(self.doc_warnings)

        self.doc_splitter = QSplitter(Qt.Orientation.Vertical)
        self.doc_splitter.setObjectName('docSplitter')
        self.doc_splitter.setChildrenCollapsible(False)
        self.doc_splitter.setHandleWidth(8)
        self.doc_table = QTableWidget(0, 3)
        self.doc_table.setHorizontalHeaderLabels(['Page / location', 'English source', 'Persian translation'])
        header = self.doc_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.doc_table.setColumnWidth(0, 135)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.doc_table.verticalHeader().setVisible(False)
        self.doc_table.setWordWrap(False)
        self.doc_table.setAlternatingRowColors(True)
        self.doc_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.doc_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.doc_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.doc_table.itemSelectionChanged.connect(self._document_select)
        self.doc_table.setMinimumHeight(125)
        self.doc_splitter.addWidget(self.doc_table)

        editor = QFrame()
        editor.setObjectName('reviewPanel')
        editor_layout = QVBoxLayout(editor)
        editor_layout.setContentsMargins(10, 9, 10, 9)
        editor_layout.setSpacing(7)
        editor_head = QHBoxLayout()
        editor_head.addWidget(QLabel('Selected segment  ·  review & correct'))
        editor_head.addStretch()
        self.doc_apply_btn = QPushButton('Apply correction')
        self.doc_apply_btn.setEnabled(False)
        self.doc_apply_btn.setToolTip('Apply changes to this segment before exporting')
        self.doc_apply_btn.clicked.connect(self._document_apply_edit)
        editor_head.addWidget(self.doc_apply_btn)
        editor_layout.addLayout(editor_head)
        editors = QHBoxLayout()
        editors.setSpacing(9)
        self.doc_source = QPlainTextEdit()
        self.doc_source.setReadOnly(True)
        self.doc_source.setPlaceholderText('Select a row to compare its source text.')
        self.doc_source.setAccessibleName('Original English segment')
        self.doc_source.setMinimumHeight(75)
        editors.addWidget(self.doc_source, 1)
        self.doc_edit = QPlainTextEdit()
        self.doc_edit.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.doc_edit.setPlaceholderText('Select a translated row to edit its Persian text.')
        self.doc_edit.setAccessibleName('Editable Persian translation')
        self.doc_edit.setMinimumHeight(75)
        self.doc_edit.textChanged.connect(self._document_edit_changed)
        editors.addWidget(self.doc_edit, 1)
        editor_layout.addLayout(editors, 1)
        editor.setMinimumHeight(130)
        self.doc_splitter.addWidget(editor)
        self.doc_splitter.setStretchFactor(0, 3)
        self.doc_splitter.setStretchFactor(1, 2)
        self.doc_splitter.setSizes([260, 165])
        work_layout.addWidget(self.doc_splitter, 1)

        actions = QHBoxLayout()
        actions.setSpacing(9)
        self.doc_translate_button = QPushButton('Translate document')
        self.doc_translate_button.setObjectName('primary')
        self.doc_translate_button.clicked.connect(self._document_translate)
        self.doc_translate_button.setEnabled(False)
        actions.addWidget(self.doc_translate_button)
        self.doc_cancel_button = QPushButton('Cancel')
        self.doc_cancel_button.setEnabled(False)
        self.doc_cancel_button.clicked.connect(self._document_cancel)
        actions.addWidget(self.doc_cancel_button)
        actions.addStretch()
        actions.addWidget(QLabel('Export as'))
        self.doc_format = QComboBox()
        self.doc_format.addItems(sorted(OUTPUT_FORMATS))
        self.doc_format.setCurrentText('.docx')
        self.doc_format.setAccessibleName('Export file format')
        actions.addWidget(self.doc_format)
        self.doc_export_btn = QPushButton('Export…')
        self.doc_export_btn.setEnabled(False)
        self.doc_export_btn.clicked.connect(self._document_export)
        actions.addWidget(self.doc_export_btn)
        work_layout.addLayout(actions)
        self.doc_progress = QProgressBar()
        self.doc_progress.setRange(0, 100)
        self.doc_progress.setValue(0)
        self.doc_progress.setFixedHeight(15)
        self.doc_progress.setAccessibleName('Document processing progress')
        self.doc_progress.hide()
        work_layout.addWidget(self.doc_progress)
        self.doc_activity = QLabel('Ready to review extracted source text.')
        self.doc_activity.setObjectName('muted')
        self.doc_activity.setAccessibleName('Document processing status')
        self.doc_activity.setWordWrap(True)
        work_layout.addWidget(self.doc_activity)
        self.doc_pages.addWidget(workspace)
        self.doc_pages.setCurrentIndex(0)
        document_scroll = QScrollArea()
        document_scroll.setObjectName('documentScroll')
        document_scroll.setFrameShape(QFrame.Shape.NoFrame)
        document_scroll.setWidgetResizable(True)
        document_scroll.setWidget(self.doc_pages)
        panel.addWidget(document_scroll, 1)
        self.document_tab = tab
        self.tabs.addTab(tab, 'Documents')

    def _document_edit_changed(self) -> None:
        row = self.doc_table.currentRow()
        active = self.document_data is not None and 0 <= row < len(self.document_data.blocks)
        self.doc_apply_btn.setEnabled(bool(active and self.doc_edit.toPlainText().strip()
                                           and self.doc_edit.toPlainText() != self.document_data.blocks[row].translated))

    def _choose_document(self) -> None:
        choices = ' '.join('*'+s for s in sorted(INPUT_FORMATS))
        path, _ = QFileDialog.getOpenFileName(self, 'Open document for translation', '',
                                              f'Supported documents ({choices});;All files (*)')
        if path:
            self._open_document(path)

    def _open_document(self, filename: str) -> None:
        if ((self.document_job is not None and self.document_job.isRunning()) or
                (self.doc_load_job is not None and self.doc_load_job.isRunning())):
            self._status('Cancel the current document job first.')
            return
        if self.active_job is not None and self.active_job.isRunning():
            self._status('Wait until the current background operation finishes.')
            return
        engine = engine_label_to_key(self.ocr_choice.currentText())
        mode = ('auto', 'always', 'never')[self.ocr_mode.currentIndex()]
        if engine in ONLINE_OCR_ENGINES and mode != 'never':
            consent = QMessageBox.question(
                self, 'Send document pages to cloud OCR?',
                f'{self.ocr_choice.currentText()} may receive rendered document pages. '
                'Only continue if you have permission to share this document. '
                'Cloud services may charge for recognition.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if consent != QMessageBox.StandardButton.Yes:
                return
        self.document_data = None
        self.doc_table.setRowCount(0)
        self.doc_edit.clear()
        self.doc_source.clear()
        self.doc_export_btn.setEnabled(False)
        self._review_row = -1
        self.doc_pages.setCurrentIndex(1)
        provider_type = 'online' if engine in ONLINE_OCR_ENGINES else 'offline'
        self.doc_name.setText(f'Reading {Path(filename).name}…')
        self.doc_warnings.setText(f'Using {self.ocr_choice.currentText()} ({provider_type}). Review OCR-heavy files carefully before export.')
        # OCR is expensive; run extraction outside the GUI event loop.
        self.doc_cancel_button.setEnabled(True)
        self.doc_translate_button.setEnabled(False)
        self.doc_progress.setRange(0, 0)
        self.doc_progress.show()
        self.doc_activity.setText('Importing and recognizing text… You can cancel; an OCR page may take time to finish.')
        self.doc_load_job = DocumentLoadJob(Path(filename), engine, mode, self.cfg)
        self.doc_load_job.result.connect(self._document_loaded)
        self.doc_load_job.failed.connect(self._document_load_failed)
        self.doc_load_job.cancelled.connect(self._document_load_cancelled)
        self.doc_load_job.progress_update.connect(self._document_progress)
        self.doc_load_job.finished.connect(self._document_load_finished)
        self.doc_load_job.start()
        self.tabs.setCurrentWidget(self.document_tab)

    def _document_load_cancelled(self) -> None:
        self.doc_pages.setCurrentIndex(0)
        self.doc_progress.hide()
        self.doc_activity.setText('Document import cancelled.')
        self._status('Document import cancelled. No file was modified.')

    def _document_load_failed(self, message: str) -> None:
        self.doc_pages.setCurrentIndex(0)
        self.doc_progress.hide()
        self.doc_activity.setText('Import failed. Check OCR settings and try again.')
        self._failure(message)

    def _document_load_finished(self) -> None:
        self.doc_progress.hide()
        self.doc_cancel_button.setEnabled(False)
        self.doc_translate_button.setEnabled(self.document_data is not None)

    def _document_loaded(self, document: DocumentData) -> None:
        self.document_data = document
        ocr_count = sum(1 for b in document.blocks if b.ocr)
        self.doc_name.setText(f'{Path(document.source).name} — {len(document.blocks):,} segments · OCR-derived: {ocr_count:,}')
        self.doc_warnings.setText(' | '.join(document.warnings) or 'Text extracted. Review before translating.')
        self._document_fill_table()
        self.doc_pages.setCurrentIndex(1)
        self.doc_activity.setText('Text extraction complete. Review source blocks, then translate.')
        self.doc_export_btn.setEnabled(False)
        self._review_row = -1
        self.doc_table.selectRow(0)
        self._status(f'Loaded {len(document.blocks):,} segments. Review extraction, then click Translate entire document.')

    def _document_fill_table(self) -> None:
        if not self.document_data: return
        self.doc_table.blockSignals(True)
        self.doc_table.setRowCount(len(self.document_data.blocks))
        for i, b in enumerate(self.document_data.blocks):
            label = 'Page ' + str(b.page) if b.page else (f'Table {b.table+1}, {b.row+1}:{b.col+1}' if b.table is not None else b.kind)
            if b.ocr: label += ' [OCR]'
            for j, value in enumerate((label, b.text, b.translated)):
                self.doc_table.setItem(i,j,QTableWidgetItem(value[:3000]))
        self.doc_table.blockSignals(False)

    def _document_select(self) -> None:
        if not self.document_data:
            return
        row = self.doc_table.currentRow()
        previous = self._review_row
        if previous != row and 0 <= previous < len(self.document_data.blocks):
            edited = self.doc_edit.toPlainText()
            existing = self.document_data.blocks[previous].translated
            if edited != existing:
                choice = QMessageBox.question(
                    self, 'Unsaved correction',
                    'Apply your changes to the previous segment before switching?',
                    QMessageBox.StandardButton.Save |
                    QMessageBox.StandardButton.Discard |
                    QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Save,
                )
                if choice == QMessageBox.StandardButton.Cancel or (
                    choice == QMessageBox.StandardButton.Save and not edited.strip()
                ):
                    if not edited.strip() and choice == QMessageBox.StandardButton.Save:
                        self._status('A correction cannot be blank.')
                    self.doc_table.blockSignals(True)
                    self.doc_table.selectRow(previous)
                    self.doc_table.blockSignals(False)
                    return
                if choice == QMessageBox.StandardButton.Save:
                    self.document_data.blocks[previous].translated = edited.strip()
                    item = self.doc_table.item(previous, 2)
                    if item:
                        item.setText(edited[:3000])
                    self.doc_export_btn.setEnabled(all(b.translated.strip() for b in self.document_data.blocks))

        self._review_row = row
        if 0 <= row < len(self.document_data.blocks):
            block = self.document_data.blocks[row]
            self.doc_source.setPlainText(block.text)
            self.doc_edit.blockSignals(True)
            self.doc_edit.setPlainText(block.translated)
            self.doc_edit.blockSignals(False)
            self.doc_apply_btn.setEnabled(False)
        else:
            self.doc_source.clear()
            self.doc_edit.clear()
            self.doc_apply_btn.setEnabled(False)

    def _document_apply_edit(self) -> None:
        if not self.document_data: return
        row = self.doc_table.currentRow()
        if 0 <= row < len(self.document_data.blocks):
            translation = self.doc_edit.toPlainText().strip()
            if not translation:
                self._status('Correction cannot be blank.'); return
            self.document_data.blocks[row].translated = translation
            self.doc_table.item(row,2).setText(translation[:3000])
            self.doc_apply_btn.setEnabled(False)
            if all(b.translated.strip() for b in self.document_data.blocks):
                self.doc_export_btn.setEnabled(True)
            self._status('Updated document translation. This edit affects the exported file.')

    def _document_translate(self) -> None:
        if not self.document_data:
            self._status('Open a document first.'); return
        if self.document_job and self.document_job.isRunning(): return
        if self.active_job and self.active_job.isRunning():
            self._status('Finish importing before translating.'); return
        self.doc_translate_button.setEnabled(False)
        self.doc_cancel_button.setEnabled(True)
        self.doc_progress.setRange(0, 0)
        self.doc_progress.show()
        self.doc_activity.setText('Translating document… Waiting for the first segment. API calls may take time.')
        self.document_job = DocumentJob(self.document_data, self.pipeline)
        self.document_job.progress_update.connect(self._document_progress)
        self.document_job.result.connect(self._document_complete)
        self.document_job.failed.connect(self._document_translation_failed)
        self.document_job.cancelled.connect(self._document_translation_cancelled)
        self.document_job.finished.connect(self._document_finished)
        self.document_job.start()

    def _document_progress(self, current: int, total: int, message: str) -> None:
        if total > 0:
            self.doc_progress.setRange(0, total)
            self.doc_progress.setValue(current)
        else:
            self.doc_progress.setRange(0, 0)
        self.doc_activity.setText(message)
        self._status(message)

    def _document_translation_failed(self, message: str) -> None:
        self.doc_activity.setText('Document translation failed. Existing reviewed segments are unchanged.')
        self._failure(message)

    def _document_translation_cancelled(self) -> None:
        self.doc_activity.setText('Document translation cancelled. Existing reviewed segments are unchanged.')
        self._status('Document translation cancelled.')

    def _document_complete(self, document: DocumentData) -> None:
        self.document_data=document
        self._document_fill_table()
        self._review_row = -1
        self.doc_table.selectRow(0)
        self.doc_export_btn.setEnabled(all(b.translated.strip() for b in document.blocks))
        self.doc_progress.setRange(0, 100)
        self.doc_progress.setValue(100)
        self.doc_activity.setText('Complete · Review the Persian segments and export when ready.')
        self._status('Translation complete. Review entries and save your chosen format.')

    def _document_finished(self) -> None:
        self.doc_progress.hide()
        self.doc_translate_button.setEnabled(self.document_data is not None)
        self.doc_cancel_button.setEnabled(False)

    def _document_cancel(self) -> None:
        if self.document_job and self.document_job.isRunning():
            self.document_job.stop_event.set()
            self.doc_activity.setText('Cancelling after the current model request finishes…')
            self.doc_cancel_button.setEnabled(False)
            self._status('Cancellation requested; current model call may need to finish first.')
        elif self.doc_load_job and self.doc_load_job.isRunning():
            self.doc_load_job.stop_event.set()
            self.doc_activity.setText('Cancelling import after the current OCR page finishes…')
            self.doc_cancel_button.setEnabled(False)
            self._status('Document import cancellation requested; current OCR page may need to finish.')

    def _document_export(self) -> None:
        if not self.document_data:
            self._status('Load and translate a document first.'); return
        if (self.document_job and self.document_job.isRunning()) or (self.doc_load_job and self.doc_load_job.isRunning()):
            self._status('Wait for document processing to finish before exporting.'); return
        # Editing the current segment without pressing Apply must never cause
        # the exported document to silently contain an older translation.
        row = self.doc_table.currentRow()
        if 0 <= row < len(self.document_data.blocks):
            pending = self.doc_edit.toPlainText()
            stored = self.document_data.blocks[row].translated
            if pending != stored:
                decision = QMessageBox.question(
                    self, 'Unsaved document correction',
                    'You have an unapplied Persian correction. Apply it before exporting?',
                    QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard |
                    QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Save,
                )
                if decision == QMessageBox.StandardButton.Cancel:
                    return
                if decision == QMessageBox.StandardButton.Save:
                    if not pending.strip():
                        self._status('The Persian correction cannot be blank.'); return
                    self._document_apply_edit()
        ext=self.doc_format.currentText()
        name=Path(self.document_data.source).stem+'_fa'+ext
        path, _ = QFileDialog.getSaveFileName(self,'Export translated document',name,
                                            f'{ext.upper().lstrip(".")} files (*{ext})')
        if not path: return
        if Path(path).suffix.lower() != ext:
            path += ext
        try:
            save_document(self.document_data, Path(path))
        except Exception as exc:
            self._failure(f'Export failed: {exc}')
            return
        self._status(f'Saved {Path(path).name}. Check scientific terminology and layout before publishing.')

    def _library_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.library_label = QLabel(f'Imported dictionary entries: {self.db.count_entries():,}')
        layout.addWidget(self.library_label)
        details = QLabel('Built-in sample terminology and your own imported dictionaries are indexed locally. '\
                         'Import an additional DOCX dictionary below. Only high-confidence bilingual pairs are retained; '\
                         'review low-quality converted documents manually before publication.')
        details.setWordWrap(True)
        layout.addWidget(details)
        btns = QHBoxLayout()
        add = QPushButton('Import DOCX terminology')
        add.clicked.connect(self._add_dictionary)
        btns.addWidget(add)
        extract = QPushButton('Export feedback JSONL')
        extract.clicked.connect(self._export_feedback)
        btns.addWidget(extract)
        btns.addStretch()
        layout.addLayout(btns)
        self.library_log = QPlainTextEdit()
        self.library_log.setReadOnly(True)
        layout.addWidget(self.library_log)
        self.tabs.addTab(tab, 'Dictionary & Data')

    def _menu(self) -> None:
        file_menu = self.menuBar().addMenu('&File')
        self._action(file_menu, 'Load input from clipboard', 'Ctrl+Shift+V', self._paste_clipboard)
        self._action(file_menu, 'Open document for translation…', 'Ctrl+O', self._choose_document)
        self._action(file_menu, 'Import dictionary…', 'Ctrl+Shift+O', self._add_dictionary)
        self._action(file_menu, 'Export feedback…', 'Ctrl+Shift+E', self._export_feedback)
        file_menu.addSeparator()
        self._action(file_menu, 'Quit', 'Ctrl+Q', self.close)
        tools = self.menuBar().addMenu('&Tools')
        self._action(tools, 'Translate', 'Ctrl+Return', self._translate)
        self._action(tools, 'Translate selected text', 'Ctrl+Shift+T', self._translate_selection)
        self._action(tools, 'Preferences…', 'Ctrl+,', self._settings)
        help_menu = self.menuBar().addMenu('&Help')
        self._action(help_menu, 'About PsyLex', '', self._about)

    def _action(self, menu, label, shortcut, callback) -> None:
        act = QAction(label, self)
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
        act.triggered.connect(callback)
        menu.addAction(act)

    def _set_translation_notice(self, message: str, kind: str = 'muted') -> None:
        self.translation_notice.setText(message)
        self.translation_notice.setObjectName({
            'success': 'statusSuccess', 'error': 'statusDanger',
            'warning': 'statusWarning',
        }.get(kind, 'muted'))
        # Dynamic Qt stylesheet selectors need a repolish after state changes.
        style = self.translation_notice.style()
        style.unpolish(self.translation_notice)
        style.polish(self.translation_notice)

    def _update_activity_elapsed(self) -> None:
        elapsed = max(0, round(time.monotonic() - self._busy_started))
        if self._busy_kind == 'translation':
            job = self.active_job
            if job is not None and job.stop_event.is_set():
                self.translation_activity_detail.setText(
                    f'Cancelling… Waiting for the current model request to return ({elapsed}s).')
            else:
                self.translation_activity_detail.setText(
                    f'Waiting for the model · {elapsed}s elapsed. Timeout and retries are set in Settings.')
        elif self._busy_kind == 'batch':
            self.batch_activity.setToolTip(f'{elapsed}s elapsed')

    def _run(self, fn, on_success, *args, task='translation'):
        if self.active_job is not None and self.active_job.isRunning():
            self._status('A task is already running. Wait or cancel it before starting another.')
            return False
        if ((self.document_job and self.document_job.isRunning()) or
            (self.doc_load_job and self.doc_load_job.isRunning())):
            self._status('Finish or cancel document processing first.')
            return False
        self._busy_kind = task
        self._busy_started = time.monotonic()
        self.translate_button.setEnabled(False)
        if task == 'translation':
            self.translate_button.setText('Translating…')
            self.translation_activity_title.setText('Translating your text')
            self.translation_activity_detail.setText('Preparing terminology and contacting the model…')
            self.translation_activity.show()
            self.cancel_translation_btn.setEnabled(True)
            self._set_translation_notice(
                'Translation in progress. Your previous result is preserved until this succeeds.')
        else:
            self._status('Importing dictionary in the background…')
        self.progress.show()
        self.active_job = BackgroundJob(fn, *args)
        self.active_job.result.connect(on_success)
        self.active_job.cancelled.connect(self._translation_cancelled)
        self.active_job.failed.connect(self._failure)
        self.active_job.finished.connect(self._job_done)
        self._activity_timer.start()
        self.active_job.start()
        return True

    def _cancel_translation(self) -> None:
        if self._busy_kind != 'translation' or self.active_job is None or not self.active_job.isRunning():
            return
        self.active_job.stop_event.set()
        self.cancel_translation_btn.setEnabled(False)
        self.translation_activity_title.setText('Cancelling translation…')
        self._set_translation_notice('Cancellation requested. Current provider request may continue until timeout.', 'warning')
        self._update_activity_elapsed()

    def _translation_cancelled(self) -> None:
        self._set_translation_notice('Translation cancelled. The previous result and history were not changed.', 'warning')
        self._status('Translation cancelled; no result was saved.')

    def _job_done(self):
        task = self._busy_kind
        self._busy_kind = ''
        self._activity_timer.stop()
        self.progress.hide()
        self.translate_button.setEnabled(True)
        self.translate_button.setText('Translate  Ctrl+Enter')
        self.batch_button.setEnabled(True)
        if task == 'translation':
            self.translation_activity.hide()
            self.cancel_translation_btn.setEnabled(False)
        elif task == 'batch':
            self.batch_cancel_btn.setEnabled(False)
            self.batch_progress.hide()

    def _failure(self, message: str) -> None:
        self._status(message)
        if self._busy_kind == 'translation':
            # A modal popup hides the editor and makes users feel the app froze.
            # An inline, selectable error keeps recovery actions accessible.
            self._set_translation_notice(message, 'error')
            return
        QMessageBox.warning(self, 'Operation failed', message)

    def _translate(self) -> None:
        text = self.input.toPlainText().strip()
        if not text:
            self._set_translation_notice('Enter an English term, sentence, or paragraph to translate.', 'warning')
            self._status('Enter some English text first.')
            return
        if self.cfg.mode == 'dictionary':
            self._set_workspace_mode('translation')
        # Save only after success on the UI thread. A cancelled provider response
        # must not enter translation history or overwrite the current answer.
        if self._run(lambda source: self.pipeline.translate(source, save=False), self._translated, text):
            self._status('Translating… The activity panel shows progress and cancellation.')

    def _translated(self, result: Translation) -> None:
        result.id = self.db.save_translation(result)
        self.current = result
        self._set_translation_notice(
            'Translation completed. Review terminology and statistical details before using the output.',
            'success')
        self.output.setPlainText(result.target)
        value = f'{round(100 * result.confidence)}% (heuristic)' if result.confidence is not None else 'not calibrated'
        self.confidence_label.setText('Confidence: ' + value)
        self.warnings.setPlainText('\n'.join('• ' + w for w in result.warnings) or 'No automated QA warnings.')
        self.evidence.setRowCount(len(result.evidence))
        for row, e in enumerate(result.evidence):
            for col, value in enumerate([e.english, e.persian,
                         f'{e.source} — {e.location}', f'{e.strategy} ({e.score:.2f})']):
                self.evidence.setItem(row, col, QTableWidgetItem(str(value)))
        self.favorite_btn.setText('☆ Save')
        self._refresh_history()
        self._status('Translation completed; review the evidence and provide feedback.')

    def _use_evidence(self, item) -> None:
        row = item.row()
        persian_item = self.evidence.item(row, 1)
        if persian_item:
            self.output.setPlainText(persian_item.text())
            self._status('Suggestion copied into result field; approve to save it as a correction.')

    def _copy_translation(self) -> None:
        target = self.output.toPlainText().strip()
        if not target:
            self._status('Translate a term or sentence before copying the result.')
            return
        QApplication.clipboard().setText(target)
        self._status('Persian translation copied to clipboard.')

    def _favorite_current(self) -> None:
        if not self.current or self.current.id is None:
            self._status('Translate a term first before adding it to Favorites.')
            return
        self.db.favorite(self.current.id, True)
        self.favorite_btn.setText('★ Saved')
        self._refresh_history()

    def _feedback(self, accepted: bool) -> None:
        if not self.current:
            self._status('Translate a term first before submitting feedback.')
            return
        corrected = self.output.toPlainText().strip()
        if not accepted:
            from PySide6.QtWidgets import QInputDialog
            corrected, ok = QInputDialog.getMultiLineText(
                self, 'Correct translation', 'Enter the preferred Iranian Persian translation:',
                corrected)
            if not ok or not corrected.strip():
                return
        if not corrected:
            QMessageBox.warning(self, 'Feedback', 'A nonempty Persian translation is required.')
            return
        if not self.cfg.store_feedback:
            self._status('Feedback storage is disabled in Settings. No changes were saved.')
            return
        self.db.record_feedback(Feedback(self.current.source, corrected if accepted else self.current.target,
                                        accepted, '' if accepted else corrected.strip()))
        self._status('Feedback stored in local translation memory; future exact matches use it first.')
        if not accepted:
            self.output.setPlainText(corrected.strip())
        QMessageBox.information(self, 'Thank you', 'Translation memory updated locally.')

    def _refresh_history(self) -> None:
        history = self.db.history()
        self.history_table.setRowCount(len(history))
        for i, row in enumerate(history):
            for j, item in enumerate([row['id'], row['source'], row['target'], row['mode']]):
                self.history_table.setItem(i, j, QTableWidgetItem(str(item)))
        self.favorites.clear()
        for row in self.db.history(favorites_only=True):
            from PySide6.QtCore import Qt as _Qt
            from PySide6.QtWidgets import QListWidgetItem
            item = QListWidgetItem(f"{row['source'][:65]}  →  {row['target'][:65]}")
            item.setData(_Qt.ItemDataRole.UserRole, row['id'])
            self.favorites.addItem(item)

    def _open_history(self, row: int, col: int) -> None:
        id_item = self.history_table.item(row, 0)
        if id_item:
            self._load_history_id(int(id_item.text()))

    def _open_favorite(self, item) -> None:
        id_ = item.data(Qt.ItemDataRole.UserRole)
        self._load_history_id(int(id_))

    def _load_history_id(self, id_: int) -> None:
        row = next((x for x in self.db.history(1000) if x['id'] == id_), None)
        if not row:
            return
        self.input.setPlainText(row['source'])
        self.output.setPlainText(row['target'])
        self.current = None  # Prevent approving stale item as the current result.
        self.tabs.setCurrentIndex(0)
        self._status('Loaded translation from history. Translate again to submit new feedback.')

    def _paste_clipboard(self) -> None:
        self.input.setPlainText(QApplication.clipboard().text())
        self.tabs.setCurrentIndex(0)

    def _translate_selection(self) -> None:
        selection = self.input.textCursor().selectedText().replace('\u2029', '\n')
        if selection.strip():
            self.input.setPlainText(selection)
        elif QApplication.clipboard().text().strip():
            self.input.setPlainText(QApplication.clipboard().text())
        self.tabs.setCurrentIndex(0)
        self._translate()

    def _busy_with_translation(self) -> bool:
        return bool((self.active_job and self.active_job.isRunning()) or
                    (self.document_job and self.document_job.isRunning()) or
                    (self.doc_load_job and self.doc_load_job.isRunning()))

    def _on_tab_changed(self, index: int) -> None:
        page = self.tabs.widget(index)
        if page is self.dictionary_tab:
            self._set_workspace_mode('dictionary', show_page=False)
        elif page in (self.translation_tab, self.document_tab):
            self._set_workspace_mode('translation', show_page=False)

    def _set_workspace_mode(self, mode: str, *, show_page: bool = True) -> None:
        if mode not in ('dictionary', 'translation'):
            raise ValueError(f'Unsupported workspace mode: {mode}')
        if self._busy_with_translation() and mode != self.cfg.mode:
            self._status('Wait until the current operation finishes before switching workspaces.')
            self.mode_selector.blockSignals(True)
            self.mode_selector.setCurrentIndex(max(0, self.mode_selector.findData(self.cfg.mode)))
            self.mode_selector.blockSignals(False)
            return
        if self.cfg.mode != mode:
            self.cfg.mode = mode
            try:
                self.cfg.save()
            except Exception as exc:
                self._status(f'Mode changed; preferences were not saved: {exc}')
        self.mode_selector.blockSignals(True)
        self.mode_selector.setCurrentIndex(self.mode_selector.findData(mode))
        self.mode_selector.blockSignals(False)
        if show_page:
            target = self.dictionary_tab if mode == 'dictionary' else self.translation_tab
            self.tabs.setCurrentWidget(target)
        self._status('Dictionary: search the local psychology lexicon.' if mode == 'dictionary'
                     else f'Translation: {self.cfg.translation_backend.upper()} model configured in Settings.')

    def _mode_changed(self, index: int) -> None:
        mode = self.mode_selector.itemData(index)
        if mode in ('dictionary', 'translation'):
            self._set_workspace_mode(mode)

    def _settings(self) -> None:
        if self._busy_with_translation():
            self._status('Wait until the current operation finishes before editing settings.')
            return
        try:
            dialog = SettingsDialog(self.cfg, self)
            dialog.setStyleSheet(stylesheet(self.cfg.theme))
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            updated_cfg = dialog.cfg
            self.pipeline = TranslationPipeline(self.db, updated_cfg)
            self.cfg = updated_cfg
            self.setStyleSheet(stylesheet(self.cfg.theme))
            self.mode_selector.setProperty('uiDark', stylesheet(self.cfg.theme) == DARK)
            self.mode_selector.update()
            # Sync the quick-switcher without triggering its save callback.
            self.mode_selector.blockSignals(True)
            self.mode_selector.setCurrentIndex(max(0, self.mode_selector.findData(self.cfg.mode)))
            self.mode_selector.blockSignals(False)
            self.ocr_choice.setCurrentText(engine_key_to_label(self.cfg.ocr_engine))
            self.ocr_mode.setCurrentIndex({'auto': 0, 'always': 1, 'never': 2}.get(self.cfg.ocr_mode, 0))
            self._status('Settings saved and applied.')
        except Exception as exc:
            self._failure(f'Unable to open or apply Settings: {type(exc).__name__}: {exc}')

    def _load_seed(self) -> None:
        path = bundle_dir() / 'resources' / 'starter_glossary.jsonl'
        if not path.exists():
            self._status('No bundled lexicon; import a DOCX from Dictionary & Data.')
            return
        def load():
            import hashlib
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            return self.db.refresh_bundled_entries(load_jsonl(path), digest)
        self._run(load, lambda count: self._seed_done(count), task='dictionary_import')
        self._status('Importing bundled dictionary into the local database…')

    def _seed_done(self, count: int) -> None:
        self.library_label.setText(f'Imported dictionary entries: {self.db.count_entries():,}')
        self.library_log.appendPlainText(f'Starter glossary refresh: {count:,} entries updated (0 = already current)')
        self._status(f'{self.db.count_entries():,} terminology entries ready.')
        if self.dict_query.text().strip():
            self._dict_search()

    def _add_dictionary(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, 'Import bilingual DOCX', '', 'Word documents (*.docx)')
        if path:
            def ingest():
                entries = parse_docx(Path(path))
                return len(entries), self.db.insert_entries(entries)
            self._run(ingest, self._import_done, task='dictionary_import')

    def _import_done(self, result) -> None:
        candidates, inserted = result
        self.library_log.appendPlainText(f'Extracted {candidates:,}; imported {inserted:,} unique records')
        self.library_label.setText(f'Imported dictionary entries: {self.db.count_entries():,}')
        self._status(f'Added {inserted:,} entries. Inspect extraction before relying on ambiguous scanned text.')
        if self.dict_query.text().strip():
            self._dict_search()

    def _load_text_file(self, filename: str) -> None:
        path = Path(filename)
        try:
            if path.suffix.lower() == '.txt':
                text = path.read_text(encoding='utf-8-sig')
            elif path.suffix.lower() == '.docx':
                from docx import Document
                document = Document(path)
                text = '\n'.join(p.text for p in document.paragraphs if p.text.strip())
            else:
                return
            self.input.setPlainText(text[:15000])
            self._status(f'Loaded input from {path.name}; maximum 15,000 characters.')
        except Exception as exc:
            self._failure(str(exc))

    def _batch_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, 'Open batch', '', 'Data (*.txt *.csv)')
        if not path:
            return
        try:
            if path.lower().endswith('.csv'):
                with open(path, encoding='utf-8-sig', newline='') as file:
                    rows = list(csv.reader(file))
                column = next((i for i, name in enumerate(rows[0]) if name.casefold() in
                               {'english', 'source', 'term'}), 0) if rows else 0
                skip = 1 if rows and rows[0][column].casefold() in {'english', 'source', 'term'} else 0
                self.batch_rows = [r[column].strip() for r in rows[skip:] if len(r) > column and r[column].strip()]
            else:
                self.batch_rows = [x.strip() for x in Path(path).read_text(encoding='utf-8-sig').splitlines() if x.strip()]
            self.batch_rows = self.batch_rows[:10000]
            self.batch_results = []
            self.batch_table.setRowCount(len(self.batch_rows))
            for i, term in enumerate(self.batch_rows):
                self.batch_table.setItem(i, 0, QTableWidgetItem(term))
                self.batch_table.setItem(i, 2, QTableWidgetItem('Pending'))
            self._status(f'Loaded {len(self.batch_rows)} rows')
        except Exception as exc:
            self._failure(str(exc))

    def _batch_translate(self) -> None:
        if not self.batch_rows:
            self._status('Import a TXT or CSV list first.')
            return
        if ((self.active_job and self.active_job.isRunning()) or
            (self.document_job and self.document_job.isRunning()) or
            (self.doc_load_job and self.doc_load_job.isRunning())):
            self._status('Finish the current operation before starting the batch.')
            return
        self.batch_results = []
        self.batch_button.setEnabled(False)
        self.translate_button.setEnabled(False)
        self.batch_cancel_btn.setEnabled(True)
        self.batch_progress.setRange(0, len(self.batch_rows))
        self.batch_progress.setValue(0)
        self.batch_progress.show()
        self.batch_activity.setText(f'Translating 0 of {len(self.batch_rows):,} rows…')
        self._busy_kind = 'batch'
        self._busy_started = time.monotonic()
        self.progress.show()
        self.active_job = BatchJob(self.batch_rows, self.pipeline)
        self.active_job.result.connect(self._batch_done)
        self.active_job.cancelled.connect(self._batch_cancelled)
        self.active_job.failed.connect(self._failure)
        self.active_job.progress_update.connect(self._batch_progress_update)
        self.active_job.finished.connect(self._job_done)
        self._activity_timer.start()
        self.active_job.start()

    def _batch_progress_update(self, current: int, total: int) -> None:
        self.batch_progress.setValue(current)
        self.batch_activity.setText(f'Processed {current:,} of {total:,} rows…')
        self._status(f'Batch: {current:,}/{total:,} rows processed')

    def _batch_cancel(self) -> None:
        if self._busy_kind == 'batch' and self.active_job and self.active_job.isRunning():
            self.active_job.stop_event.set()
            self.batch_cancel_btn.setEnabled(False)
            self.batch_activity.setText('Cancellation requested. Finishing the current row…')

    def _batch_cancelled(self, rows) -> None:
        self._batch_done(rows, cancelled=True)

    def _batch_done(self, rows, cancelled: bool = False) -> None:
        self.batch_results = rows
        for i, (_, target, status) in enumerate(rows):
            self.batch_table.setItem(i, 1, QTableWidgetItem(target))
            self.batch_table.setItem(i, 2, QTableWidgetItem(status))
        for i in range(len(rows), len(self.batch_rows)):
            self.batch_table.setItem(i, 2, QTableWidgetItem('Cancelled' if cancelled else 'Pending'))
        self.batch_button.setEnabled(True)
        self.batch_activity.setText(
            f'Cancelled after {len(rows):,} rows. Export completed rows if needed.' if cancelled
            else f'Finished processing {len(rows):,} rows. Review failures before exporting.')
        self._refresh_history()
        self._status(self.batch_activity.text())

    def _batch_export(self) -> None:
        if not self.batch_results:
            self._status('Translate an imported batch before exporting results.')
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Export results', 'psylex_batch.csv', 'CSV (*.csv)')
        if path:
            with open(path, 'w', encoding='utf-8-sig', newline='') as fp:
                writer = csv.writer(fp)
                writer.writerow(['english', 'persian', 'status'])
                writer.writerows(self.batch_results)
            self._status(f'Exported {len(self.batch_results)} rows')

    def _export_feedback(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, 'Export reviews', 'feedback.jsonl', 'JSONL (*.jsonl)')
        if path:
            count = self.db.export_feedback(Path(path))
            self._status(f'Exported {count} local feedback records. Review before training.')

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        if not event.mimeData().hasUrls():
            return super().dropEvent(event)
        path = event.mimeData().urls()[0].toLocalFile()
        if Path(path).suffix.lower() in INPUT_FORMATS:
            self._open_document(path)
            self.tabs.setCurrentWidget(self.document_tab)
        else:
            self._status('Unsupported dropped file type.')

    def _about(self) -> None:
        QMessageBox.about(self, 'About PsyLex',
            'PsyLex Studio 0.6.5 Release Candidate\nEnglish → Persian psychology translation.\n\n'
            'Offline terms, optional local/cloud models, source evidence, and correction memory.\n'
            'Not medical advice. Human review required for academic or clinical publication.')

    def closeEvent(self, event):
        if ((self.active_job is not None and self.active_job.isRunning()) or
            (self.document_job is not None and self.document_job.isRunning()) or
            (self.doc_load_job is not None and self.doc_load_job.isRunning())):
            QMessageBox.information(self, 'Background task', 'Finish or cancel the current operation before quitting.')
            event.ignore()
            return
        self.db.close()
        event.accept()
