"""Upload category definitions for the category-based document upload system.

Maps the six user-facing upload slots to canonical document categories and
provides UI grouping/ordering metadata.
"""
from __future__ import annotations

from typing import Any

UPLOAD_CATEGORIES: dict[str, dict[str, Any]] = {
    "intermediate_transcript": {
        "label": "HSSC / Intermediate Transcript",
        "canonical_category": "intermediate_transcript",
        "allows_multiple": False,
        "group": "Academic",
    },
    "matric_certificate": {
        "label": "SSC / Matric Certificate",
        "canonical_category": "matric_certificate",
        "allows_multiple": False,
        "group": "Academic",
    },
    "entry_test_score": {
        "label": "Entry Test Score Card",
        "canonical_category": "entry_test_score",
        "allows_multiple": True,
        "group": "Admission Test",
    },
    "cnic_bform": {
        "label": "CNIC / B-Form",
        "canonical_category": "cnic_bform",
        "allows_multiple": False,
        "group": "Identity & Residence",
    },
    "domicile": {
        "label": "Domicile Certificate",
        "canonical_category": "domicile",
        "allows_multiple": False,
        "group": "Identity & Residence",
    },
    "other": {
        "label": "Other Documents",
        "canonical_category": "other",
        "allows_multiple": True,
        "group": "Other",
    },
}

CATEGORY_TO_CANONICAL: dict[str, str] = {
    key: val["canonical_category"] for key, val in UPLOAD_CATEGORIES.items()
}

CANONICAL_TO_UPLOAD: dict[str, str] = {
    val["canonical_category"]: key for key, val in UPLOAD_CATEGORIES.items()
}

MULTI_DOC_CATEGORIES: set[str] = {
    key for key, val in UPLOAD_CATEGORIES.items() if val["allows_multiple"]
}

UPLOAD_GROUPS: dict[str, list[str]] = {
    "Academic": ["intermediate_transcript", "matric_certificate"],
    "Admission Test": ["entry_test_score"],
    "Identity & Residence": ["cnic_bform", "domicile"],
    "Other": ["other"],
}

DISPLAY_ORDER: list[str] = [
    cat for group in UPLOAD_GROUPS.values() for cat in group
]
