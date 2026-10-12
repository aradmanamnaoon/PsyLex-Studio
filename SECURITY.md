# Security and data handling

PsyLex stores provider API keys through the OS credential manager and stores application settings, correction history and imported terminology in per-user local storage. Avoid disclosing logs, support archives, local databases, exported translations, model weights and any credentials. Git ignores development builds and user data by default.

**Public-data boundary:** The two third-party psychology dictionaries and the derived full lexicon are not in this repository or public installer. The bundled `resources/starter_glossary.jsonl` is a small original illustration. User-imported dictionaries stay local unless the user deliberately selects a cloud model/provider for content processing.

To report a vulnerability, avoid posting keys, personal medical information or private documents in public GitHub issues. Rotate any key accidentally published. `.gitignore` does not remove files already in Git history.

Original code: MIT. Third-party libraries each have their own licenses; assess binary redistribution requirements (notably PyMuPDF) before redistributing a release.
