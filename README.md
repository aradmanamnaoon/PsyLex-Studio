# PsyLex Studio

English → Persian psychology terminology, translation and document OCR for Windows.

**Version:** 0.6.5 · **License:** MIT for original code · **Public source edition**

> **No third-party dictionary books or extracted proprietary lexicons are bundled.** A small original 16-term starter glossary demonstrates offline lookup. Import documents you are authorized to use to populate a private terminology library.

## Features

- Offline English–Persian dictionary search with fuzzy suggestions and entry provenance
- Optional local and online LLM translation and terminology-assisted generation
- First-launch detection of *running* Ollama, LM Studio, llama.cpp or vLLM servers
- API keys securely stored in the operating-system credential store, with masked view and Show/Hide/Forget controls
- Document translation, PDF processing, image OCR (RapidOCR), review and exports
- Local SQLite history, feedback and user-approved terminology corrections
- Keyboard-friendly, Windows-native PySide6 GUI

## Download for Windows

Visit **[Releases](../../releases)** and download `PsyLexStudio-Setup-v0.6.5.exe` from the release's **Assets** section. The Windows installer includes the Python runtime; no separate Python install is required for end users.

The bundled starter glossary is intentionally limited. Import your own lawfully sourced bilingual DOCX glossary from **Dictionary & Data** for fuller coverage. A local LLM requires a separately running model server. Cloud API calls may incur charges.

## Build from source

Open PowerShell in the repository root:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\public_release_audit.py
.\.venv\Scripts\python.exe main.py
```

Run the strict Windows gate before packaging:

```powershell
.\.venv\Scripts\python.exe scripts\release_gate.py --require-windows --require-gui --require-native-ocr
```

With Inno Setup 6 installed, build the installer:

```powershell
.\.venv\Scripts\python.exe build_installer.py --clean
```

The output will be `dist/installer/PsyLexStudio-Setup.exe`. Run `PsyLexStudio.exe --self-test-report ...` before uploading it.

## Publishing source and binaries

The **public-source ZIP**, not the older private dictionary build, contains `publish_github.ps1`. On Windows, open PowerShell **inside this public-source folder** and run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\publish_github.ps1
```

This script checks the source package, installs missing build/publishing tools using winget (when available), authenticates GitHub CLI if necessary, creates a venv, runs the tests and Windows gate, builds a *new* Windows installer from the public source, executes its packaged self-test, creates `aradmanamnaoon/PsyLex-Studio` and uploads the installer as a GitHub Release asset. It stops on failures. **Do not run it from the earlier private source folder.** GitHub sign-in may need an interactive browser approval.

See `PUBLISHING_GUIDE.md` and `RELEASE_NOTES.md` for details.

## Security and licensing

No API keys or user data should be committed. `.gitignore` excludes environments, executables, installers, databases, backups, and secrets. It is not a substitute for reviewing tracked files and Git history. Model weights and the two third-party dictionary books are not distributed. Users are responsible for the rights to any imported data.

Some dependencies have additional licensing obligations (including PyMuPDF AGPL/commercial licensing). Review those before redistribution. The translation system is research-oriented and not a substitute for clinical judgment.
