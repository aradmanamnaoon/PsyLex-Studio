# Ten-minute PsyLex Studio evaluation (Windows)

This is a **voluntary first-user test**, not a request for stars or positive reviews. Try the actual v0.6.5 release and report candidly whether the workflow works. The application is research/productivity software, **not a validated clinical translator**.

## Before starting

- **Windows 10/11:** Download the tagged [v0.6.5 installer](https://github.com/aradmanamnaoon/PsyLex-Studio/releases/tag/v0.6.5). Verify that you are on GitHub's official release page and read the [release notes](../RELEASE_NOTES.md). The installer includes Python.
- **Other operating systems:** The shipped installer is Windows-specific. You can review source code, UX documents, and privacy boundaries, but **do not claim you tested the packaged Windows application**.
- **Python source installations:** The supported, hosted-CI-checked matrix is currently **3.10–3.12**. See [Python 3.13 compatibility issue](https://github.com/aradmanamnaoon/PsyLex-Studio/issues/1) for the unsupported release boundary. Python 3.11 is recommended.
- **No model or account required** for offline dictionary lookup. Optional local or cloud translation has separate setup, security and possibly cost implications.

## Suggested ten-minute test

| Minutes | Task | What to record |
| --- | --- | --- |
| 0–2 | Launch from the installed Windows Start menu shortcut. | Did the app start? What version, and was there an installation or Windows publisher warning? |
| 2–4 | Open **Dictionary** and search for **working memory** and **classical conditioning**. | Were results useful and clearly marked as glossary-backed? A missing item is valid feedback; the public built-in glossary has just 16 starter terms. |
| 4–6 | Inspect **Translation** without connecting to any cloud account. | Does the interface distinguish generated suggestions from dictionary evidence? Translation inference **may be unavailable** until a model is configured; do not mark it successful if you did not run it. |
| 6–8 | Open **Documents** and **Dictionary & Data** without importing confidential files. | Are the controls and instructions understandable? Use only your own invented or openly licensed material if you decide to test an import. |
| 8–10 | Read **Settings** privacy/provider options and note the first confusing step. | Are model/API-key requirements and optional cloud transmission clear? What one change would most improve usability? |

**Good synthetic inputs:** `working memory`, `classical conditioning`, `attentional bias`, and an invented sentence such as *"Participants recalled five unrelated words after a short delay."* These are **evaluation prompts**, not claims that all expressions are present in the 16-term sample dictionary.

## Report precisely what happened

[Open the optional first-run issue form](https://github.com/aradmanamnaoon/PsyLex-Studio/issues/new?template=first-run.yml). Indicate the last stage you reached, Windows environment, and a specific observed behavior or reproducible failure. Installation problems count as onboarding feedback, **not completed active users**. Reports, reactions and downloads do not automatically establish independent model or translation accuracy.

Do **not** post screenshots containing names, participant or patient data, proprietary psychology books or dictionaries, unpublished research text, identifiable documents, credential values, or paid-provider tokens. We do not need any private data for first-run help.

## Independent technical review without Windows

Review source and release artifacts rather than claiming to have used the application:

- [Application source](../psylex) and [installation guidance](../README.md#get-psylex-for-windows).
- [Windows CI definition](../.github/workflows/windows-ci.yml), which exercises source tests and GUI smoke checks.
- [Current release notes](../RELEASE_NOTES.md) and [public-source safety audit](../scripts/public_release_audit.py).

Ask whether source tests cover the critical path, whether license obligations are transparent, and whether glossary evidence is distinguishable from model-generated output. A constructive negative assessment is as valuable as a positive one.
