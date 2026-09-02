"""File validation for uploaded documents."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.documents.models import ValidationResult


# Supported extensions that the pipeline can handle at some level.
SUPPORTED_EXTENSIONS: set[str] = {
    ".txt",
    ".md",
    ".csv",
}

# File types accepted for upload but only handled as placeholders until OCR arrives.
PLACEHOLDER_EXTENSIONS: set[str] = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
}

MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB


def validate_upload(filename: str, content: bytes | None = None) -> ValidationResult:
    """Validate a single uploaded file.

    Checks extension support, emptiness, size, and basic corruption indicators.
    Returns a ValidationResult; errors mean the file should not be processed.
    """
    result = ValidationResult()

    if not filename or not isinstance(filename, str):
        result.add_error("Filename is missing or invalid.")
        return result

    suffix = Path(filename).suffix.lower()
    if not suffix:
        result.add_error("File has no extension.")
        return result

    if suffix not in SUPPORTED_EXTENSIONS and suffix not in PLACEHOLDER_EXTENSIONS:
        result.add_error(
            f"Unsupported file type '{suffix}'. Supported: "
            f"{', '.join(sorted(SUPPORTED_EXTENSIONS | PLACEHOLDER_EXTENSIONS))}"
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

    # Basic corruption sniff: if a text file contains too many null bytes, treat it
    # as binary/corrupted.
    if suffix in SUPPORTED_EXTENSIONS:
        null_bytes = content.count(b"\x00")
        if null_bytes > 0 and null_bytes / len(content) > 0.01:
            result.add_error("Text file appears corrupted or binary.")

    if suffix in PLACEHOLDER_EXTENSIONS:
        result.add_warning(
            f"{suffix.upper()} files are accepted but not parsed in this version. "
            "Please enter the document details manually."
        )

    return result


def is_supported_text_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in SUPPORTED_EXTENSIONS
