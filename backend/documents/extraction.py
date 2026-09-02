"""Raw text extraction from uploaded documents."""
from __future__ import annotations

from pathlib import Path
from typing import Any


# File extensions that we treat as plain text.
TEXT_EXTENSIONS = {".txt", ".md", ".csv"}


def extract_text(filename: str, content: bytes) -> dict[str, Any]:
    """Extract raw text from a supported document.

    For text files the raw text is decoded from UTF-8. For PDFs and images a
    placeholder is returned so the pipeline can still classify by filename and
    leave manual entry to the student.

    Returns a dict with keys:
      - raw_text: str
      - extraction_method: "text" | "filename_only" | "placeholder"
      - ocr_note: str | None
      - is_scanned_pdf: bool | None
    """
    suffix = Path(filename).suffix.lower()

    if suffix in TEXT_EXTENSIONS:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("utf-8", errors="ignore")
        return {
            "raw_text": text,
            "extraction_method": "text",
            "ocr_note": None,
            "is_scanned_pdf": False if suffix == ".pdf" else None,
        }

    if suffix == ".pdf":
        return {
            "raw_text": "",
            "extraction_method": "placeholder",
            "ocr_note": "PDF parsing is not enabled in this version. Please confirm the details manually.",
            "is_scanned_pdf": None,  # Unknown until OCR is added.
        }

    if suffix in {".png", ".jpg", ".jpeg"}:
        return {
            "raw_text": "",
            "extraction_method": "placeholder",
            "ocr_note": "Image OCR is not enabled in this version. Please confirm the details manually.",
            "is_scanned_pdf": False,
        }

    # Should not reach here if validation runs first, but keep a safe fallback.
    return {
        "raw_text": "",
        "extraction_method": "placeholder",
        "ocr_note": "This file type is not parsed in this version. Please confirm the details manually.",
        "is_scanned_pdf": None,
    }
