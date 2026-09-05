"""Raw text extraction from uploaded documents."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.documents.ocr import extract_image_ocr
from backend.documents.pdf import extract_pdf

TEXT_EXTENSIONS = {".txt", ".md", ".csv"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def _result(
    raw_text: str = "",
    extraction_method: str = "error",
    ocr_note: str | None = None,
    is_scanned_pdf: bool | None = None,
    ocr_confidence: float | None = None,
    page_count: int | None = None,
    pages_processed: int | None = None,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
    ocr_attempts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "raw_text": raw_text,
        "extraction_method": extraction_method,
        "ocr_note": ocr_note,
        "is_scanned_pdf": is_scanned_pdf,
        "ocr_confidence": ocr_confidence,
        "page_count": page_count,
        "pages_processed": pages_processed,
        "errors": errors or [],
        "warnings": warnings or [],
        "ocr_attempts": ocr_attempts or [],
    }


def _ocr_note(method: str, confidence: float | None) -> str:
    source = "PDF OCR" if method.startswith("pdf") else "Image OCR"
    if confidence is None:
        return f"{source} extracted text. Please verify all details before using them."
    return (
        f"{source} extracted text with {confidence:.0f}% average token confidence. "
        "Please verify all details before using them."
    )


def extract_text(filename: str, content: bytes) -> dict[str, Any]:
    """Extract raw text and OCR metadata from a supported document."""
    suffix = Path(filename).suffix.lower()

    if suffix in TEXT_EXTENSIONS:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("utf-8", errors="ignore")
        return _result(raw_text=text, extraction_method="text")

    if suffix in IMAGE_EXTENSIONS:
        ocr = extract_image_ocr(content)
        attempts_data = [
            {
                "variant": a.preprocessing_variant,
                "psm": a.psm_mode,
                "chars": a.char_count,
                "words": a.word_count,
                "confidence": a.confidence,
                "preview": a.text_preview,
            }
            for a in ocr.attempts
        ]
        if ocr.status == "success":
            warnings = [ocr.message] if ocr.message else []
            if ocr.confidence is not None and ocr.confidence < 50:
                warnings.append(
                    f"OCR confidence is low ({ocr.confidence:.0f}%). "
                    "Please verify all extracted details carefully."
                )
            return _result(
                raw_text=ocr.raw_text,
                extraction_method="image_ocr",
                ocr_note=_ocr_note("image_ocr", ocr.confidence),
                ocr_confidence=ocr.confidence,
                warnings=warnings,
                ocr_attempts=attempts_data,
            )
        if ocr.status == "empty":
            note = ocr.message or (
                "No readable text was found in this marksheet. Please upload a clearer "
                "image or enter details manually."
            )
            return _result(
                raw_text=ocr.raw_text,
                extraction_method="image_ocr",
                ocr_note=note,
                ocr_confidence=ocr.confidence,
                warnings=[note],
                ocr_attempts=attempts_data,
            )
        if ocr.status == "unavailable":
            note = (
                "OCR is not available on this server. Install Tesseract or enter details "
                "manually."
            )
            return _result(
                extraction_method="unavailable",
                ocr_note=note,
                warnings=[note],
            )
        message = ocr.message or "This marksheet could not be processed."
        return _result(
            extraction_method="error",
            ocr_note=message,
            errors=[message],
        )

    if suffix == ".pdf":
        pdf = extract_pdf(content)
        warnings = list(pdf.warnings)
        note: str | None = None
        if pdf.extraction_method in {"pdf_ocr", "pdf_hybrid"}:
            note = _ocr_note(pdf.extraction_method, pdf.ocr_confidence)
        elif pdf.extraction_method == "pdf_text":
            note = "PDF text was extracted. Please verify all details before using them."
        elif pdf.extraction_method == "unavailable":
            note = "OCR is not available on this server; enter details manually."
        elif pdf.errors:
            note = pdf.errors[0]

        return _result(
            raw_text=pdf.raw_text,
            extraction_method=pdf.extraction_method,
            ocr_note=note,
            is_scanned_pdf=pdf.is_scanned_pdf,
            ocr_confidence=pdf.ocr_confidence,
            page_count=pdf.page_count,
            pages_processed=pdf.pages_processed,
            errors=pdf.errors,
            warnings=warnings,
        )

    return _result(
        extraction_method="placeholder",
        ocr_note="This file type is not parsed. Please confirm the details manually.",
    )
