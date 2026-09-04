"""Centralized document-status helpers.

Single source of truth for answering "Has the student uploaded a document
of category X?" Used by Upload, Profile, Eligibility, and Action Plan pages.
"""
from __future__ import annotations

from typing import Any


def get_document_records(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Return document_records from profile, or empty list."""
    return list(profile.get("document_records") or [])


def has_document(profile: dict[str, Any], category: str) -> bool:
    """Check if a document of the given category exists in the profile.

    Checks ``document_records`` first (new path), then falls back to the
    legacy ``documents + document_labels`` combination.
    """
    records = get_document_records(profile)
    if records:
        return any(r.get("category") == category for r in records)

    docs = [d for d in profile.get("documents", []) if isinstance(d, str)]
    if docs:
        from backend.eligibility import _student_document_categories
        cats = _student_document_categories(docs)
        return category in cats

    return False


def get_document_status(
    profile: dict[str, Any],
    category: str,
) -> dict[str, Any]:
    """Return detailed status for a document category.

    Returns ``{uploaded, extraction_status, fields, filenames}``.
    """
    records = get_document_records(profile)
    matching = [r for r in records if r.get("category") == category]

    if not matching:
        return {
            "uploaded": False,
            "extraction_status": "none",
            "fields": {},
            "filenames": [],
        }

    all_fields: dict[str, Any] = {}
    filenames: list[str] = []
    best_status = "none"

    for rec in matching:
        filenames.append(rec.get("filename", "?"))
        status = rec.get("extraction_status", "none")
        fields = rec.get("fields") or {}
        all_fields.update(fields)

        if status == "extracted":
            best_status = "extracted"
        elif status == "partial" and best_status != "extracted":
            best_status = "partial"
        elif status == "failed" and best_status in ("none",):
            best_status = "failed"

    return {
        "uploaded": True,
        "extraction_status": best_status,
        "fields": all_fields,
        "filenames": filenames,
    }


def get_uploaded_categories(profile: dict[str, Any]) -> set[str]:
    """Return all categories with at least one uploaded document."""
    records = get_document_records(profile)
    if records:
        return {r["category"] for r in records if r.get("category")}

    docs = [d for d in profile.get("documents", []) if isinstance(d, str)]
    if docs:
        from backend.eligibility import _student_document_categories
        return _student_document_categories(docs)

    return set()


def document_exists_vs_extracted(
    profile: dict[str, Any],
    category: str,
) -> tuple[bool, bool]:
    """Return ``(doc_uploaded, data_extracted)``.

    Distinguishes "document was uploaded" from "data was successfully
    extracted from it."
    """
    status = get_document_status(profile, category)
    uploaded = status["uploaded"]
    extracted = status["extraction_status"] in ("extracted", "partial")
    return uploaded, extracted
