"""Build a self-contained Windows executable and optional Inno Setup installer.

Run ON WINDOWS with Python, pip, PyInstaller, and optional Inno Setup.
PyInstaller creates executables for the host OS, not cross-platform.
"""
from __future__ import annotations
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / 'dist'


def run(command: list[str]) -> None:
    print('>', ' '.join(str(x) for x in command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def locate_iscc() -> str | None:
    exe = shutil.which('ISCC.exe') or shutil.which('iscc')
    if exe:
        return exe
    for dir_ in (r'C:\Program Files (x86)\Inno Setup 6', r'C:\Program Files\Inno Setup 6'):
        guess = Path(dir_) / 'ISCC.exe'
        if guess.exists():
            return str(guess)
    return None


def main() -> int:
    args = argparse.ArgumentParser(description='Package PsyLex Studio for Windows')
    args.add_argument('--onefile', action='store_true', help='single portable .exe instead of an installer-ready directory')
    args.add_argument('--skip-installer', action='store_true', help='skip Inno Setup')
    args.add_argument('--clean', action='store_true')
    args.add_argument('--dev-build', action='store_true',
                      help='diagnostic build only: bypass Windows release gate; NOT for publication')
    args.add_argument('--bundle-tesseract', action='store_true', help='bundle native Tesseract EXE, DLLs and English traineddata for legacy OCR support')
    options = args.parse_args()
    if sys.platform != 'win32':
        print('ERROR: Build on a Windows PC/VM. Windows .exe cross-compilation is not supported by PyInstaller.')
        return 2
    if not options.dev_build:
        print('Checking strict Windows release gate before packaging...', flush=True)
        gate = subprocess.run([sys.executable, 'scripts/release_gate.py',
                               '--require-windows', '--require-gui', '--require-native-ocr'],
                              cwd=ROOT, check=False)
        if gate.returncode != 0:
            print('ERROR: Strict release gate failed; installer build blocked. '
                  'Inspect reports/release_gate.json. For diagnostic-only builds '
                  'use --dev-build --skip-installer.')
            return 3
    else:
        print('WARNING: development-only package; strict release gate was NOT performed.')
    if options.clean:
        for folder in [ROOT / 'build', DIST]:
            shutil.rmtree(folder, ignore_errors=True)
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print('PyInstaller is missing: python -m pip install pyinstaller')
        return 2
    lexicon = ROOT / 'resources' / 'starter_glossary.jsonl'
    if not lexicon.exists():
        print('Original starter glossary missing: verify the public source package')
        return 2
    cmd = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--windowed',
           '--name', 'PsyLexStudio', '--clean',
           '--icon', str(ROOT / 'assets' / 'branding' / 'logo_icon.ico'),
           '--add-data', f'{ROOT / "resources"}{os.pathsep}resources',
           '--add-data', f'{ROOT / "assets"}{os.pathsep}assets',
           '--collect-submodules', 'litellm', '--collect-submodules', 'langgraph',
           '--collect-all', 'rapidocr_onnxruntime', '--collect-all', 'onnxruntime',
           '--hidden-import', 'keyring.backends.Windows']
    try:
        import paddleocr  # noqa: F401
        cmd += ['--collect-submodules', 'paddleocr']
        print('Optional OCR packaging: PaddleOCR detected and will be bundled.')
    except Exception:
        print('Optional OCR packaging: PaddleOCR not installed; exe will ship without the advanced local OCR engine.')
    if options.bundle_tesseract:
        candidates = [Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'Tesseract-OCR',
                      Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'Tesseract-OCR']
        tesseract_dir = next((d for d in candidates if (d/'tesseract.exe').is_file()), None)
        if tesseract_dir is None:
            raise RuntimeError('Tesseract not found in Program Files. Install before building the offline OCR installer.')
        model = tesseract_dir / 'tessdata' / 'eng.traineddata'
        if not model.is_file():
            raise RuntimeError(f'Tesseract English data not found: {model}')
        cmd += ['--add-binary', f'{tesseract_dir / "tesseract.exe"}{os.pathsep}tesseract']
        cmd += ['--add-data', f'{model}{os.pathsep}tesseract/tessdata']
        for dll in tesseract_dir.glob('*.dll'):
            cmd += ['--add-binary', f'{dll}{os.pathsep}tesseract']
        for license_name in ('LICENSE', 'LICENSE.txt', 'LICENSE.md', 'COPYING'):
            license_file = tesseract_dir / license_name
            if license_file.exists():
                cmd += ['--add-data', f'{license_file}{os.pathsep}tesseract']
        print('Including bundled OCR runtime:', tesseract_dir)
    cmd.append('--onefile' if options.onefile else '--onedir')
    cmd.append(str(ROOT / 'main.py'))
    run(cmd)
    exe = DIST / ('PsyLexStudio.exe' if options.onefile else 'PsyLexStudio/PsyLexStudio.exe')
    if not exe.exists():
        raise RuntimeError(f'Executable was not generated: {exe}')
    print('WINDOWS EXECUTABLE:', exe)
    if options.onefile:
        print('Portable single-file executable generated; use onedir for MSI-style installer.')
        return 0
    if options.skip_installer:
        return 0
    iscc = locate_iscc()
    if not iscc:
        print('Inno Setup 6 not found: executable works in dist/PsyLexStudio/.')
        print('Install Inno Setup and rerun this script to generate an installable Setup.exe.')
        return 0
    run([iscc, str(ROOT / 'installer.iss')])
    print('INSTALLER:', DIST / 'installer' / 'PsyLexStudio-Setup.exe')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
