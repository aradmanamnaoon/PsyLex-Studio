# Changelog

## v0.6.5 — Public-source and Windows release edition

- Preserves PySide6 UI, first-launch model detection and OS-keyring persistence with masked Show/Hide controls.
- Removes the two third-party dictionary DOCX files and the extracted 13,848-candidate JSONL from public source and binaries.
- Adds a small original starter glossary and keeps local import of user-supplied authorized DOCX dictionaries.
- Fixes built-in dictionary refresh to target only PsyLex-created seed entries and preserve user-imported materials.
- Updates regression tests, public dictionary smoke, and strict release gate for the intentionally small starter glossary.
- Adds public-source security audit, enhanced `.gitignore` and one-command Windows GitHub publishing workflow.

## Previous versions

Earlier development versions used locally provided reference books. Those private assets and their extracted lexicons must **never** be uploaded as part of this public release.
