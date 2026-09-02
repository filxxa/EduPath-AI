"""Backward-compatible document parsing facade.

This module delegates to the new `backend.documents` pipeline while preserving
the original `parse_upload()` and `build_profile_from_parsed()` signatures used
by the Streamlit UI.
"""
from __future__ import annotations

from typing import Any

from backend.documents import ExtractedDocument, process_upload, propose_profile


def parse_upload(filename: str, content: bytes | None = None) -> dict[str, Any]:
    """Parse an uploaded document and return a legacy-shaped dict."""
    doc = process_upload(filename, content)
    return doc.to_dict()


def build_profile_from_parsed(parsed_docs: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge parsed documents into a student profile (legacy shape)."""
    docs = [ExtractedDocument.from_dict(d) for d in parsed_docs]
    proposal = propose_profile(docs)
    return proposal.profile


def build_profile_proposal(parsed_docs: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a merge proposal, including conflicts and warnings, as a dict."""
    docs = [ExtractedDocument.from_dict(d) for d in parsed_docs]
    proposal = propose_profile(docs)
    return proposal.to_dict()
