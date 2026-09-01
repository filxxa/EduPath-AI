"""Document parsing helpers.

The MVP does not include production OCR. This module provides:
- Text extraction from plain text / markdown files.
- Filename-based hints for common Pakistani academic documents.
- A structured extraction step that the student can verify and edit.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


QUALIFICATION_HINTS = {
    "fsc pre-engineering": "FSc Pre-Engineering",
    "pre-engineering": "FSc Pre-Engineering",
    "pre engineering": "FSc Pre-Engineering",
    "ics": "ICS",
    "fsc": "FSc",
    "a-level": "A-Levels",
    "alevel": "A-Levels",
    "a level": "A-Levels",
    "fa": "FA",
}

BOARD_HINTS = {
    "fbi": "FBISE Islamabad",
    "fbise": "FBISE Islamabad",
    "islamabad": "FBISE Islamabad",
    "lahore": "BISE Lahore",
    "karachi": "BISE Karachi",
    "rawalpindi": "BISE Rawalpindi",
}


def _clean_text(text: str) -> str:
    return " ".join(text.replace("\r", " ").replace("\n", " ").split()).lower()


def extract_aggregate(text: str) -> float | None:
    """Find a percentage / aggregate value in text."""
    patterns = [
        r"aggregate[:\s]+(\d+(?:\.\d+)?)",
        r"percentage[:\s]+(\d+(?:\.\d+)?)",
        r"obtained[:\s]+(\d+(?:\.\d+)?)\s*%",
        r"(\d+(?:\.\d+)?)\s*%\s*(?:aggregate|overall|marks)",
        r"result[:\s]+(\d+(?:\.\d+)?)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = float(m.group(1))
            if 0 <= val <= 100:
                return val
    return None


def extract_qualification(text: str) -> str | None:
    t = _clean_text(text)
    for hint, value in QUALIFICATION_HINTS.items():
        if hint in t:
            return value
    return None


def extract_board(text: str) -> str | None:
    t = _clean_text(text)
    for hint, value in BOARD_HINTS.items():
        if hint in t:
            return value
    return None


def classify_document(filename: str) -> str:
    """Classify a document by filename for UI feedback."""
    name = Path(filename).name.lower()
    if any(k in name for k in ["fsc", "inter", "hssc", "intermediate"]):
        return "Academic Transcript (FSc/Intermediate)"
    if any(k in name for k in ["matric", "ssc", "metric"]):
        return "Matriculation Certificate"
    if any(k in name for k in ["cnic", "bform", "b-form", "identity"]):
        return "CNIC / B-Form"
    if any(k in name for k in ["nts", "nat", "entry test", "test result"]):
        return "Entry Test Score Card"
    if any(k in name for k in ["domicile", "residence"]):
        return "Domicile Certificate"
    if any(k in name for k in ["photo", "picture", "image"]):
        return "Photograph"
    return "Supporting Document"


def parse_text_file(content: str, filename: str) -> dict[str, Any]:
    text = content + " " + filename
    return {
        "document_type": classify_document(filename),
        "qualification": extract_qualification(text),
        "board": extract_board(text),
        "aggregate": extract_aggregate(text),
        "raw_text": content[:2000],
    }


def parse_upload(filename: str, content: bytes | None = None) -> dict[str, Any]:
    """Parse an uploaded document.

    For .txt / .md files we extract structured data from text.
    For PDFs and images we return a placeholder the student must verify.
    """
    suffix = Path(filename).suffix.lower()
    if suffix in (".txt", ".md", ".csv") and content is not None:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("utf-8", errors="ignore")
        return parse_text_file(text, filename)

    return {
        "document_type": classify_document(filename),
        "qualification": None,
        "board": None,
        "aggregate": None,
        "raw_text": "",
        "ocr_note": "OCR is not enabled in this MVP. Please confirm the extracted details manually.",
    }


def build_profile_from_parsed(parsed_docs: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge parsed document fields into a single student profile."""
    profile: dict[str, Any] = {
        "name": "",
        "qualification": None,
        "board": None,
        "aggregate": None,
        "documents": [],
    }
    aggregates: list[float] = []
    for doc in parsed_docs:
        if doc.get("qualification"):
            profile["qualification"] = doc["qualification"]
        if doc.get("board"):
            profile["board"] = doc["board"]
        if doc.get("aggregate") is not None:
            aggregates.append(doc["aggregate"])
        profile["documents"].append(doc["document_type"])

    if aggregates:
        profile["aggregate"] = max(aggregates)

    return profile
