"""Bounded Tesseract OCR support for uploaded document images."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import io
import os
import shutil
from typing import Any
import warnings

try:
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps, UnidentifiedImageError
except ImportError:  # pragma: no cover - exercised when optional runtime deps are absent.
    Image = None  # type: ignore[assignment]
    ImageEnhance = None  # type: ignore[assignment]
    ImageFilter = None  # type: ignore[assignment]
    ImageOps = None  # type: ignore[assignment]
    UnidentifiedImageError = Exception  # type: ignore[assignment,misc]

try:
    import pytesseract
except ImportError:  # pragma: no cover - exercised when optional runtime deps are absent.
    pytesseract = None  # type: ignore[assignment]

OCR_LANGUAGE = "eng"
OCR_TIMEOUT_SECONDS = 20
MAX_IMAGE_PIXELS = 40_000_000
MIN_OCR_CHARS = 15
MIN_IMAGE_LONG_EDGE = 1500
MAX_IMAGE_LONG_EDGE = 2400

_WINDOWS_TESSERACT_PATHS = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
    os.path.expandvars(r"%LOCALAPPDATA%\Tesseract-OCR\tesseract.exe"),
)


def _find_tesseract() -> str | None:
    """Locate a Tesseract binary from env, PATH, or known Windows install paths."""
    env_cmd = os.environ.get("TESSERACT_CMD")
    if env_cmd and os.path.isfile(env_cmd):
        return env_cmd

    path_binary = shutil.which("tesseract")
    if path_binary:
        return path_binary

    for candidate in _WINDOWS_TESSERACT_PATHS:
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


@dataclass
class OcrResult:
    """OCR text and source-level confidence from one image."""

    raw_text: str = ""
    confidence: float | None = None
    word_count: int = 0
    status: str = "success"
    message: str | None = None


@lru_cache(maxsize=1)
def _availability() -> tuple[bool, str | None]:
    if pytesseract is None:
        return False, "OCR Python dependencies are not installed."

    command = _find_tesseract()
    if command:
        pytesseract.pytesseract.tesseract_cmd = command

    try:
        pytesseract.get_tesseract_version()
        if OCR_LANGUAGE not in pytesseract.get_languages(config=""):
            return False, "The English OCR language pack is not available."
    except Exception:
        return (
            False,
            "Tesseract OCR was not found. Install Tesseract or set TESSERACT_CMD.",
        )

    return True, None


def tesseract_available() -> bool:
    """Return whether the configured English Tesseract engine can run."""
    return _availability()[0]


def _prepare_image(image: Any) -> Any:
    """Preprocess image for optimal OCR: grayscale, contrast, threshold, upscale."""
    if Image is None or ImageOps is None:
        raise RuntimeError("OCR Python dependencies are not installed.")

    image = ImageOps.exif_transpose(image).convert("RGB")

    long_edge = max(image.size)
    if long_edge and long_edge < MIN_IMAGE_LONG_EDGE:
        scale = min(MIN_IMAGE_LONG_EDGE / long_edge, 2.5)
        new_size = tuple(max(1, round(side * scale)) for side in image.size)
        resampling = getattr(Image, "Resampling", Image).LANCZOS
        image = image.resize(new_size, resampling)

    gray = image.convert("L")
    gray = ImageOps.autocontrast(gray)

    if ImageEnhance is not None:
        gray = ImageEnhance.Contrast(gray).enhance(1.5)
        gray = ImageEnhance.Sharpness(gray).enhance(1.3)

    if ImageFilter is not None:
        gray = gray.filter(ImageFilter.SHARPEN)

    return gray


def _open_image(content: bytes) -> Any:
    if Image is None:
        raise RuntimeError("OCR Python dependencies are not installed.")

    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        image = Image.open(io.BytesIO(content))
        if image.width * image.height > MAX_IMAGE_PIXELS:
            raise ValueError("Image dimensions exceed the 40 MP OCR limit.")
        image.load()
    return image


def _text_and_confidence(data: dict[str, list[Any]]) -> tuple[str, float | None, int]:
    lines: dict[tuple[Any, Any, Any, Any], list[str]] = {}
    confidences: list[float] = []
    tokens = data.get("text", [])

    for index, token in enumerate(tokens):
        token = str(token).strip()
        if not token:
            continue

        line_key = tuple(
            data.get(key, [0] * len(tokens))[index]
            for key in ("page_num", "block_num", "par_num", "line_num")
        )
        lines.setdefault(line_key, []).append(token)

        try:
            confidence = float(data.get("conf", ["-1"] * len(tokens))[index])
        except (TypeError, ValueError):
            confidence = -1
        if confidence >= 0:
            confidences.append(confidence)

    raw_text = "\n".join(" ".join(words) for words in lines.values()).strip()
    average = sum(confidences) / len(confidences) if confidences else None
    return raw_text, average, len(confidences)


def _run_ocr_with_psm(prepared: Any, psm: int) -> tuple[str, float | None, int]:
    """Run Tesseract with a specific PSM mode and return (text, confidence, word_count)."""
    data = pytesseract.image_to_data(
        prepared,
        lang=OCR_LANGUAGE,
        config=f"--oem 3 --psm {psm}",
        output_type=pytesseract.Output.DICT,
        timeout=OCR_TIMEOUT_SECONDS,
    )
    return _text_and_confidence(data)


def ocr_image(image: Any) -> OcrResult:
    """Extract text and token confidence from a decoded Pillow image.

    Uses a multi-PSM strategy: if the initial PSM 6 pass yields fewer than
    100 characters, retries with PSM 11 (sparse text) and picks the better result.
    """
    available, reason = _availability()
    if not available:
        return OcrResult(status="unavailable", message=reason)

    try:
        prepared = _prepare_image(image)
        raw_text, confidence, word_count = _run_ocr_with_psm(prepared, 6)

        if len(raw_text) < 100:
            alt_text, alt_conf, alt_words = _run_ocr_with_psm(prepared, 11)
            if len(alt_text) > len(raw_text):
                raw_text, confidence, word_count = alt_text, alt_conf, alt_words

        if len(raw_text) < 100:
            alt_text, alt_conf, alt_words = _run_ocr_with_psm(prepared, 4)
            if len(alt_text) > len(raw_text):
                raw_text, confidence, word_count = alt_text, alt_conf, alt_words

    except RuntimeError:
        return OcrResult(
            status="error",
            message="OCR timed out before text could be extracted from this marksheet. "
            "Please upload a clearer scan or enter details manually.",
        )
    except Exception:
        return OcrResult(
            status="error",
            message="OCR could not read this marksheet. Please upload a higher-resolution "
            "image, ensure the text is upright and well-lit, or enter details manually.",
        )

    if len(raw_text) < MIN_OCR_CHARS:
        return OcrResult(
            raw_text=raw_text,
            confidence=confidence,
            word_count=word_count,
            status="empty",
            message="No readable text was found in this marksheet. The scan may be blank, "
            "low resolution, or too faint for OCR. Please upload a clearer image or enter "
            "details manually.",
        )

    return OcrResult(raw_text=raw_text, confidence=confidence, word_count=word_count)


def extract_image_ocr(content: bytes) -> OcrResult:
    """Decode uploaded image bytes and run OCR without leaking decoder errors."""
    try:
        image = _open_image(content)
    except Exception:
        return OcrResult(
            status="error",
            message="This marksheet image appears corrupt, unreadable, or too large for OCR. "
            "Please upload a fresh image or enter details manually.",
        )

    return ocr_image(image)
