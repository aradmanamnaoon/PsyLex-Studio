<div align="center">

<img src="assets/branding/logo_icon.png" alt="PsyLex Studio icon" width="110" />

# PsyLex Studio

### English → Persian psychology terminology, translation and document intelligence

**Go beyond word-for-word translation. Preserve the meaning behind the research.**

[![Release](https://img.shields.io/badge/release-v0.6.5-245d46?style=flat-square)](https://github.com/aradmanamnaoon/PsyLex-Studio/releases/tag/v0.6.5)
[![Windows](https://img.shields.io/badge/platform-Windows-376451?style=flat-square)](https://github.com/aradmanamnaoon/PsyLex-Studio/releases)
[![Python](https://img.shields.io/badge/Python-3.10--3.12-377653?style=flat-square)](pyproject.toml)
[![License](https://img.shields.io/badge/original%20code-MIT-40604f?style=flat-square)](LICENSE)

**[📖 Settings Guide](#complete-settings-guide)** · **[⬇️ Download Windows Installer](https://github.com/aradmanamnaoon/PsyLex-Studio/releases/download/v0.6.5/PsyLexStudio-Setup-v0.6.5.exe)** · **[Explore the App](#inside-the-workspace)** · **[Build from Source](#build-from-source)** · **[Release Notes](RELEASE_NOTES.md)**

**[🔎 Ten-minute honest first-run test](docs/FIRST_RUN_EVALUATION.md)** — the quick path for reviewers, including a safe feedback form and clear scope.

</div>

---

## Where psychology meets language

How do you translate *attentional bias*, *working memory*, or *classical conditioning* into Persian without losing their research meaning?

**PsyLex Studio** is a local-first Windows workbench for psychology students, researchers, translators, and anyone working between English and Iranian Persian. It combines terminology lookup, optional AI translation, document processing, OCR, and review in one focused desktop interface.

> **No API key is needed for offline dictionary lookup.** AI-assisted translation is optional: run a supported local model server or configure a cloud model.

## Inside the workspace

<div align="center">
<a href="docs/images/translation-workspace.svg"><img src="docs/images/translation-workspace.svg" width="100%" alt="PsyLex translation interface preview: English input, Persian result, terminology evidence and QA panels" /></a>

*Translation — compare English source and Persian output, then review terminology evidence.*
</div>

<table>
<tr>
<td width="50%" valign="top">
<a href="docs/images/dictionary-workspace.svg"><img src="docs/images/dictionary-workspace.svg" width="100%" alt="PsyLex psychology dictionary search interface preview" /></a>
<p align="center"><strong>Dictionary</strong><br />Search terms, compare equivalents, and browse related vocabulary.</p>
</td>
<td width="50%" valign="top">
<a href="docs/images/documents-workspace.svg"><img src="docs/images/documents-workspace.svg" width="100%" alt="PsyLex document translation and OCR interface preview" /></a>
<p align="center"><strong>Documents</strong><br />Import, extract, review, translate, and export.</p>
</td>
</tr>
</table>

<sub>These are illustrated interface previews based on the application's workflows, not screenshots captured from a running v0.6.5 Windows installation. Actual appearance varies by theme and version.</sub>

## What can PsyLex do?

| Workspace | Capabilities |
|:--|:--|
| **Dictionary** | Offline EN–FA glossary lookup, fuzzy suggestions, and provenance-aware terminology matches. |
| **Translation** | Model-powered translation with related dictionary evidence, quality notices, copy, favorites, and feedback. |
| **Documents** | Import documents and scans, extract text, run optional OCR, review translation segments, then export. |
| **Batch** | Process lists of terminology using TXT or CSV input. |
| **History & Favorites** | Return to past translations and store frequently used results. |
| **Dictionary & Data** | Build a private terminology library by importing material you are authorized to use. |

**A practical workflow:** research text → terminology lookup → model-assisted translation → human review → export.

PsyLex keeps **retrieved dictionary entries** distinct from **generated translations**, helping you see what was found versus what the model inferred.

## Get PsyLex for Windows

### Option 1 — Download the app

**[Download PsyLexStudio-Setup-v0.6.5.exe](https://github.com/aradmanamnaoon/PsyLex-Studio/releases/download/v0.6.5/PsyLexStudio-Setup-v0.6.5.exe)**

1. Download the installer from [Releases](https://github.com/aradmanamnaoon/PsyLex-Studio/releases/tag/v0.6.5).
2. Run setup and open PsyLex Studio from the Start menu.
3. Use **Dictionary** immediately, or configure a model to enable AI translation.
4. Open **Dictionary & Data** to import additional permitted reference material.

The packaged installer includes Python. You do **not** need a separate Python installation. An unsigned build may display a Windows publisher warning; check the release provenance before proceeding.

### Verified Python support

Use **Python 3.10–3.12** for current source installs, preferably Python **3.11** for the Windows release workflow. The 2026-10-12 hosted CI matrix passed on 3.10–3.12, but the Python 3.13 job failed during dependency installation, before tests. Its exact package-resolution cause remains under investigation in [issue #1](https://github.com/aradmanamnaoon/PsyLex-Studio/issues/1). Python 3.13 is **not currently claimed as supported**; this restriction does not alter the published v0.6.5 installer. Test the install and feature behaviour on your machine before trusting results.

### Option 2 — Build from source

Requires Python 3.10 and Windows. Open PowerShell in the repository root:

~~~powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe main.py
~~~

For tests and the public-source security audit:

~~~powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\public_release_audit.py
~~~

## Choose how your translation runs

| Local inference | Online inference |
|:--|:--|
| Connect a running **Ollama, LM Studio, llama.cpp, or vLLM** model server. | Configure a supported cloud provider such as **OpenRouter**. |
| First-launch model setup scans known local loopback endpoints. | Enter an API key in **Settings**. |
| Models and server software are installed separately. | Requests need internet access and may incur charges. |

**Model discovery detects running services**, not model weights scattered on your disks. Offline glossary lookup works independently of the chosen AI provider.

Saved API credentials use your operating system's credential store, with masked entry and Show/Hide/Forget controls.

## Complete Settings Guide

> **Start here if you're setting up PsyLex Studio v0.6.5.** This guide covers the five tabs in the actual Preferences window, safe defaults, step-by-step local and cloud model configuration, OCR, search, privacy, and troubleshooting. Basic offline Dictionary lookup needs none of these integrations.

### Settings guide contents

- [1. Opening Settings](#1-opening-settings)
- [2. Choosing local or cloud translation](#2-choosing-local-or-cloud-translation)
- [3. Connecting Ollama](#3-connecting-ollama)
- [4. Connecting LM Studio, llama.cpp and vLLM](#4-connecting-lm-studio-llamacpp-and-vllm)
- [5. Setting up OpenRouter and other cloud providers](#5-setting-up-openrouter-and-other-cloud-providers)
- [6. Models & API: every control](#6-models--api-every-control)
- [7. API keys and secure credential storage](#7-api-keys-and-secure-credential-storage)
- [8. Generation controls: practical defaults](#8-generation-controls-practical-defaults)
- [9. RAG / Search: every control](#9-rag--search-every-control)
- [10. Enabling optional dense retrieval](#10-enabling-optional-dense-retrieval)
- [11. Documents & OCR: every control](#11-documents--ocr-every-control)
- [12. Local OCR vs cloud OCR](#12-local-ocr-vs-cloud-ocr)
- [13. Prompt editor and mandatory placeholders](#13-prompt-editor-and-mandatory-placeholders)
- [14. Interface & Feedback: every control](#14-interface--feedback-every-control)
- [15. Dictionary import and practical workflows](#15-dictionary-import-and-practical-workflows)
- [16. Recommended configuration presets](#16-recommended-configuration-presets)
- [17. Troubleshooting Settings](#17-troubleshooting-settings)
- [18. Local data, backups and privacy](#18-local-data-backups-and-privacy)
- [19. Final setup checklist](#19-final-setup-checklist)

### 1. Opening Settings

1. Open the application from your Windows Start menu.
2. Select the **Settings** button at the top of the main window.
3. Or open **Tools → Preferences…**.
4. Or press **Ctrl+,**.
5. The window title is **Preferences • PsyLex Studio**.
6. Its long forms are scrollable; scroll inside the current tab.
7. Select **Models & API** for model/provider connections.
8. Select **RAG / Search** for terminology retrieval.
9. Select **Documents & OCR** for text recognition.
10. Select **Prompt** for translation instructions.
11. Select **Interface & Feedback** for appearance and feedback.
12. Select **Save** to apply validated changes.
13. Select **Cancel** to discard changes you have not saved.
14. Wait for an ongoing model scan or connection test to finish before closing Preferences.
15. The main-window **Dictionary / Translation** switch is a separate setting from backend choice.
16. Dictionary lookup can work with neither a local model nor an API key.

| I want to... | Where to go |
|:--|:--|
| Look up a term offline | Main window → Dictionary |
| Translate a paragraph | Main window → Translation |
| Connect Ollama | Settings → Models & API |
| Add my OpenRouter key | Settings → Models & API |
| Improve retrieval | Settings → RAG / Search |
| Process a scanned PDF | Settings → Documents & OCR |
| Customize translator instructions | Settings → Prompt |
| Change the app theme | Settings → Interface & Feedback |
| Import a bilingual glossary | Main window → Dictionary & Data |

### 2. Choosing local or cloud translation

The **Translation backend** dropdown has two options:

- **Local model (on your computer)** is the initial default.
- **Online API provider** uses an external inference service.
- Local models run in a separately installed runtime.
- Cloud requests require access to the chosen service and its authentication method.
- Choosing a backend does not download model weights.
- Choosing a backend does not start a local inference server.
- A valid **Model ID** is required before saving a translation configuration.
- Local and online providers can retain separate model/URL profiles.
- Offline Dictionary does not submit a request to your translation provider.
- Cloud translation may transmit input text and selected glossary context to the provider.

**Local provider options:** Ollama, LM Studio, llama.cpp server, vLLM, GPT4All, and Transformers.

**Cloud provider options:** OpenAI, Azure OpenAI, Anthropic, Google Gemini, Google Vertex AI, Mistral, Cohere, Groq, Together, Fireworks, OpenRouter, DeepSeek, xAI, Perplexity, and Generic OpenAI endpoint.

### 3. Connecting Ollama

Ollama is a practical starting point for local translation.

1. Install Ollama separately.
2. Start its background service or desktop application.
3. Open PowerShell.
4. Check the models installed on your computer:

~~~powershell
ollama list
~~~

5. If desired, download an example model:

~~~powershell
ollama pull qwen2.5:7b
~~~

6. Open PsyLex **Settings → Models & API**.
7. Select **Local model (on your computer)**.
8. Set **Provider** to **Ollama**.
9. Set **Model ID** to **ollama/qwen2.5:7b** only if that is actually installed.
10. Set **Base URL** to **http://localhost:11434**.
11. Set **Model connection method** to **Direct HTTP (recommended)**.
12. Normally leave the API key empty for a local Ollama service.
13. Select **Test connection**.
14. Wait for the connection test to finish.
15. Select **Save** after a successful test.
16. In the main window select **Translation**.
17. Translate one short, non-sensitive English psychology sentence.
18. Review the Persian output rather than assuming it is scientifically perfect.

**Faster method:** Use **Find running local servers and models**, select the responding model, then **Test connection → Save**.

### 4. Connecting LM Studio, llama.cpp and vLLM

#### LM Studio

1. Install LM Studio.
2. Download or import a supported model within LM Studio.
3. Load the model.
4. Start LM Studio's **Local Server**.
5. Find **Settings → Models & API** inside PsyLex.
6. Choose **Local model**.
7. Select **LM Studio**.
8. Default Base URL: **http://localhost:1234/v1**.
9. Enter the model ID reported by LM Studio, not an invented model name.
10. Use the local-server discovery button to populate available models.
11. Select **Test connection**.
12. Select **Save**.
13. Re-test if you change the loaded model or port in LM Studio.

#### llama.cpp server

1. Start your local llama.cpp server manually.
2. Make sure its OpenAI-compatible API is reachable.
3. Select **Local model → llama.cpp server**.
4. Default Base URL: **http://localhost:8080/v1**.
5. Enter the ID that the running server reports.
6. Test the connection and save.

#### vLLM

1. Start vLLM as an OpenAI-compatible local server.
2. Select **Local model → vLLM**.
3. Default Base URL: **http://localhost:8000/v1**.
4. Use the actual model identifier served by vLLM.
5. Test the connection and save.
6. Change the Base URL if your server uses a different port.

#### First-launch model discovery

- PsyLex offers an optional discovery wizard for a new Windows user profile.
- The wizard looks for **running** local model servers.
- It checks common localhost ports: 11434, 1234, 8080, and 8000.
- It does not scan your disks for downloaded model files.
- It does not download model weights.
- It does not automatically launch Ollama or LM Studio.
- Select **Scan again** after starting your local server.
- Select **Use selected model** to accept a discovered model.
- Select **Skip for now** to continue without local-model setup.
- Skipping does not erase your cloud configuration.
- The dialog generally appears once per Windows user profile.
- You can configure any model again later from Settings.
- You can manually reopen the wizard from a source checkout:

~~~powershell
.\.venv\Scripts\python.exe main.py --setup-local-models
~~~

### 5. Setting up OpenRouter and other cloud providers

#### OpenRouter setup

1. Obtain an OpenRouter account and an API key.
2. Open **Settings → Models & API**.
3. Set **Translation backend** to **Online API provider**.
4. Set **Provider** to **OpenRouter**.
5. Set **Model ID** to an available OpenRouter model.
6. Example: **openrouter/openai/gpt-4.1-mini** is the application's default OpenRouter example.
7. Actual account access and pricing are controlled by OpenRouter.
8. Leave **Base URL** blank for the default service.
9. Alternatively enter **https://openrouter.ai/api/v1**.
10. Do not route an OpenRouter API key to an unrelated domain.
11. Enter your secret in **API key (OS keyring)**.
12. Leave **API key environment variable** blank unless you intend to use an environment override.
13. Use **Direct HTTP (recommended)** first.
14. Select **Test connection**.
15. Select **Save**.
16. Close and reopen Settings to check that the key appears masked.
17. Translate a short example, then inspect any rate-limit or billing messages.

#### Other cloud providers

- Choose the provider that matches your account.
- Enter its supported model identifier.
- Provide the appropriate key or supported environment-based authentication.
- **OpenAI** expects an OpenAI-compatible model ID.
- **Azure OpenAI** normally needs your correct deployment and endpoint.
- **Google Vertex AI** may rely on application-default identity configuration.
- **Generic OpenAI endpoint** is for an OpenAI-compatible service with a custom Base URL.
- Model names and availability change independently of the PsyLex release.
- Test before sending lengthy or confidential material.
- Cloud providers can impose charges, quotas, regional restrictions, and retention rules.

### 6. Models & API: every control

| UI control | What it changes | Default or note |
|:--|:--|:--|
| Translation backend | Local vs online model | Local |
| Provider | Inference service | Ollama |
| Model ID | Identifier sent to selected provider | ollama/qwen2.5:7b |
| Base URL | Override API/server endpoint | http://localhost:11434 initially |
| Find running local servers and models | Detect active localhost services | Shown for local backend |
| Model connection method | Direct HTTP or LiteLLM | Direct HTTP |
| API key (OS keyring) | Secret for current provider | Usually empty for local runtime |
| Show | Temporarily reveal masked key | Explicit action |
| Hide | Re-mask the field | Recommended |
| Forget | Delete saved provider key after confirmation and Save | Reversible before Save |
| API key environment variable | Name of variable holding a key | Empty |
| Temperature | Sampling variability | 0.1 |
| Top-p | Sampling probability cutoff | 1.0 |
| Max tokens | Output length limit | 2048 |
| Seed (-1 disables) | Random seed when supported | 42 |
| Timeout (seconds) | Per-request timeout | 120 |
| Transient retries | Retry count for recoverable failures | 2 |
| Test connection | Probe current configuration | Does not itself save credentials |

**Choosing a model:** The provider, Model ID, and Base URL must match one another.

**Direct HTTP:** Prefer this for supported local servers and OpenRouter.

**LiteLLM (compatibility):** Try this when a provider integration needs the compatibility adapter.

**Test connection:** The test uses the current dialog values in memory. You must still select **Save** to persist them.

### 7. API keys and secure credential storage

Your model provider keys use Windows Credential Manager through the OS keyring interface.

1. Open **Models & API**.
2. Choose the correct cloud provider.
3. Paste its key into the API key field.
4. Click **Save** to persist it securely.
5. Reopen Settings.
6. The key field should be populated and **masked**.
7. Select **Show** only when you need to inspect its text.
8. Select **Hide** after inspection.
9. Each supported provider maintains its own credential.
10. Changing providers should restore that provider's unsaved draft or saved key.
11. Selecting **Cancel** does not commit unsaved API-key changes.
12. **Forget** first asks for confirmation.
13. A confirmed Forget action only takes effect after **Save**.
14. You may switch providers before saving; the pending removal should remain.
15. Forgetting a key does not delete the provider's model and URL preferences.
16. Never include live keys in issues, screenshots, error reports, or Git commits.

#### Credential priority

1. A temporarily entered key is used for the current **Test connection**.
2. If **API key environment variable** is configured, that named variable is consulted.
3. A standard provider variable may supply credentials where supported.
4. Otherwise, PsyLex reads the provider's OS keyring entry.
5. A configured but empty environment variable can block credential resolution.
6. If an apparently saved key is ignored, inspect the environment-variable field.
7. Clear conflicting overrides, select **Test connection**, and **Save**.

**OpenRouter environment variable example (temporary shell session):**

~~~powershell
$env:OPENROUTER_API_KEY = "your-own-secret-value"
~~~

- The example is not a real API key.
- Never paste actual credentials into documentation or Git commits.
- Environment variables set in one PowerShell session might not exist when launching the installed app from Start.
- For typical desktop use, use the built-in keyring-backed API key field.
- Ordinary settings.json is not intended to contain provider API-key plaintext.
- OCR service secrets are also handled separately from ordinary JSON preferences.
- Keep private user documents and diagnostics out of public GitHub issues.

### 8. Generation controls: practical defaults

| Control | Valid UI range | Starting value |
|:--|:--|:--|
| Temperature | 0–2, step 0.05 | 0.1 |
| Top-p | 0.01–1.0, step 0.05 | 1.0 |
| Max tokens | 32–32768 | 2048 |
| Seed | -1 to 2147483647 | 42 |
| Timeout (seconds) | 5–600 | 120 |
| Transient retries | 0–5 | 2 |

- Lower **Temperature** for more consistent specialist wording.
- Higher temperature can make phrasing more varied, not necessarily more accurate.
- Keep **Top-p** at 1.0 until you have a reason to tune it.
- Increase **Max tokens** if long outputs are truncated.
- Larger token budgets can cost more or take longer.
- Increase **Timeout** for slow local inference.
- Decrease timeout when you prefer a quicker connection failure.
- Retrying helps only with errors considered transient.
- A wrong API key will not be fixed by sending the same request again.
- A fixed seed is not a promise of reproducibility across every model.
- Some providers do not support all sampling controls.
- Always evaluate actual psychological terminology before changing many values at once.

### 9. RAG / Search: every control

RAG retrieves terminology evidence before the translation model writes a response.

| UI control | Meaning | Default |
|:--|:--|:--|
| Evidence results | How many evidence hits to request | 6 |
| Local embedding model | Optional local dense-search encoder | intfloat/multilingual-e5-small |
| Vector database | Vector storage backend | chroma |
| Enable dense retrieval | Turn on local vector search | Off |
| BM25 weight | Relative lexical relevance score contribution | 0.40 |
| Fuzzy weight | Relative approximate-match contribution | 0.35 |
| Dense weight | Relative vector relevance contribution | 0.25 |
| Reranker model | Optional cross-encoder reranking model | Empty |
| Enable multi-query expansion | Experimental query expansion | Off |
| Compress evidence snippets in prompt | Shorten evidence context | On |

#### Evidence results

- Accepts values from **1 to 30**.
- Start with the default **6**.
- Fewer results keep prompts more focused.
- More results can help with complex or ambiguous terms.
- Extra evidence cannot replace a missing dictionary entry.
- The public edition includes only **16 starter terms**.
- Importing authorized reference material improves the potential coverage.

#### Search ranking weights

- **BM25** is a lexical/token-based retrieval approach.
- **Fuzzy** is useful for spelling and term variations.
- **Dense** requires a separate vector index and embedding model.
- The weights influence ranking; they are not accuracy percentages.
- Keep **0.40 / 0.35 / 0.25** until you can evaluate retrieval outcomes.
- Exact matches and approved corrections remain useful evidence.
- Dense search is optional, and its absence should not disable ordinary dictionary lookup.

#### Experimental options

- **Reranker model:** Leave blank unless its extra dependencies and model are available.
- **Multi-query expansion:** Can change recall and processing time.
- **Compress evidence snippets:** Keep enabled initially to control prompt size.
- **Embedding model:** Needs appropriate language coverage and downloadable weights.
- **Chroma:** The only vector database currently offered by this Settings UI.
- Changing these options does not fine-tune a language model.

### 10. Enabling optional dense retrieval

Dense retrieval is an advanced feature for source installations.

1. Keep dense retrieval **Off** for the simplest, offline default.
2. To enable it, work from a local source checkout.
3. Open PowerShell in the project root.
4. Install the optional RAG packages:

~~~powershell
.\.venv\Scripts\python.exe -m pip install -e ".[rag]"
~~~

5. Import bilingual dictionary data you are authorized to process.
6. Build the local dense index:

~~~powershell
.\.venv\Scripts\python.exe scripts\build_index.py
~~~

7. The first build may download the selected embedding model.
8. Return to **Settings → RAG / Search**.
9. Turn on **Enable dense retrieval (requires prebuilt index)**.
10. Leave **Vector database** set to **chroma**.
11. Click **Save**.
12. Compare retrieval for representative terms.
13. If indexing fails, disable dense retrieval and use ordinary dictionary lookup.
14. The public Windows installer does not guarantee all optional RAG libraries are bundled.

### 11. Documents & OCR: every control

OCR extracts text from images and scanned pages.

| UI control | Purpose | Default or guidance |
|:--|:--|:--|
| Default OCR engine | Starting recognition engine | RapidOCR |
| Default OCR mode | Decide when to recognize images | auto |
| OCR language | Engine-dependent language hint | eng |
| OCR.space API key | Cloud OCR.space secret | Optional |
| Google Vision API key | Cloud Vision secret | Optional |
| Azure endpoint | Azure Document Intelligence service URL | Required for that provider |
| Azure key | Azure Document Intelligence key | Required for that provider |
| AWS region | AWS Textract region | us-east-1 |
| Mathpix app ID | Mathpix identifier | Required for that provider |
| Mathpix app key | Mathpix secret | Required for that provider |
| Mistral API key | Mistral OCR secret | Required for that provider |
| Mistral OCR model | OCR model name | mistral-ocr-latest |

#### Choosing OCR mode

- **auto:** Prefer embedded/selectable text where possible; OCR pages that need it.
- **always:** Request OCR when processing documents.
- **never:** Avoid OCR entirely.
- Use **auto** for most research PDFs.
- Use **always** for files made from scanned page images.
- Use **never** for trusted text-only material when OCR is unnecessary.
- A scanned PDF can produce no useful text with OCR disabled.
- The main **Documents** workspace also has per-workflow **OCR provider** and **Mode** controls.
- The default engine and mode in Settings initialize those controls.
- Language hints are not implemented identically by every OCR provider.

### 12. Local OCR vs cloud OCR

| Available engine | Where it runs | What you need |
|:--|:--|:--|
| RapidOCR (recommended offline) | Local | Included in typical Windows packaging |
| PaddleOCR (highest-quality local, optional) | Local | Additional installation |
| OCR.space (online) | External service | OCR.space API key |
| Google Cloud Vision (online) | External service | Google API key |
| Azure Document Intelligence (online) | External service | Endpoint and key |
| AWS Textract (online) | External service | AWS SDK credentials and region |
| Mathpix (online) | External service | App ID and app key |
| Mistral OCR (online) | External service | API key and OCR model |

#### Recommended offline OCR setup

1. Open **Settings → Documents & OCR**.
2. Select **RapidOCR (recommended offline)**.
3. Set **Default OCR mode** to **auto**.
4. Leave **OCR language** at **eng** for English input.
5. Leave all optional cloud OCR credentials blank.
6. Select **Save**.
7. Switch to the main **Documents** tab.
8. Select **Open document…**.
9. Load a document or scan that you have permission to process.
10. Review extracted source text and any warnings.
11. Translate only after verifying the extraction is readable.
12. Review corrected Persian segments before exporting.

#### Cloud OCR security guidance

- Selecting cloud OCR may transmit page images to an external company.
- The Documents workflow requests confirmation before such uploads.
- Do not send patient records or restricted research documents without appropriate permission.
- Different OCR services have different pricing, quotas, regions, and privacy terms.
- Store OCR API secrets through Settings rather than code or public files.
- OCR credentials are separate from language-model provider keys.
- For AWS Textract, supply suitable AWS SDK credentials; the form exposes an AWS region.
- Poor scan resolution can cause incorrect numbers, citations, or line order.
- Handwritten material, tables, and mixed languages need careful review.
- Always inspect extraction results before publishing translated research.

### 13. Prompt editor and mandatory placeholders

The **Prompt** tab contains the **Translation prompt** editor.

The default prompt asks for:
- Faithful English-to-Iranian-Persian psychology translation.
- Suitable academic register and terminology.
- Preservation of numbers, abbreviations, and references.
- No invented citations.
- Persian translation only, without preamble.

**These three placeholders are mandatory:**

| Placeholder | Supplied data |
|:--|:--|
| **{text}** | English input |
| **{context}** | Retrieved terminology evidence |
| **{examples}** | Previously human-approved examples |

- Do not delete **{text}**.
- Do not delete **{context}**.
- Do not delete **{examples}**.
- Keep the braces exactly as written.
- Settings validation blocks saving when a placeholder is missing.
- You can change instructions outside those placeholders.
- Avoid copying API keys or confidential notes into the prompt template.
- Use several test passages before adopting a custom prompt.

**Example adapted prompt:**

~~~text
Translate English psychology research into accurate Iranian Persian.
Keep numerical findings, abbreviations, references, and scientific meaning.
Use the terminology evidence when relevant. Never invent a reference.
Return only the Persian translation.

Terminology:
{context}

Reviewed examples:
{examples}

English text:
{text}
~~~

#### If your prompt causes problems

1. Verify all three placeholders are present.
2. Remove contradictory instructions.
3. Request translation only if the model adds introductions.
4. Check **Max tokens** if the answer stops early.
5. Check **Temperature** if phrasing becomes inconsistent.
6. Revert to a simpler prompt and retest one sentence.
7. Never treat an AI translation as a verified clinical interpretation.

### 14. Interface & Feedback: every control

| UI control | Choices | Default |
|:--|:--|:--|
| Theme | dark, light, system | dark |
| Interface density | comfortable, compact | comfortable |
| Startup tab | translator, documents | translator |
| Save accepted and corrected translations | Enabled or disabled | Enabled |
| Few-shot feedback examples | 0–12 | 4 |

#### Appearance

- **dark:** Dark application styling.
- **light:** Light application styling.
- **system:** Apply the application's system-theme handling.
- **comfortable:** More space around interactive controls.
- **compact:** Denser layout for smaller windows.
- **translator:** Open on the translation/dictionary workspace group.
- **documents:** Open on the Documents workspace.

#### Feedback

- **Approve** records a reviewed translation when feedback storage is enabled.
- **Suggest correction** lets you submit an edited Persian result.
- The Dictionary workspace also offers **Correct / approve** for selected terminology.
- Feedback can contribute examples to later translation prompts.
- **Few-shot feedback examples** controls the number of retrieved examples.
- **0** disables injecting examples from feedback into prompts.
- The default is **4** examples.
- Feedback is saved in local translation memory, not in a remote LLM's weights.
- Turning off future feedback storage does not automatically erase older records.
- Consider participant consent and research confidentiality before retaining text.

### 15. Dictionary import and practical workflows

The public edition intentionally ships with a **16-entry original starter glossary**.

1. Open **Dictionary** from the main window.
2. Search an English psychology term.
3. Review exact and related matches.
4. Select a result to inspect its provenance.
5. Use **Copy Persian** if the equivalent is appropriate.
6. Use **Open in Translation** for more context or prose translation.
7. For additional terminology, open **Dictionary & Data**.
8. Select **Import DOCX terminology**.
9. Choose a bilingual DOCX file you are authorized to use.
10. Wait for candidate terms to be extracted and indexed.
11. Review ambiguous entries and extraction quality.
12. The current dictionary import dialog supports **DOCX** files.
13. It does not promise direct PDF/CSV import into the dictionary library.
14. The **Documents** workspace supports more input formats for document processing.
15. Imported terms are kept in your local application database.
16. The third-party books and their extracted lexicon are **not** part of the public repository.
17. Dictionary lookup only knows the terms currently in your local glossary.
18. It does not invent a translation for an unknown term while in Dictionary mode.

#### Translation workflow

1. Select the **Translation** workspace mode.
2. Confirm a model connection in Settings.
3. Enter an English term, sentence, or paragraph.
4. Select **Translate** or press **Ctrl+Enter**.
5. Review Persian output and terminology evidence.
6. Inspect quality notices, especially for statistics and technical abbreviations.
7. Use **Approve** or **Suggest correction** when applicable.
8. Copy results or save them as favorites for later reference.

#### Documents workflow

1. Open the **Documents** tab.
2. Select an OCR provider and mode.
3. Open a supported DOCX, PDF, image, or other listed document type.
4. Review extracted English text.
5. Select **Translate document**.
6. Select a row to compare English and Persian segments.
7. Edit the Persian text and select **Apply correction**.
8. Choose an export format.
9. Select **Export…**.
10. Check the exported file before sharing.

### 16. Recommended configuration presets

#### Preset A: offline terminology lookup

| Setting | Suggested choice |
|:--|:--|
| Workspace | Dictionary |
| Translation model | Not needed |
| API key | Not needed |
| OCR engine | RapidOCR |
| Dense retrieval | Off |
| Additional vocabulary | Import authorized bilingual DOCX |
| Privacy | Work locally |

#### Preset B: private Ollama translation

| Setting | Suggested choice |
|:--|:--|
| Workspace | Translation |
| Backend | Local model |
| Provider | Ollama |
| Model ID | Your installed Ollama model |
| Base URL | http://localhost:11434 |
| Connection method | Direct HTTP |
| Temperature | 0.1 |
| Max tokens | 2048 to start |
| OCR | RapidOCR |
| Prompt | Default terminology-aware prompt |

#### Preset C: OpenRouter translation

| Setting | Suggested choice |
|:--|:--|
| Workspace | Translation |
| Backend | Online API provider |
| Provider | OpenRouter |
| Model ID | Available model on your account |
| Base URL | Empty or https://openrouter.ai/api/v1 |
| Credential storage | Windows Credential Manager |
| Environment override | Blank unless deliberate |
| Temperature | 0.1 |
| Timeout | 120 seconds |

#### Preset D: scanned research PDFs

| Setting | Suggested choice |
|:--|:--|
| Startup tab | documents |
| Default OCR engine | RapidOCR |
| Default OCR mode | auto |
| OCR language | eng |
| Model | Validated local or online provider |
| Workflow | Extract → review → translate → correct → export |
| Feedback storage | Enable only where retention is allowed |

### 17. Troubleshooting Settings

| Problem | What to check first |
|:--|:--|
| No local model detected | Start the model server; scan again |
| Ollama connection refused | Check localhost port 11434 |
| LM Studio does not respond | Load a model and start Local Server |
| Model not found | Copy exact server-reported model ID |
| Cloud HTTP 401/403 | Check key, account, and correct provider |
| OpenRouter HTTP 402 | Check provider credits and model billing |
| Saved key not used | Check named environment-variable override |
| Key missing after saving | Check for keyring failure or save warning |
| Connection test slow | Verify server and increase timeout if justified |
| Repeated timeouts | Reduce task size or use a faster model |
| Translation cut short | Increase Max tokens within provider limits |
| Inconsistent style | Lower Temperature or simplify Prompt |
| Dictionary too small | Import a permitted bilingual DOCX glossary |
| Dense retrieval empty | Build the index and enable it |
| OCR returns no text | Try auto or always OCR and verify the scan |
| OCR gets terms wrong | Review resolution and extracted text |
| Cloud OCR authentication error | Verify that OCR provider's separate credentials |
| Prompt cannot save | Restore {text}, {context}, {examples} |
| Cannot close Settings | Wait for ongoing scan/connection test |
| Interface feels cramped | Try compact density |
| Feedback appears in history | Feedback storage and historical data are distinct |

#### Local server diagnostic commands

To list installed Ollama models:

~~~powershell
ollama list
~~~

To query a running Ollama server:

~~~powershell
Invoke-RestMethod http://localhost:11434/api/tags
~~~

To query a running LM Studio local server:

~~~powershell
Invoke-RestMethod http://localhost:1234/v1/models
~~~

- These commands test the model runtimes, not the entire application.
- Use **Test connection** in PsyLex for the final end-to-end probe.
- Never include actual keys in logs or public bug reports.

### 18. Local data, backups and privacy

PsyLex stores per-user application data on Windows at:

~~~text
%LOCALAPPDATA%\PsyLexStudio\
~~~

| Path or store | Purpose |
|:--|:--|
| settings.json | Non-secret application and model preferences |
| psylex.sqlite3 | Local dictionary, history, favorites, feedback |
| psylex.log | Local diagnostic warnings |
| vectors/ | Optional local Chroma vector index |
| first_launch_local_model_setup.v1.json | Remembered first-launch setup outcome |
| Windows Credential Manager | Provider and supported OCR secrets |

#### Backup safely

1. Close PsyLex before copying its SQLite database.
2. Store backups outside any public repository.
3. Keep private research documents outside GitHub commits and issue attachments.
4. Copying settings.json does not automatically transfer OS-stored credentials.
5. On a new Windows user profile, re-enter keys into the credential store.
6. Do not delete your database to troubleshoot a connection issue.
7. Ollama and LM Studio model weights are managed by their respective applications.
8. Do not assume uninstalling PsyLex securely deletes every past backup.
9. Do not post unredacted API keys, medical records, or research participant data.
10. Check cloud provider policies before uploading sensitive material.

### 19. Final setup checklist

- [ ] Open **Settings** from the app or press **Ctrl+,**.
- [ ] Select Local model or Online API provider.
- [ ] Choose a provider and a valid Model ID.
- [ ] Set a matching Base URL.
- [ ] Confirm any required model runtime is actually running.
- [ ] Select **Test connection**.
- [ ] Click **Save**, then reopen Settings.
- [ ] Confirm provider and model are preserved.
- [ ] If using a cloud service, confirm its key is saved and masked.
- [ ] Ensure environment variables do not override the intended saved key.
- [ ] Keep all mandatory Prompt placeholders.
- [ ] Select the OCR engine and mode appropriate for your documents.
- [ ] Try a known term in offline Dictionary.
- [ ] Translate one short psychology sentence and review it.
- [ ] Import only dictionary data you have rights to use.
- [ ] Review OCR results before trusting document translation.
- [ ] Export and inspect a small test document.
- [ ] Choose your Theme, density and Startup tab.
- [ ] Decide whether to store accepted and corrected translations.

> **Mental model:** Dictionary retrieves local terminology; Translation calls a configured model; Documents & OCR extracts text; Settings connects the pieces. Start simple, verify one feature at a time, then enable optional integrations.

---

## A note about the included dictionary

This is the **public edition**, designed for redistributable source code and installation. It includes a **small, independently prepared 16-term starter glossary** to demonstrate offline search.

It does **not** include the two third-party psychology dictionaries or the large extracted lexicon from earlier private builds. A new installation is therefore **not** a comprehensive psychology reference work.

To grow your terminology database, use **Dictionary & Data** to import dictionaries you have permission to use. Imported terms are stored for your local workflow rather than being automatically sent to GitHub.

## How it works

~~~text
PsyLex Studio  ·  PySide6 desktop GUI
    │
    ├── Dictionary → local glossary + fuzzy retrieval
    ├── Translation → local or online language model
    ├── Documents → extraction + optional OCR + review + export
    ├── History / favorites / feedback → SQLite
    └── Settings → provider profiles + OS-backed credential storage
~~~

**Technology:** Python, PySide6 / Qt, SQLite, RapidFuzz, RapidOCR + ONNX Runtime, optional LiteLLM / LangGraph workflows, PyMuPDF and python-docx.

### Build a Windows release

Run the strict release gate:

~~~powershell
.\.venv\Scripts\python.exe scripts\release_gate.py --require-windows --require-gui --require-native-ocr
~~~

With **Inno Setup 6** installed, build the installer:

~~~powershell
.\.venv\Scripts\python.exe build_installer.py --clean
~~~

The expected output is `dist\installer\PsyLexStudio-Setup.exe`. Build artifacts and private user files are intentionally excluded by [`.gitignore`](.gitignore). For release-specific details, see [RELEASE_NOTES.md](RELEASE_NOTES.md).

## Frequently asked questions

<details>
<summary><strong>Can I use it without internet?</strong></summary>
<br />
Yes for the built-in offline dictionary and supported local processing. AI translation additionally requires a running local model server. Cloud translation is optional.
</details>

<details>
<summary><strong>Why does a fresh install contain only 16 glossary entries?</strong></summary>
<br />
The public version excludes third-party book content and private extracted databases. Import your own lawfully sourced terminology to extend the library.
</details>

<details>
<summary><strong>Why isn't my local LLM detected?</strong></summary>
<br />
Start Ollama, LM Studio or another supported server, ensure a model is served on localhost, and scan again. A downloaded model file alone is not discoverable.
</details>

<details>
<summary><strong>Can I trust OCR and AI output without checking?</strong></summary>
<br />
No. Scan quality, model capabilities, and specialist terminology vary. Always review extracted text and translations before using them in academic or clinical contexts.
</details>

## Open source, carefully

- **Original application code:** [MIT License](LICENSE).
- **Third-party dependencies:** May have different obligations, including PyMuPDF's AGPL/commercial terms. Review before redistributing modified binaries.
- **Imported reference materials:** Users are responsible for their right to use them.
- **Security:** Do not commit API keys, local databases, private model files, or patient/research documents. See [SECURITY.md](SECURITY.md).
- **Status:** v0.6.5 is research/productivity software, **not a clinical decision-support tool**.

**First time trying PsyLex?** Please [report your first-run experience](https://github.com/aradmanamnaoon/PsyLex-Studio/issues/new?template=first-run.yml), including installation failure or confusing screens. This is voluntary; do not paste confidential psychology reports, participant text, scanned personal documents, unpublished datasets, or provider API keys.

Found a reproducible bug, a terminology edge case, or an idea for improving the Persian language experience? **[Open an issue](https://github.com/aradmanamnaoon/PsyLex-Studio/issues)** with clear reproduction steps and sanitized screenshots.

<div align="center">

---

**Made for research that crosses languages.**

[⬇ Download](https://github.com/aradmanamnaoon/PsyLex-Studio/releases/tag/v0.6.5) · [Source](https://github.com/aradmanamnaoon/PsyLex-Studio) · [Issues](https://github.com/aradmanamnaoon/PsyLex-Studio/issues)

</div>
