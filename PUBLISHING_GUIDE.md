# Publish PsyLex Studio v0.6.5 on GitHub

## One command (from a fresh, extracted **public source** ZIP)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\publish_github.ps1
```

The script is meant to be executed from the root where `PUBLIC_RELEASE_MARKER.json` and `main.py` are located; it always builds new public-edition binaries. It requires Windows x64, internet access, and a GitHub account with permission to create repositories. If necessary, `winget` installs Git, GitHub CLI, and Inno Setup. The script runs GitHub CLI's browser sign-in flow if not authenticated. Browser confirmation cannot be automated safely.

### What it does

1. Verify the public-edition marker and reject original source books and derived dictionary exports.
2. Install build/publish tools, initialize a virtual environment and dependencies.
3. Run tests and strict Windows gate including real native OCR fixture and Qt GUI smoke tests.
4. Build a new PyInstaller app and compile an Inno Setup installer.
5. Run the packaged EXE self-test **with process wait**, requiring JSON result `PASS`.
6. Audit Git's staged paths to exclude binaries, secrets and original book contents.
7. Create the public repository `aradmanamnaoon/PsyLex-Studio` if it does not exist, push source and tag `v0.6.5`.
8. Attach `PsyLexStudio-Setup-v0.6.5.exe` as a GitHub Release asset with `RELEASE_NOTES.md`.
9. Print the source repository, release URL and SHA-256 hash.

The installer is **not included in Git commits**; it is uploaded to **Releases → Assets**.

### Important limits

- If the GitHub repository already exists, the script **stops** to prevent accidentally replacing an existing project or release. Inspect it before retrying.
- You must complete a real GitHub login if prompted. You may have to approve browser or device authorization.
- The installer and Windows UI must still be manually tested on a separate clean machine before broad distribution.
- The original books or their derived lexicon are not included; the built-in glossary is a small independent starter fixture.
- The script checks likely secret file names but cannot guarantee every file is safe. Review materials and third-party license obligations before sharing publicly.
- Publishing will create a public repository and release, which are publicly visible actions.
- **Dependency licensing:** Removing the books does not settle all licensing. PyMuPDF uses AGPL/commercial licensing. Before public redistribution, review https://pymupdf.io/licensing and the licenses for other bundled components. The release script does not grant a PyMuPDF commercial license or guarantee AGPL compliance.
- Files in the source ZIP are checksummed in `SHA256SUMS.txt`; the script rebuilds the installer from scratch rather than uploading the earlier private binary.

### Manual troubleshooting

```powershell
.\.venv\Scripts\python.exe scripts\public_release_audit.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\release_gate.py --require-windows --require-gui --require-native-ocr
gh auth status
git status --short
```

If the script stops, preserve its error and fix the underlying cause. Don't upload the old private installer as a fallback.
