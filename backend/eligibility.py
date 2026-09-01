"""Rule-based eligibility checking engine."""
from __future__ import annotations

import re
from datetime import date
from typing import Any


# ---------------------------------------------------------------------------
# Qualification taxonomy
# ---------------------------------------------------------------------------
# Each canonical qualification has a list of aliases. Aliases are lowercased
# and cleaned so they can be matched against normalized input text.
# Matching is done longest-alias-first to avoid partial mis-matches.
QUALIFICATION_ALIASES: dict[str, list[str]] = {
    "fsc_pre_engineering": [
        "fsc pre-engineering",
        "fsc pre engineering",
        "fsc engineering",
        "fsc eng",
        "fsc pre-eng",
        "pre-engineering",
        "pre engineering",
        "pre eng",
    ],
    "fsc_pre_medical": [
        "fsc pre-medical",
        "fsc pre medical",
        "fsc medical",
        "fsc med",
        "fsc pre-med",
        "pre-medical",
        "pre medical",
        "pre med",
    ],
    "ics": [
        "ics",
        "intermediate in computer science",
        "intermediate computer science",
        "fsc computer science",
        "fsc cs",
        "computer science",
    ],
    "a_levels": [
        "a-levels",
        "a levels",
        "a level",
        "alevels",
        "alevel",
        "gce a-levels",
        "gce a levels",
        "gce a level",
        "advanced levels",
    ],
    "fa": [
        "fa",
        "faculty of arts",
        "f.a",
        "f a",
    ],
    "dae": [
        "dae",
        "diploma of associate engineering",
        "diploma of associate engineer",
    ],
    "fsc": [
        "fsc",
        "hssc",
        "higher secondary school certificate",
        "faculty of science",
    ],
    "equivalent": [
        "equivalent",
        "equivalency certificate",
    ],
}

# Parent relationships: a more specific qualification can satisfy a requirement
# that accepts a broader parent category (e.g., FSc Pre-Engineering satisfies FSc).
QUALIFICATION_PARENTS: dict[str, str] = {
    "fsc_pre_engineering": "fsc",
    "fsc_pre_medical": "fsc",
}


# ---------------------------------------------------------------------------
# Document taxonomy
# ---------------------------------------------------------------------------
# Real document labels (from filenames, OCR, or manual entry) are mapped to a
# small set of canonical categories. Required document names from the JSON
# dataset are also mapped to the same categories.
DOCUMENT_ALIASES: dict[str, list[str]] = {
    "matric_certificate": [
        "matric certificate",
        "matriculation certificate",
        "ssc certificate",
        "matric marksheet",
        "ssc marksheet",
        "matric transcript",
        "ssc transcript",
    ],
    "intermediate_transcript": [
        "fsc transcript",
        "intermediate transcript",
        "hssc transcript",
        "fsc marksheet",
        "intermediate marksheet",
        "hssc marksheet",
        "fsc equivalence",
        "a levels equivalence",
        "a level equivalence",
        "alevel equivalence",
        "fsc a levels equivalence",
        "fsc intermediate marksheet",
        "fsc a levels transcript",
        "fsc intermediate",
        "intermediate fsc",
    ],
    "cnic_bform": [
        "cnic",
        "b form",
        "bform",
        "b-form",
        "national identity card",
        "identity card",
        "cnic b form",
    ],
    "entry_test_score": [
        "nts nat ie ics score card",
        "nts nat ie score card",
        "nts nat ics score card",
        "valid nts nat score card",
        "nts nat score card",
        "nts score card",
        "nat score card",
        "nust entry test result",
        "net result",
        "lcat score report",
        "sat score report",
        "ecat score card",
        "entry test score card",
        "entry test result",
        "admission test score",
    ],
    "domicile": [
        "domicile certificate",
        "domicile",
        "residence certificate",
        "provincial domicile",
    ],
    "photographs": [
        "passport size photographs",
        "passport size photograph",
        "passport size photo",
        "passport photographs",
        "passport photo",
        "photographs",
        "photograph",
        "photo",
    ],
    "statement_of_purpose": [
        "statement of purpose",
        "sop",
    ],
}


def _clean_text(text: str) -> str:
    """Normalize text for matching: lowercase, strip punctuation, collapse spaces."""
    if not text:
        return ""
    # Lowercase and replace punctuation with spaces so "a-levels" becomes "a levels".
    cleaned = re.sub(r"[^\w\s]+", " ", text.lower())
    # Collapse multiple spaces and trim.
    return " ".join(cleaned.split())


def _normalize_by_aliases(text: str, aliases: dict[str, list[str]]) -> str | None:
    """Return the canonical key for a text if any alias matches, else None.

    Aliases are matched longest-first to prefer more specific patterns.
    """
    cleaned = _clean_text(text)
    if not cleaned:
        return None

    # Build a flat list of (alias, canonical) and sort by alias length descending.
    flattened = [
        (alias, canonical)
        for canonical, alias_list in aliases.items()
        for alias in alias_list
    ]
    flattened.sort(key=lambda pair: len(pair[0]), reverse=True)

    for alias, canonical in flattened:
        if alias in cleaned:
            return canonical
    return None


def _normalize_qualification(text: str | None) -> str | None:
    """Map a qualification string to a canonical qualification type."""
    if not text:
        return None
    return _normalize_by_aliases(text, QUALIFICATION_ALIASES)


def _qualification_ancestors(canonical: str) -> list[str]:
    """Return the parent chain for a canonical qualification type."""
    ancestors: list[str] = []
    current = canonical
    while current in QUALIFICATION_PARENTS:
        parent = QUALIFICATION_PARENTS[current]
        ancestors.append(parent)
        current = parent
    return ancestors


def _qualification_matches(student_qual: str | None, accepted_quals: list[str]) -> bool:
    """Check if the student's qualification matches any accepted qualification.

    Both sides are normalized to canonical types before comparing, so
    "FSc Pre-Engineering" and "fsc engineering" match. A more specific
    subtype (e.g., FSc Pre-Engineering) also satisfies a generic parent
    requirement such as "FSc", but a bare "FSc" does not satisfy a
    specific Pre-Engineering requirement.
    """
    student_canonical = _normalize_qualification(student_qual)
    if not student_canonical:
        return False

    accepted_canonical = {
        q for q in (_normalize_qualification(aq) for aq in accepted_quals) if q
    }
    if student_canonical in accepted_canonical:
        return True

    return any(ancestor in accepted_canonical for ancestor in _qualification_ancestors(student_canonical))


def _normalize_document(text: str | None) -> str | None:
    """Map a document label to a canonical document category."""
    if not text:
        return None
    return _normalize_by_aliases(text, DOCUMENT_ALIASES)


def _student_document_categories(student_docs: list[str]) -> set[str]:
    """Return the set of canonical document categories present in the profile."""
    categories: set[str] = set()
    for doc in student_docs:
        canonical = _normalize_document(doc)
        if canonical:
            categories.add(canonical)
    return categories


def _required_document_found(
    required_doc: dict[str, Any], student_categories: set[str]
) -> bool:
    """Check whether a required document category is satisfied.

    The required document name (from JSON) is normalized to a canonical
    category, then we check if that category exists among the student's
    uploaded/verified document categories.

    If a required document name cannot be mapped to a known category, we
    treat it as not found. This is safer than guessing via substring matching.
    """
    required_category = _normalize_document(required_doc.get("name", ""))
    if not required_category:
        return False
    return required_category in student_categories


def _parse_deadline(deadline_str: str | None) -> date | None:
    if not deadline_str:
        return None
    try:
        return date.fromisoformat(deadline_str)
    except ValueError:
        return None


def check_eligibility(
    profile: dict[str, Any],
    program: dict[str, Any],
    today: date | None = None,
) -> dict[str, Any]:
    """Evaluate a student profile against a program's requirements.

    Returns a result dict with verdict, reasons, missing documents, and deadlines.
    """
    if today is None:
        today = date.today()

    req = program.get("requirements", {})
    accepted_quals = req.get("qualification", [])
    min_aggregate = req.get("minimum_aggregate", 0.0)
    estimated_cutoff = req.get("estimated_cutoff")
    admission_test = req.get("admission_test")
    required_documents = req.get("required_documents", [])
    deadline_str = req.get("application_deadline")

    student_aggregate = profile.get("aggregate")
    student_qual = profile.get("qualification")
    student_docs = [d for d in profile.get("documents", []) if isinstance(d, str)]
    student_test_scores = profile.get("test_scores", {})

    reasons: list[str] = []
    missing_docs: list[dict[str, Any]] = []
    conditional = False
    eligible = True

    # Qualification check (normalized)
    qual_ok = _qualification_matches(student_qual, accepted_quals)
    if not qual_ok:
        eligible = False
        reasons.append(
            f"Qualification mismatch: '{student_qual}' is not among accepted qualifications "
            f"({', '.join(accepted_quals)})."
        )
    else:
        reasons.append(f"Qualification '{student_qual}' is accepted.")

    # Aggregate check
    if student_aggregate is None:
        eligible = False
        reasons.append("Aggregate percentage is missing from the profile.")
    elif student_aggregate < min_aggregate:
        eligible = False
        reasons.append(
            f"Aggregate {student_aggregate}% is below the minimum requirement of {min_aggregate}%."
        )
    else:
        reasons.append(f"Aggregate {student_aggregate}% meets the minimum requirement of {min_aggregate}%.")
        if estimated_cutoff and student_aggregate < estimated_cutoff:
            conditional = True
            reasons.append(
                f"Your aggregate is below the estimated cutoff ({estimated_cutoff}%). "
                "Admission may be competitive."
            )

    # Required documents check (normalized categories)
    student_doc_categories = _student_document_categories(student_docs)
    for doc in required_documents:
        doc_name = doc["name"]
        # Only mandatory documents can make a student conditionally eligible.
        if not doc.get("required", False):
            continue

        found = _required_document_found(doc, student_doc_categories)
        if found:
            reasons.append(f"Required document found: {doc_name}.")
        else:
            missing_docs.append(doc)
            conditional = True

    # Admission test check
    test_missing = admission_test and admission_test not in student_test_scores
    if test_missing:
        conditional = True
        reasons.append(
            f"A valid {admission_test} score has not been added to your profile yet."
        )
    elif admission_test:
        reasons.append(f"{admission_test} score is present.")

    # Deadline check
    deadline = _parse_deadline(deadline_str)
    days_remaining = None
    if deadline:
        days_remaining = (deadline - today).days
        if days_remaining < 0:
            eligible = False
            reasons.append(f"Application deadline ({deadline}) has passed.")
        else:
            reasons.append(f"Application deadline is {deadline} ({days_remaining} days remaining).")

    # Final verdict
    if not eligible:
        verdict = "NOT ELIGIBLE"
    elif conditional:
        verdict = "ELIGIBLE - Conditional"
    else:
        verdict = "ELIGIBLE"

    return {
        "verdict": verdict,
        "eligible": eligible,
        "conditional": conditional,
        "reasons": reasons,
        "missing_documents": missing_docs,
        "admission_test": admission_test,
        "test_missing": test_missing,
        "application_deadline": deadline_str,
        "days_remaining": days_remaining,
        "estimated_cutoff": estimated_cutoff,
        "minimum_aggregate": min_aggregate,
    }
