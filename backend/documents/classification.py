"""Document classification using filename and content hints."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


# Human-readable labels by canonical category.
DOCUMENT_LABELS: dict[str, str] = {
    "matric_certificate": "Matriculation Certificate",
    "intermediate_transcript": "Academic Transcript (FSc/Intermediate)",
    "cnic_bform": "CNIC / B-Form",
    "entry_test_score": "Entry Test Score Card",
    "domicile": "Domicile Certificate",
    "photographs": "Photograph",
    "statement_of_purpose": "Statement of Purpose",
}

# Filename hints grouped by canonical category.
FILENAME_HINTS: dict[str, list[str]] = {
    "matric_certificate": [
        "matric",
        "ssc",
        "metric",
        "matriculation",
        "10th",
    ],
    "intermediate_transcript": [
        "fsc",
        "inter",
        "hssc",
        "intermediate",
        "ics",
        "alevel",
        "a level",
        "a-level",
        "12th",
        "equivalence",
    ],
    "cnic_bform": [
        "cnic",
        "bform",
        "b-form",
        "b form",
        "identity",
        "national identity",
    ],
    "entry_test_score": [
        "nts",
        "nat",
        "entry test",
        "test result",
        "net",
        "ecat",
        "sat",
        "lcat",
        "act",
        "muet",
        "nts-nat",
        "fast",
        "admission test",
    ],
    "domicile": [
        "domicile",
        "residence",
    ],
    "photographs": [
        "photo",
        "picture",
        "image",
        "pic",
        "passport size",
    ],
    "statement_of_purpose": [
        "sop",
        "statement of purpose",
        "purpose statement",
    ],
}

# Content hints (keywords/phrases) grouped by canonical category.
CONTENT_HINTS: dict[str, list[str]] = {
    "matric_certificate": [
        "secondary school certificate",
        "ssc",
        "matriculation",
        "matric",
        "10th class",
        "grade 10",
        "board of secondary",
        "marks obtained",
    ],
    "intermediate_transcript": [
        "higher secondary school certificate",
        "hssc",
        "intermediate",
        "fsc",
        "ics",
        "a levels",
        "a level",
        "alevel",
        "gce",
        "grade 12",
        "board of intermediate",
        "marks obtained",
        "total marks",
        "candidate",
    ],
    "cnic_bform": [
        "national identity card",
        "cnic",
        "b-form",
        "b form",
        "identity number",
        "nadra",
    ],
    "entry_test_score": [
        "nts",
        "nat",
        "entry test",
        "net result",
        "ecat",
        "sat",
        "lcat",
        "act",
        "muet",
        "nts-nat",
        "admission test",
        "test score",
        "roll number",
    ],
    "domicile": [
        "domicile certificate",
        "domicile",
        "residence certificate",
        "provincial domicile",
    ],
    "photographs": [
        "passport size photograph",
        "photograph",
        "photo",
    ],
    "statement_of_purpose": [
        "statement of purpose",
        "sop",
        "motivation letter",
    ],
}


def _clean_text(text: str) -> str:
    """Normalize text for matching: lowercase, collapse spaces, keep letters/numbers."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^\w\s]|_", " ", text)
    return " ".join(text.split())


def _score_hints(text: str, hints: dict[str, list[str]]) -> dict[str, int]:
    """Return a score per category based on hint matches in text."""
    cleaned = _clean_text(text)
    scores: dict[str, int] = {}
    for category, keywords in hints.items():
        score = 0
        for keyword in keywords:
            keyword_clean = _clean_text(keyword)
            if re.search(rf"\b{re.escape(keyword_clean)}\b", cleaned):
                # Longer matches are weighted more heavily.
                score += len(keyword_clean.split()) + 1
        scores[category] = score
    return scores


def classify_document(filename: str, content: str = "") -> dict[str, Any]:
    """Classify a document using filename hints first, then content hints.

    Filename-based classification takes precedence when the filename contains
    informative hints (e.g. "fsc_transcript.pdf"). When the filename is generic
    (e.g. "scan_001.pdf", "image.png"), content-based classification is used
    instead, looking for marksheet indicators like "board of intermediate",
    "marks obtained", "candidate", etc.
    """
    name_lower = Path(filename).name.lower()

    filename_scores = _score_hints(name_lower, FILENAME_HINTS)
    best_filename = max(filename_scores, key=filename_scores.get, default=None)
    if best_filename and filename_scores[best_filename] > 0:
        return {
            "canonical_category": best_filename,
            "document_type": DOCUMENT_LABELS[best_filename],
            "method": "filename",
        }

    if content:
        content_scores = _score_hints(content, CONTENT_HINTS)
        best_content = max(content_scores, key=content_scores.get, default=None)
        if best_content and content_scores[best_content] > 0:
            return {
                "canonical_category": best_content,
                "document_type": DOCUMENT_LABELS[best_content],
                "method": "content",
            }

    return {
        "canonical_category": None,
        "document_type": "Supporting Document",
        "method": "unknown",
    }
