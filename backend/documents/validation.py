"""File validation for uploaded documents."""
from __future__ import annotations

from pathlib import Path

from backend.documents.models import ValidationResult

TEXT_EXTENSIONS: set[str] = {".txt", ".md", ".csv"}
PDF_EXTENSIONS: set[str] = {".pdf"}
IMAGE_EXTENSIONS: set[str] = {".png", ".jpg", ".jpeg"}
SUPPORTED_EXTENSIONS: set[str] = TEXT_EXTENSIONS | PDF_EXTENSIONS | IMAGE_EXTENSIONS
PLACEHOLDER_EXTENSIONS: set[str] = set()
MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024


def _has_expected_signature(suffix: str, content: bytes) -> bool:
    if suffix == ".pdf":
        return b"%PDF-" in content[:1024]
    if suffix == ".png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix in {".jpg", ".jpeg"}:
        return content.startswith(b"\xff\xd8\xff")
    return True


def validate_upload(filename: str, content: bytes | None = None) -> ValidationResult:
    """Validate a single uploaded file before text extraction begins."""
    result = ValidationResult()

    if not filename or not isinstance(filename, str):
        result.add_error("Filename is missing or invalid.")
        return result

    suffix = Path(filename).suffix.lower()
    if not suffix:
        result.add_error("File has no extension.")
        return result

    if suffix not in SUPPORTED_EXTENSIONS:
        result.add_error(
            f"Unsupported file type '{suffix}'. Supported: "
            f"{', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
        return result

    if content is None:
        result.add_error("File content is missing.")
        return result

    if not isinstance(content, bytes):
        result.add_error("File content must be bytes.")
        return result

    if len(content) == 0:
        result.add_error("File is empty.")
        return result

    if len(content) > MAX_FILE_SIZE_BYTES:
        result.add_error(
            f"File is too large ({len(content) / 1024 / 1024:.1f} MB). "
            f"Maximum allowed is {MAX_FILE_SIZE_BYTES / 1024 / 1024:.0f} MB."
        )

    if suffix in TEXT_EXTENSIONS:
        null_bytes = content.count(b"\x00")
        if null_bytes > 0 and null_bytes / len(content) > 0.01:
            result.add_error("Text file appears corrupted or binary.")

    if suffix in PDF_EXTENSIONS | IMAGE_EXTENSIONS and not _has_expected_signature(suffix, content):
        result.add_error(f"File content does not match the '{suffix}' extension.")

    return result


def is_supported_text_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in TEXT_EXTENSIONS
