"""Windows-ready PsyLex Studio entry point."""
from __future__ import annotations
import logging
import sys
from pathlib import Path
from psylex.core.config import Settings, data_dir, bundle_dir
from psylex.core.database import Database


def packaged_self_test(report: Path, *, require_native_ocr: bool = True) -> int:
    """Offline, non-GUI packaged EXE validation.

    Run from Windows: PsyLexStudio.exe --self-test-report C:/temp/psylex-check.json
    This never sends a network request or touches the user's translation history.
    """
    import json
    import tempfile
    import importlib.util
    from PIL import Image, ImageDraw, ImageFont
    from psylex.core.database import Database
    from psylex.core.models import DictionaryEntry
    from psylex.core.dictionary import DictionaryService
    from psylex.core.ocr import run_ocr

    outcomes = {}
    resource = bundle_dir() / 'resources' / 'starter_glossary.jsonl'
    icon = bundle_dir() / 'assets' / 'branding' / 'logo_icon.png'
    outcomes['lexicon_present'] = resource.is_file() and resource.stat().st_size > 500
    outcomes['icon_present'] = icon.is_file()
    with tempfile.TemporaryDirectory(prefix='psylex-packaged-test-') as folder:
        db = Database(Path(folder) / 'probe.sqlite3')
        try:
            db.insert_entries([DictionaryEntry('attention', 'توجه', 'fixture', 'row 1', .99)])
            outcomes['dictionary_lookup'] = any(h.persian == 'توجه'
                for h in DictionaryService(db).search('ATTENTION'))
        finally:
            db.close()
    native = importlib.util.find_spec('rapidocr_onnxruntime') is not None
    outcomes['rapidocr_native_import'] = native
    if require_native_ocr and not native:
        outcomes['rapidocr_inference'] = False
    else:
        try:
            image = Image.new('RGB', (950, 150), 'white')
            draw = ImageDraw.Draw(image)
            font_file = Path('C:/Windows/Fonts/arial.ttf') if sys.platform == 'win32' else Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
            font = ImageFont.truetype(str(font_file), 48) if font_file.is_file() else ImageFont.load_default()
            draw.text((30, 34), 'Cognitive behavioral therapy', fill='black', font=font)
            recognized = run_ocr(image, 'rapidocr')
            outcomes['rapidocr_inference'] = bool(recognized.strip())
            outcomes['ocr_excerpt'] = recognized[:110]
        except Exception as exc:
            outcomes['rapidocr_inference'] = False
            outcomes['ocr_error'] = f'{type(exc).__name__}: {str(exc)[:200]}'
    passed = all(outcomes.get(x, False) for x in
        ('lexicon_present', 'icon_present', 'dictionary_lookup', 'rapidocr_inference'))
    if require_native_ocr:
        passed = passed and native
    payload = {'result': 'PASS' if passed else 'FAIL', 'platform': sys.platform,
               'python': sys.version.split()[0], 'checks': outcomes}
    report = Path(report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if passed else 1


def offer_local_models_on_first_launch(*, force: bool = False) -> str:
    """Show a non-blocking-inference wizard once per Windows user profile.

    The Qt dialog runs on the GUI thread; network discovery uses its worker
    thread. Only the explicit Use selected model action updates Settings.
    """
    from PySide6.QtWidgets import QApplication, QDialog
    from psylex.core.first_run import needs_model_setup, mark_model_setup_finished
    from psylex.ui.installation_models import InstallLocalModelDialog
    from psylex.ui.styles import stylesheet

    if not force and not needs_model_setup():
        return 'already-completed'
    app = QApplication.instance()
    if app is None:
        raise RuntimeError('The application must exist before first-launch setup.')
    app.setStyleSheet(stylesheet(Settings.load().theme))
    dialog = InstallLocalModelDialog()
    outcome = ('configured' if dialog.exec() == QDialog.DialogCode.Accepted
               else 'skipped')
    mark_model_setup_finished(outcome)
    return outcome


def main() -> int:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon
    from psylex.ui.main_window import MainWindow
    app = QApplication(sys.argv)
    app.setApplicationName('PsyLex Studio')
    app.setOrganizationName('PsyLex')
    icon = bundle_dir() / 'assets' / 'branding' / 'logo_icon.png'
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    location = data_dir()
    location.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=str(location / 'psylex.log'), level=logging.WARNING,
                        format='%(asctime)s %(levelname)s %(message)s')
    try:
        # First launch: choose a responding local model, or explicitly skip.
        # Do not run in self-test-report mode (handled in __main__ below).
        try:
            offer_local_models_on_first_launch()
        except Exception:
            logging.exception('Optional first-launch model setup failed; continuing app startup')
        db = Database(location / 'psylex.sqlite3')
        window = MainWindow(db, Settings.load())
        window.show()
        return app.exec()
    except Exception as exc:
        logging.exception('Fatal application startup error')
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(None, 'PsyLex startup failed', f'{type(exc).__name__}: {exc}')
        return 1


def model_setup_command() -> int:
    """Manual re-run used by the installer or for user-requested configuration."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName('PsyLex Studio')
    app.setOrganizationName('PsyLex')
    offer_local_models_on_first_launch(force=True)
    return 0


if __name__ == '__main__':
    if '--setup-local-models' in sys.argv:
        sys.exit(model_setup_command())
    if '--self-test-report' in sys.argv:
        index = sys.argv.index('--self-test-report')
        if index + 1 >= len(sys.argv):
            sys.exit(2)
        sys.exit(packaged_self_test(Path(sys.argv[index + 1])))
    sys.exit(main())
