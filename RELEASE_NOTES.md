# PsyLex Studio v0.6.5 — Windows Release

**Download:** `PsyLexStudio-Setup-v0.6.5.exe` from the Assets section below.

PsyLex Studio is a Windows desktop workspace for English-to-Persian psychology terminology, offline dictionary lookup, optional local or cloud LLM translation, document workflows, and OCR.

## Highlights

- First-run detection of **running** local model servers (Ollama, LM Studio, llama.cpp, vLLM); users can choose or skip.
- Stored API keys are retrieved from the OS credential store, remain masked when Settings reopens, and support Show/Hide/Forget.
- Offline dictionary mode with an **original 16-term introductory sample**, plus local import of user-supplied DOCX dictionaries.
- Document import, review, OCR and export; no Python install required on the Windows target PC.
- Source code, Windows tests, and Windows packaging scripts are published separately from the executable.

## Dictionary-data notice

**The two third-party psychology reference books and the derived full lexicon are NOT included in this release or public source repository.** The 16-term glossary is illustrative and not clinically validated. To use more terms, import your own lawfully obtained dictionary files using Dictionary & Data. Imported files and indexes remain on your computer, subject to the app's own data storage and selected processing provider.

## Installation

1. Download the installer and run it on Windows x64.
2. On first launch, select a running local LLM if available, or skip setup.
3. Import a dictionary if desired, or configure an online model API key in Settings.
4. Test Dictionary and Translation modes. Your cloud provider may charge for API usage.

## Known limitations

- The sample glossary is **not** the earlier 13,848-candidate reference lexicon.
- Local language models require a separately running inference server and model weights.
- Live cloud access and some OCR providers may require credentials or additional dependencies.
- The installer is not code-signed. Windows SmartScreen may show an unverified publisher notice.
- Redistributors should assess third-party runtime license obligations, including PyMuPDF's AGPL/commercial options.

Source license: MIT for original PsyLex code. Dependencies are licensed independently.
