"""PyMuPDF-based PDF extraction with bounded scanned-page OCR."""
from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any

from backend.documents.ocr import MAX_IMAGE_PIXELS, extract_image_ocr

logger = logging.getLogger(__name__)

try:
    import pymupdf as fitz
except ImportError:  # pragma: no cover - exercised when runtime deps are absent.
    fitz = None  # type: ignore[assignment]

MAX_PDF_PAGES = 10
MAX_OCR_PAGES = 5
OCR_DPI = 300
# A real marksheet/certificate should have far more than this. Treating sparse
# embedded text (watermarks, page numbers, filenames) as sufficient causes
# scanned PDFs to skip OCR and return nothing useful.
MIN_TEXT_LAYER_CHARS = 150


@dataclass
class PdfExtraction:
    """Result of extracting text from a PDF."""

    raw_text: str = ""
    extraction_method: str = "error"
    ocr_confidence: float | None = None
    is_scanned_pdf: bool | None = None
    page_count: int | None = None
    pages_processed: int | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _combine_confidence(weighted_scores: list[tuple[float, int]]) -> float | None:
    total_words = sum(words for _, words in weighted_scores)
    if total_words == 0:
        return None
    return sum(score * words for score, words in weighted_scores) / total_words


def extract_pdf(content: bytes) -> PdfExtraction:
    """Extract text-layer content and OCR pages that lack usable text."""
    if fitz is None:
        return PdfExtraction(
            extraction_method="unavailable",
            errors=["PDF extraction dependencies are not installed."],
        )

    document: Any | None = None
    try:
        document = fitz.open(stream=content, filetype="pdf")
        if document.needs_pass:
            return PdfExtraction(
                errors=["This PDF is password-protected. Please upload an unlocked copy."],
            )

        page_count = document.page_count
        pages_processed = min(page_count, MAX_PDF_PAGES)
        result = PdfExtraction(page_count=page_count, pages_processed=pages_processed)
        if page_count > MAX_PDF_PAGES:
            result.warnings.append(
                f"Only the first {MAX_PDF_PAGES} PDF pages were processed."
            )

        chunks: list[str] = []
        text_layer_pages = 0
        ocr_pages = 0
        ocr_attempts = 0
        ocr_scores: list[tuple[float, int]] = []
        ocr_unavailable = False
        ocr_errors: list[str] = []
        needs_ocr = False

        for page_number in range(pages_processed):
            try:
                page = document.load_page(page_number)
                page_text = page.get_text("text").strip()
                logger.debug(
                    f"PDF page {page_number + 1}: text_layer={len(page_text)} chars"
                )
                if len(page_text) >= MIN_TEXT_LAYER_CHARS:
                    chunks.append(page_text)
                    text_layer_pages += 1
                    continue

                needs_ocr = True
                if ocr_attempts >= MAX_OCR_PAGES:
                    continue

                ocr_attempts += 1
                pixmap = page.get_pixmap(dpi=OCR_DPI, alpha=False)
                if pixmap.width * pixmap.height > MAX_IMAGE_PIXELS:
                    ocr_errors.append(
                        f"Page {page_number + 1} exceeds the image size limit for OCR."
                    )
                    continue

                ocr_result = extract_image_ocr(pixmap.tobytes("png"))
                logger.debug(
                    f"PDF page {page_number + 1} OCR: status={ocr_result.status}, "
                    f"text_len={len(ocr_result.raw_text)}"
                )
                if ocr_result.status == "success":
                    ocr_pages += 1
                    if ocr_result.raw_text:
                        chunks.append(ocr_result.raw_text)
                    if ocr_result.confidence is not None and ocr_result.word_count:
                        ocr_scores.append((ocr_result.confidence, ocr_result.word_count))
                    if ocr_result.message:
                        result.warnings.append(ocr_result.message)
                elif ocr_result.status == "unavailable":
                    ocr_unavailable = True
                else:
                    ocr_errors.append(ocr_result.message or f"OCR could not process page {page_number + 1}.")
            except Exception as e:
                logger.warning(f"PDF page {page_number + 1} processing failed: {e}")
                ocr_errors.append(f"Page {page_number + 1} could not be processed.")
                continue

        if needs_ocr and ocr_attempts >= MAX_OCR_PAGES:
            scanned_pages = pages_processed - text_layer_pages
            if scanned_pages > MAX_OCR_PAGES:
                result.warnings.append(
                    f"Only the first {MAX_OCR_PAGES} scanned PDF pages were OCR processed."
                )

        result.raw_text = "\n\n".join(chunks).strip()
        result.ocr_confidence = _combine_confidence(ocr_scores)

        if text_layer_pages and ocr_pages:
            result.extraction_method = "pdf_hybrid"
            result.is_scanned_pdf = True
        elif text_layer_pages:
            result.extraction_method = "pdf_text"
            result.is_scanned_pdf = None if ocr_unavailable else False
        elif ocr_pages:
            result.extraction_method = "pdf_ocr"
            result.is_scanned_pdf = True
        elif ocr_unavailable:
            result.extraction_method = "unavailable"
            result.is_scanned_pdf = None
            result.warnings.append("OCR is not available on this server; enter details manually.")
        elif ocr_errors:
            result.extraction_method = "error"
            result.is_scanned_pdf = None
            result.errors.extend(ocr_errors)
        else:
            result.extraction_method = "pdf_ocr"
            result.is_scanned_pdf = True
            result.warnings.append("No readable text was found. The PDF may be blank or low quality.")

        if ocr_errors and result.raw_text:
            result.warnings.extend(ocr_errors)
        logger.info(
            f"PDF extraction: method={result.extraction_method}, "
            f"text_len={len(result.raw_text)}, pages={text_layer_pages}+{ocr_pages}"
        )
        return result
    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        return PdfExtraction(errors=["This PDF appears corrupt or unreadable."])
    finally:
        if document is not None:
            document.close()
