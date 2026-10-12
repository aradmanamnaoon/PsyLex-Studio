"""Offline and cloud OCR adapters for PsyLex Studio.

Goals
-----
- ship with a strong Python-only offline OCR path
- support a higher-quality local OCR option when users want it
- expose optional cloud OCR providers behind a single interface
- never upload pages silently; provider choice must be explicit
"""
from __future__ import annotations

import base64
import io
import json
import time
from dataclasses import dataclass

from PIL import Image

OFFLINE_OCR_ENGINES = {
    "rapidocr": "RapidOCR (recommended offline)",
    "paddle": "PaddleOCR (highest-quality local, optional)",
}

ONLINE_OCR_ENGINES = {
    "ocrspace": "OCR.space (online)",
    "google_vision": "Google Cloud Vision (online)",
    "azure_di": "Azure Document Intelligence (online)",
    "aws_textract": "AWS Textract (online)",
    "mathpix": "Mathpix (online)",
    "mistral_ocr": "Mistral OCR (online)",
}

ALL_OCR_ENGINES = {**OFFLINE_OCR_ENGINES, **ONLINE_OCR_ENGINES}

DEFAULT_OCR_ENDPOINTS = {
    "ocrspace": "https://api.ocr.space/parse/image",
    "google_vision": "https://vision.googleapis.com/v1/images:annotate",
    "azure_di": "https://YOUR-RESOURCE.cognitiveservices.azure.com/",
    "aws_textract": "AWS SDK managed endpoint",
    "mathpix": "https://api.mathpix.com/v3/text",
    "mistral_ocr": "https://api.mistral.ai/v1/ocr",
}


@dataclass
class OCRConfig:
    ocr_language: str = "eng"
    ocrspace_api_key: str = ""
    google_vision_api_key: str = ""
    azure_document_endpoint: str = ""
    azure_document_key: str = ""
    aws_region: str = "us-east-1"
    mathpix_app_id: str = ""
    mathpix_app_key: str = ""
    mistral_api_key: str = ""
    mistral_model: str = "mistral-ocr-latest"


def available_engine_labels() -> list[str]:
    return list(ALL_OCR_ENGINES.values())


def engine_label_to_key(label: str) -> str:
    reverse = {v: k for k, v in ALL_OCR_ENGINES.items()}
    return reverse.get(label, "rapidocr")


def engine_key_to_label(key: str) -> str:
    return ALL_OCR_ENGINES.get(key, ALL_OCR_ENGINES["rapidocr"])


def engine_choices() -> list[tuple[str, str]]:
    return list(ALL_OCR_ENGINES.items())


def _lang(cfg: OCRConfig | object | None) -> str:
    return getattr(cfg, "ocr_language", getattr(cfg, "language", "eng")) if cfg else "eng"


def _image_to_png_bytes(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def _image_to_b64(image: Image.Image) -> str:
    return base64.b64encode(_image_to_png_bytes(image)).decode("ascii")


def _tesseract_fallback(image: Image.Image, cfg: OCRConfig | object | None = None) -> str:
    """Fallback used only when RapidOCR is unavailable in the runtime.

    End users should normally rely on bundled RapidOCR. This keeps tests and
    degraded environments functional.
    """
    try:
        import pytesseract
    except ImportError as exc:
        raise RuntimeError("RapidOCR is unavailable and pytesseract is not installed.") from exc
    try:
        return pytesseract.image_to_string(image, lang=_lang(cfg), config="--psm 3").strip()
    except Exception as exc:
        raise RuntimeError(f"RapidOCR is unavailable and the fallback OCR failed: {exc}") from exc


def _rapidocr(image: Image.Image, cfg: OCRConfig | object | None = None) -> str:
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        return _tesseract_fallback(image, cfg)
    engine = getattr(_rapidocr, "_engine", None)
    if engine is None:
        engine = RapidOCR()
        _rapidocr._engine = engine
    result, _ = engine(_image_to_png_bytes(image))
    if not result:
        return ""
    return "\n".join(str(item[1]) for item in result if len(item) > 1 and str(item[1]).strip()).strip()


def _paddle(image: Image.Image, cfg: OCRConfig | object | None = None) -> str:
    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise RuntimeError("PaddleOCR is not installed. Install optional OCR dependencies.") from exc
    import numpy as np
    engine = getattr(_paddle, "_engine", None)
    if engine is None:
        engine = PaddleOCR(
            lang="en",
            use_doc_orientation_classify=True,
            use_doc_unwarping=True,
            use_textline_orientation=True,
        )
        _paddle._engine = engine
    result = engine.predict(np.array(image.convert("RGB")))
    lines: list[str] = []
    for item in result:
        data = item.json
        if callable(data):
            data = data()
        data = data.get("res", data)
        lines.extend(str(line) for line in data.get("rec_texts", []) if str(line).strip())
    return "\n".join(lines).strip()


def _require_requests():
    try:
        import requests
        return requests
    except ImportError as exc:
        raise RuntimeError("The requests dependency is required for online OCR providers.") from exc


def _ocrspace(image: Image.Image, cfg: OCRConfig | object) -> str:
    api_key = getattr(cfg, "ocrspace_api_key", "")
    if not api_key:
        raise RuntimeError("Set the OCR.space API key in Settings > Documents & OCR.")
    requests = _require_requests()
    response = requests.post(
        DEFAULT_OCR_ENDPOINTS["ocrspace"],
        data={
            "apikey": api_key,
            "language": "eng",
            "isOverlayRequired": "false",
            "OCREngine": "2",
            "base64Image": "data:image/png;base64," + _image_to_b64(image),
        },
        timeout=120,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("IsErroredOnProcessing"):
        errors = "; ".join(payload.get("ErrorMessage") or payload.get("ErrorDetails") or ["OCR.space error"])
        raise RuntimeError(errors)
    return "\n".join((item.get("ParsedText") or "").strip() for item in payload.get("ParsedResults", [])).strip()


def _google_vision(image: Image.Image, cfg: OCRConfig | object) -> str:
    api_key = getattr(cfg, "google_vision_api_key", "")
    if not api_key:
        raise RuntimeError("Set the Google Vision API key in Settings > Documents & OCR.")
    requests = _require_requests()
    body = {
        "requests": [{
            "image": {"content": _image_to_b64(image)},
            "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
        }]
    }
    response = requests.post(f"{DEFAULT_OCR_ENDPOINTS['google_vision']}?key={api_key}", json=body, timeout=120)
    response.raise_for_status()
    data = response.json()["responses"][0]
    if data.get("error"):
        raise RuntimeError(data["error"].get("message", "Google Vision OCR failed"))
    return (data.get("fullTextAnnotation") or {}).get("text", "").strip()


def _azure_document_intelligence(image: Image.Image, cfg: OCRConfig | object) -> str:
    endpoint = getattr(cfg, "azure_document_endpoint", "").rstrip("/")
    key = getattr(cfg, "azure_document_key", "")
    if not (endpoint and key):
        raise RuntimeError("Set Azure endpoint and key in Settings > Documents & OCR.")
    requests = _require_requests()
    analyze_url = f"{endpoint}/documentintelligence/documentModels/prebuilt-read:analyze?api-version=2024-11-30"
    response = requests.post(
        analyze_url,
        headers={"Ocp-Apim-Subscription-Key": key, "Content-Type": "application/octet-stream"},
        data=_image_to_png_bytes(image),
        timeout=120,
    )
    response.raise_for_status()
    poll_url = response.headers.get("operation-location")
    if not poll_url:
        raise RuntimeError("Azure OCR did not return an operation-location header.")
    for _ in range(60):
        poll = requests.get(poll_url, headers={"Ocp-Apim-Subscription-Key": key}, timeout=60)
        poll.raise_for_status()
        payload = poll.json()
        status = payload.get("status", "").lower()
        if status == "succeeded":
            result = payload.get("analyzeResult", {})
            lines = []
            for page in result.get("pages", []):
                lines.extend((line.get("content") or "").strip() for line in page.get("lines", []))
            return "\n".join(x for x in lines if x).strip()
        if status == "failed":
            raise RuntimeError("Azure OCR analysis failed.")
        time.sleep(1.5)
    raise RuntimeError("Azure OCR timed out while polling for results.")


def _aws_textract(image: Image.Image, cfg: OCRConfig | object) -> str:
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError("boto3 is required for AWS Textract.") from exc
    region = getattr(cfg, "aws_region", "us-east-1") or "us-east-1"
    client = boto3.client("textract", region_name=region)
    response = client.detect_document_text(Document={"Bytes": _image_to_png_bytes(image)})
    lines = [item.get("Text", "").strip() for item in response.get("Blocks", []) if item.get("BlockType") == "LINE"]
    return "\n".join(x for x in lines if x).strip()


def _mathpix(image: Image.Image, cfg: OCRConfig | object) -> str:
    app_id = getattr(cfg, "mathpix_app_id", "")
    app_key = getattr(cfg, "mathpix_app_key", "")
    if not (app_id and app_key):
        raise RuntimeError("Set the Mathpix app ID and app key in Settings > Documents & OCR.")
    requests = _require_requests()
    payload = {"src": "data:image/png;base64," + _image_to_b64(image), "formats": ["text"], "ocr": ["text"]}
    response = requests.post(
        DEFAULT_OCR_ENDPOINTS["mathpix"],
        headers={"app_id": app_id, "app_key": app_key, "Content-type": "application/json"},
        data=json.dumps(payload),
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("error"):
        raise RuntimeError(str(data["error"]))
    return (data.get("text") or "").strip()


def _mistral_ocr(image: Image.Image, cfg: OCRConfig | object) -> str:
    api_key = getattr(cfg, "mistral_api_key", "")
    model = getattr(cfg, "mistral_model", "mistral-ocr-latest") or "mistral-ocr-latest"
    if not api_key:
        raise RuntimeError("Set the Mistral API key in Settings > Documents & OCR.")
    requests = _require_requests()
    body = {
        "model": model,
        "document": {"type": "image_url", "image_url": "data:image/png;base64," + _image_to_b64(image)},
    }
    response = requests.post(
        DEFAULT_OCR_ENDPOINTS["mistral_ocr"],
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=body,
        timeout=180,
    )
    response.raise_for_status()
    data = response.json()
    pages = data.get("pages") or []
    chunks: list[str] = []
    for page in pages:
        text = page.get("markdown") or page.get("text") or ""
        if text.strip():
            chunks.append(text.strip())
    if not chunks and data.get("text"):
        chunks.append(str(data["text"]).strip())
    return "\n\n".join(chunks).strip()


_DISPATCH = {
    "rapidocr": _rapidocr,
    "paddle": _paddle,
    "ocrspace": _ocrspace,
    "google_vision": _google_vision,
    "azure_di": _azure_document_intelligence,
    "aws_textract": _aws_textract,
    "mathpix": _mathpix,
    "mistral_ocr": _mistral_ocr,
}


def run_ocr(image: Image.Image, engine: str, cfg: OCRConfig | object | None = None) -> str:
    if engine not in _DISPATCH:
        raise ValueError(f"Unknown OCR engine: {engine}")
    configuration = cfg or OCRConfig()
    try:
        return _DISPATCH[engine](image, configuration).strip()
    except Exception as exc:
        message = str(exc)
        # requests.HTTPError can include URL query parameters containing API keys.
        # Never display credentials in GUI error messages or test logs.
        for name in ("ocrspace_api_key", "google_vision_api_key", "azure_document_key",
                     "mathpix_app_key", "mistral_api_key"):
            secret = getattr(configuration, name, "")
            if isinstance(secret, str) and secret:
                message = message.replace(secret, "[REDACTED]")
        raise RuntimeError(f"{engine} OCR failed: {message[:500]}") from None
