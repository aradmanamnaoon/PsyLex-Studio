"""Persistent settings; secrets use OS keyring or environment variables."""
from __future__ import annotations
import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

SERVICE = "PsyLex Studio"
OCR_SECRET_FIELDS = (
    "ocrspace_api_key", "google_vision_api_key", "azure_document_key",
    "mathpix_app_key", "mistral_api_key",
)


def _keyring_get(name: str) -> str:
    try:
        import keyring
        return keyring.get_password(SERVICE, f"ocr:{name}") or ""
    except Exception:
        return ""


def _keyring_store(name: str, value: str) -> None:
    try:
        import keyring
        keyring.set_password(SERVICE, f"ocr:{name}", value)
    except Exception as exc:
        raise RuntimeError(
            "Could not securely save OCR credentials to the operating-system keyring. "
            "Install/configure the keyring backend before saving a cloud OCR key."
        ) from exc

DEFAULT_PROMPT = '''You are a professional English-to-Iranian-Persian psychology translator.
Translate faithfully, naturally, and precisely. Prefer the supplied psychology
terminology over a general-language meaning, preserving scientific register,
numbers, citations and abbreviations. Never invent source citations.
Return ONLY the Persian translation; no preamble, markdown or explanation.

Approved/contextual terminology (source anchors, not necessarily all approved):
{context}

Prior human-approved examples:
{examples}

English to translate:
{text}'''


def data_dir() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local")))
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
    return root / "PsyLexStudio"


def bundle_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))


@dataclass
class Settings:
    mode: str = "dictionary"
    translation_backend: str = "local"
    provider: str = "Ollama"
    model: str = "ollama/qwen2.5:7b"
    base_url: str = "http://localhost:11434"
    api_key_env: str = ""
    temperature: float = 0.1
    top_p: float = 1.0
    max_tokens: int = 2048
    seed: int = 42
    timeout_seconds: int = 120
    retry_attempts: int = 2  # transient failures only; total calls <= retry_attempts + 1
    transport: str = "native"  # direct HTTP for Ollama, OpenRouter, and local OpenAI-compatible servers
    provider_profiles: dict = field(default_factory=dict)  # non-secret model/URL drafts across restarts
    # Connection tests use this in-memory secret; never serialize it.
    session_api_key: str = field(default="", repr=False, compare=False)
    theme: str = "dark"
    retrieval_k: int = 6
    bm25_weight: float = 0.40
    vector_weight: float = 0.25
    fuzzy_weight: float = 0.35
    vector_enabled: bool = False
    embedding_model: str = "intfloat/multilingual-e5-small"
    vector_store: str = "chroma"
    reranker_model: str = ""
    multi_query: bool = False
    compression: bool = True
    feedback_examples: int = 4
    store_feedback: bool = True
    prompt: str = DEFAULT_PROMPT

    # OCR / document processing
    ocr_engine: str = "rapidocr"
    ocr_mode: str = "auto"
    ocr_language: str = "eng"
    ocr_timeout_seconds: int = 120
    ocrspace_api_key: str = ""
    google_vision_api_key: str = ""
    azure_document_endpoint: str = ""
    azure_document_key: str = ""
    aws_region: str = "us-east-1"
    mathpix_app_id: str = ""
    mathpix_app_key: str = ""
    mistral_api_key: str = ""
    mistral_model: str = "mistral-ocr-latest"

    # UX preferences
    ui_density: str = "comfortable"
    startup_tab: str = "translator"

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        path = path or data_dir() / "settings.json"
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            valid = {f.name for f in fields(cls)}
            clean = {k: v for k, v in data.items() if k in valid and k != "session_api_key"}
            # v0.5.x: local/api were workspace modes, not translation backends.
            legacy_mode = clean.get('mode', 'dictionary')
            if legacy_mode in {'local', 'api'}:
                clean['translation_backend'] = legacy_mode
                clean['mode'] = 'translation'
            # Normalize provider identifiers from pre-0.6.2 settings.
            canonical = {name.casefold(): name for name in (
                "OpenAI", "Azure OpenAI", "Anthropic", "Google Gemini", "Google Vertex AI",
                "Mistral", "Cohere", "Groq", "Together", "Fireworks", "OpenRouter",
                "DeepSeek", "xAI", "Perplexity", "Generic OpenAI endpoint", "Ollama",
                "LM Studio", "llama.cpp server", "vLLM", "GPT4All", "Transformers") }
            clean["provider"] = canonical.get(str(clean.get("provider", "Ollama")).casefold(), clean.get("provider", "Ollama"))
            # Cloud credentials never need to be copied into a new settings file.
            # Read legacy plaintext values for one-time migration when saved.
            for name in OCR_SECRET_FIELDS:
                if not clean.get(name):
                    clean[name] = _keyring_get(name)
            # A missing mode should not silently enable a network workflow.
            if not isinstance(clean.get("provider_profiles", {}), dict):
                clean["provider_profiles"] = {}
            return cls(**clean)
        except (ValueError, TypeError, OSError):
            return cls()

    def save(self, path: Path | None = None) -> None:
        path = path or data_dir() / "settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        settings_data = asdict(self)
        settings_data.pop("session_api_key", None)
        # Store credentials in Windows Credential Manager / OS keyring, not
        # plaintext JSON. Old plaintext fields are migrated on next save.
        # Failure is explicit and leaves the existing settings file intact.
        for field_name in OCR_SECRET_FIELDS:
            secret = settings_data.pop(field_name, "")
            if secret:
                _keyring_store(field_name, secret)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(settings_data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def get_key(self) -> str:
        """Credential order: explicitly entered test key > configured env > provider env > keyring.

        The temporary key is never persisted, including when the dialog is cancelled.
        A named but empty environment variable is an error rather than an
        accidental fallback to an unrelated key.
        """
        if self.session_api_key.strip():
            return self.session_api_key.strip()
        if self.api_key_env.strip():
            return os.environ.get(self.api_key_env.strip(), "").strip()
        standard = {
            "OpenRouter": "OPENROUTER_API_KEY", "OpenAI": "OPENAI_API_KEY",
            "Azure OpenAI": "AZURE_API_KEY", "Anthropic": "ANTHROPIC_API_KEY",
            "Google Gemini": "GEMINI_API_KEY", "Mistral": "MISTRAL_API_KEY",
            "Groq": "GROQ_API_KEY", "DeepSeek": "DEEPSEEK_API_KEY",
            "Together": "TOGETHERAI_API_KEY", "Fireworks": "FIREWORKS_AI_API_KEY",
            "xAI": "XAI_API_KEY", "Perplexity": "PERPLEXITYAI_API_KEY",
            "Cohere": "COHERE_API_KEY",
        }.get(self.provider)
        if standard and os.environ.get(standard, "").strip():
            return os.environ[standard].strip()
        try:
            import keyring
            return (keyring.get_password(SERVICE, self.provider)
                    or keyring.get_password(SERVICE, self.provider.lower()) or "")
        except Exception:
            return ""

    def get_stored_key(self, provider: str | None = None) -> str:
        """Read only this provider's secret from OS keyring, never from JSON.

        The value is used solely in a masked settings field after an explicit
        Settings dialog open. Environment variables are deliberately not
        copied into editable fields or provider profiles.
        """
        name = provider or self.provider
        try:
            import keyring
            return (keyring.get_password(SERVICE, name)
                    or keyring.get_password(SERVICE, name.lower()) or "")
        except Exception:
            return ""

    def set_key(self, key: str) -> None:
        try:
            import keyring
        except ImportError as exc:
            raise RuntimeError("Install keyring, or supply API_KEY_ENV variable.") from exc
        if key:
            keyring.set_password(SERVICE, self.provider, key)
        else:
            # Legacy versions sometimes saved lowercase provider names.
            # Clear both aliases or a deleted key would reappear on reopen.
            for name in {self.provider, self.provider.lower()}:
                try:
                    keyring.delete_password(SERVICE, name)
                except Exception:
                    pass

    def validate(self) -> None:
        if self.mode not in {"dictionary", "translation"}:
            raise ValueError("Unsupported workspace mode")
        if not self.model.strip():
            raise ValueError("Model ID is required. Choose a provider and enter its exact model ID.")
        if not (0 <= self.retry_attempts <= 5):
            raise ValueError("Retry attempts must be between 0 and 5")
        if self.transport not in {"native", "litellm"}:
            raise ValueError("Request transport must be native or litellm")
        if self.translation_backend not in {"local", "api"}:
            raise ValueError("Translation backend must be local or api")
        if self.ocr_mode not in {"auto", "always", "never"}:
            raise ValueError("Unsupported OCR mode")
        if self.ui_density not in {"comfortable", "compact"}:
            raise ValueError("Unsupported interface density")
        if self.startup_tab not in {"translator", "documents"}:
            raise ValueError("Unsupported startup tab")
        if not (0 <= self.temperature <= 2 and 0 < self.top_p <= 1):
            raise ValueError("Invalid sampling settings")
        if not (1 <= self.retrieval_k <= 30 and 32 <= self.max_tokens <= 32768):
            raise ValueError("Invalid retrieval / token count")
        if not (5 <= self.timeout_seconds <= 600 and 5 <= self.ocr_timeout_seconds <= 600):
            raise ValueError("Invalid timeout settings")
        if any(x not in self.prompt for x in ("{text}", "{context}", "{examples}")):
            raise ValueError("Prompt must include {text}, {context}, and {examples}")
