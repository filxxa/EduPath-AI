"""Pipeline orchestrator for document processing."""
from __future__ import annotations

import logging

from backend.documents.classification import classify_document
from backend.documents.extraction import extract_text
from backend.documents.fields import extract_fields
from backend.documents.merging import merge_documents
from backend.documents.models import ExtractedDocument, MergeProposal
from backend.documents.validation import validate_upload

logger = logging.getLogger(__name__)


def process_upload(
    filename: str,
    content: bytes | None = None,
    user_category: str | None = None,
) -> ExtractedDocument:
    """Run the full pipeline on a single uploaded file.

    When ``user_category`` is provided it is stored on the resulting
    ``ExtractedDocument`` and used for field-extraction routing instead of
    the auto-detected ``canonical_category``.  A non-blocking warning is
    appended when the user's category disagrees with auto-classification.
    """
    validation = validate_upload(filename, content)

    if not validation.valid or content is None:
        return ExtractedDocument(
            filename=filename,
            document_type="Unsupported / Invalid File",
            canonical_category=None,
            validation=validation,
            extraction_method="none",
            raw_text="",
            fields=[],
            user_category=user_category,
        )

    extraction = extract_text(filename, content)
    for error in extraction["errors"]:
        validation.add_error(error)
    for warning in extraction["warnings"]:
        validation.add_warning(warning)

    raw_text = extraction["raw_text"]
    classification = classify_document(filename, raw_text)
    auto_category = classification["canonical_category"]
    logger.info(
        f"Pipeline [{filename}]: method={extraction['extraction_method']}, "
        f"text_len={len(raw_text)}, category={auto_category}, "
        f"user_category={user_category}, "
        f"validation_valid={validation.valid}"
    )

    if user_category and auto_category and user_category != auto_category:
        from backend.documents.categories import CATEGORY_TO_CANONICAL
        user_canonical = CATEGORY_TO_CANONICAL.get(user_category, user_category)
        if user_canonical != auto_category:
            validation.add_warning(
                f"Auto-classification detected '{auto_category}' but you "
                f"categorized this as '{user_category}'. Using your selection."
            )

    routing_category = user_category or auto_category
    if routing_category and routing_category not in (
        "intermediate_transcript", "matric_certificate",
    ):
        routing_category_for_extract = auto_category
    else:
        routing_category_for_extract = routing_category

    if raw_text:
        fields = extract_fields(filename, raw_text, routing_category_for_extract)
        logger.info(f"Pipeline [{filename}]: extracted {len(fields)} fields")
    else:
        fields = []
        logger.warning(f"Pipeline [{filename}]: no raw_text — skipping field extraction")

    return ExtractedDocument(
        filename=filename,
        document_type=classification["document_type"],
        canonical_category=auto_category,
        user_category=user_category,
        validation=validation,
        extraction_method=extraction["extraction_method"],
        raw_text=raw_text,
        fields=fields,
        ocr_note=extraction["ocr_note"],
        is_scanned_pdf=extraction["is_scanned_pdf"],
        ocr_confidence=extraction["ocr_confidence"],
        page_count=extraction["page_count"],
        pages_processed=extraction["pages_processed"],
        ocr_attempts=extraction.get("ocr_attempts", []),
    )


def process_uploads(
    uploads: list[tuple[str, bytes]],
    user_categories: dict[str, str] | None = None,
) -> list[ExtractedDocument]:
    """Run the pipeline on multiple uploaded files.

    ``user_categories`` maps filename → user-selected category key.
    """
    categories = user_categories or {}
    return [
        process_upload(filename, content, user_category=categories.get(filename))
        for filename, content in uploads
    ]


def propose_profile(docs: list[ExtractedDocument]) -> MergeProposal:
    """Build a proposed profile from a list of extracted documents."""
    return merge_documents(docs)


def process_uploads_and_propose_profile(
    uploads: list[tuple[str, bytes]],
) -> tuple[list[ExtractedDocument], MergeProposal]:
    """Convenience helper: process uploads and build a merge proposal."""
    docs = process_uploads(uploads)
    proposal = propose_profile(docs)
    return docs, proposal
