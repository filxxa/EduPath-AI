"""Structured field extraction from document text."""
from __future__ import annotations

import re
from typing import Any

from backend.documents.models import ExtractedField


QUALIFICATION_HINTS: dict[str, str] = {
    "fsc pre-engineering": "FSc Pre-Engineering",
    "pre-engineering": "FSc Pre-Engineering",
    "pre engineering": "FSc Pre-Engineering",
    "fsc pre medical": "FSc Pre-Medical",
    "pre-medical": "FSc Pre-Medical",
    "pre medical": "FSc Pre-Medical",
    "ics": "ICS",
    "fsc": "FSc",
    "a-level": "A-Levels",
    "alevel": "A-Levels",
    "a level": "A-Levels",
    "fa": "FA",
    "dae": "DAE",
}

BOARD_HINTS: dict[str, str] = {
    "fbi": "FBISE Islamabad",
    "fbise": "FBISE Islamabad",
    "islamabad": "FBISE Islamabad",
    "lahore": "BISE Lahore",
    "karachi": "BISE Karachi",
    "rawalpindi": "BISE Rawalpindi",
    "peshawar": "BISE Peshawar",
    "multan": "BISE Multan",
    "faisalabad": "BISE Faisalabad",
    "sargodha": "BISE Sargodha",
    "gujranwala": "BISE Gujranwala",
    "bahawalpur": "BISE Bahawalpur",
    "sahiwal": "BISE Sahiwal",
    "dera ghazi khan": "BISE Dera Ghazi Khan",
    "mirpur": "BIM Kashmir",
    "mirpur kashmir": "BIM Kashmir",
    "ajk": "BIM Kashmir",
}


def _clean_text(text: str) -> str:
    """Normalize text for matching."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def _find_first(patterns: list[str], text: str) -> re.Match | None:
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m
    return None


def extract_name(text: str) -> str | None:
    """Try to extract a candidate full name from the document text."""
    patterns = [
        r"(?:name|student name|candidate name)[ \t:]*([A-Z][a-z]+(?:[ \t]+[A-Z][a-z]+){1,3})",
        r"(?:mr\.?|ms\.?|mrs\.?)[ \t]+([A-Z][a-z]+(?:[ \t]+[A-Z][a-z]+){1,2})",
    ]
    m = _find_first(patterns, text)
    if m:
        return m.group(1).strip()
    return None


def extract_qualification(text: str) -> str | None:
    """Map extracted qualification text to a standard label."""
    cleaned = _clean_text(text)
    for hint, value in QUALIFICATION_HINTS.items():
        if hint in cleaned:
            return value
    return None


def extract_board(text: str) -> str | None:
    """Map extracted board text to a standard label."""
    cleaned = _clean_text(text)
    for hint, value in BOARD_HINTS.items():
        if hint in cleaned:
            return value
    return None


def extract_aggregate(text: str) -> float | None:
    """Find a percentage / aggregate value in text."""
    patterns = [
        r"aggregate[\s:]*(?:marks?)?[\s:]*(\d+(?:\.\d+)?)",
        r"percentage[\s:]*(\d+(?:\.\d+)?)",
        r"obtained[\s:]*(\d+(?:\.\d+)?)\s*%",
        r"(\d+(?:\.\d+)?)\s*%\s*(?:aggregate|overall|marks)",
        r"result[\s:]*(\d+(?:\.\d+)?)",
        r"\baggregate\b.*?\b(\d{2}(?:\.\d+)?)\b",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = float(m.group(1))
            if 0 <= val <= 100:
                return val
    return None


def extract_test_score(text: str) -> dict[str, str] | None:
    """Extract a test name and score/roll number if present."""
    test_patterns = [
        r"\b(?:nts|nat)\b\s*(?:ie)?\s*(?:ics)?",
        r"\bnust\s*entry\s*test\b",
        r"\bnet\b",
        r"\becat\b",
        r"\bsat\b",
        r"\blcat\b",
    ]
    found_test: str | None = None
    cleaned = _clean_text(text)
    for pat in test_patterns:
        m = re.search(pat, cleaned, re.IGNORECASE)
        if m:
            found_test = m.group(0).upper().strip()
            break

    if not found_test:
        return None

    score_patterns = [
        r"score[\s:]*(\d+(?:\.\d+)?)",
        r"marks[\s:]*(\d+(?:\.\d+)?)",
        r"roll\s*no\.?[\s:]*([\w\-]+)",
        r"percent(?:ile)?[\s:]*(\d+(?:\.\d+)?)",
    ]
    score_match = _find_first(score_patterns, text)
    score = score_match.group(1).strip() if score_match else ""
    return {"test": found_test, "score": score}


def extract_fields(filename: str, text: str, canonical_category: str | None) -> list[ExtractedField]:
    """Extract structured fields from document text.

    Confidence is left as None for rule-based extractions because a regex cannot
    produce a calibrated confidence score. The field is still present so future
    OCR/ML stages can populate it without changing the schema.
    """
    fields: list[ExtractedField] = []
    source = filename

    name = extract_name(text)
    if name:
        fields.append(
            ExtractedField(
                field="name",
                value=name,
                confidence=None,
                source_document=source,
                extraction_method="regex",
            )
        )

    qualification = extract_qualification(text)
    if qualification:
        fields.append(
            ExtractedField(
                field="qualification",
                value=qualification,
                confidence=None,
                source_document=source,
                extraction_method="regex",
            )
        )

    board = extract_board(text)
    if board:
        fields.append(
            ExtractedField(
                field="board",
                value=board,
                confidence=None,
                source_document=source,
                extraction_method="regex",
            )
        )

    aggregate = extract_aggregate(text)
    if aggregate is not None:
        fields.append(
            ExtractedField(
                field="aggregate",
                value=aggregate,
                confidence=None,
                source_document=source,
                extraction_method="regex",
            )
        )

    test_score = extract_test_score(text)
    if test_score:
        fields.append(
            ExtractedField(
                field="test_score",
                value=test_score,
                confidence=None,
                source_document=source,
                extraction_method="regex",
            )
        )

    return fields
