"""Conflict-aware merging of extracted documents into a student profile."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from backend.documents.models import Conflict, ExtractedDocument, MergeProposal


# Canonical categories that contain academic aggregate information.
# When picking an aggregate, we only trust categories that represent the
# student's latest secondary/intermediate result.
ACADEMIC_CATEGORIES = {
    "intermediate_transcript",
    "matric_certificate",
}


def _unique_values(values: list[Any]) -> list[Any]:
    """Return unique values preserving order."""
    seen: set[Any] = set()
    result: list[Any] = []
    for v in values:
        # Dictionaries are not hashable; use their string representation.
        key = tuple(sorted(v.items())) if isinstance(v, dict) else v
        if key not in seen:
            seen.add(key)
            result.append(v)
    return result


def _detect_conflicts(docs: list[ExtractedDocument]) -> list[Conflict]:
    """Detect fields where documents disagree."""
    field_values: dict[str, list[tuple[Any, str]]] = defaultdict(list)
    for doc in docs:
        for f in doc.fields:
            if f.value is not None:
                field_values[f.field].append((f.value, doc.filename))

    conflicts: list[Conflict] = []
    for field_name, entries in field_values.items():
        if len(entries) < 2:
            continue
        values = [v for v, _ in entries]
        unique = _unique_values(values)
        if len(unique) > 1:
            conflicts.append(
                Conflict(
                    field=field_name,
                    values=unique,
                    source_documents=[src for _, src in entries],
                )
            )
    return conflicts


def _pick_name(docs: list[ExtractedDocument]) -> str | None:
    """Prefer names from the most reliable identity and academic documents."""
    for preferred in ["intermediate_transcript", "matric_certificate", "cnic_bform"]:
        for doc in docs:
            if doc.canonical_category == preferred:
                name = doc.field_value("name")
                if name:
                    return name
    for doc in docs:
        name = doc.field_value("name")
        if name:
            return name
    return None


def _pick_qualification(docs: list[ExtractedDocument]) -> str | None:
    """Prefer intermediate-level qualification over matric/equivalent."""
    order = ["intermediate_transcript"]
    for preferred in order:
        for doc in docs:
            if doc.canonical_category == preferred:
                q = doc.field_value("qualification")
                if q:
                    return q
    for doc in docs:
        q = doc.field_value("qualification")
        if q:
            return q
    return None


def _pick_board(docs: list[ExtractedDocument]) -> str | None:
    """Use the board from the most academically-relevant document."""
    for preferred in ["intermediate_transcript", "matric_certificate"]:
        for doc in docs:
            if doc.canonical_category == preferred:
                b = doc.field_value("board")
                if b:
                    return b
    for doc in docs:
        b = doc.field_value("board")
        if b:
            return b
    return None


def _pick_father_name(docs: list[ExtractedDocument]) -> str | None:
    """Pick father's name from the most reliable identity/academic document."""
    for preferred in ["intermediate_transcript", "matric_certificate", "cnic_bform"]:
        for doc in docs:
            if doc.canonical_category == preferred:
                val = doc.field_value("father_name")
                if val:
                    return val
    for doc in docs:
        val = doc.field_value("father_name")
        if val:
            return val
    return None


def _pick_roll_number(docs: list[ExtractedDocument]) -> str | None:
    """Pick roll number from the most academically-relevant document."""
    for preferred in ["intermediate_transcript", "matric_certificate"]:
        for doc in docs:
            if doc.canonical_category == preferred:
                val = doc.field_value("roll_number")
                if val:
                    return str(val)
    for doc in docs:
        val = doc.field_value("roll_number")
        if val:
            return str(val)
    return None


def _pick_hssc_group(docs: list[ExtractedDocument]) -> str | None:
    """Pick HSSC group from the intermediate transcript."""
    for doc in docs:
        if doc.canonical_category == "intermediate_transcript":
            val = doc.field_value("hssc_group")
            if val:
                return val
    for doc in docs:
        val = doc.field_value("hssc_group")
        if val:
            return val
    return None


def _pick_total_marks(docs: list[ExtractedDocument]) -> int | None:
    """Pick total marks from the most academically-relevant document."""
    for preferred in ["intermediate_transcript", "matric_certificate"]:
        for doc in docs:
            if doc.canonical_category == preferred:
                val = doc.field_value("total_marks")
                if isinstance(val, (int, float)):
                    return int(val)
    for doc in docs:
        val = doc.field_value("total_marks")
        if isinstance(val, (int, float)):
            return int(val)
    return None


def _pick_obtained_marks(docs: list[ExtractedDocument]) -> int | None:
    """Pick obtained marks from the most academically-relevant document."""
    for preferred in ["intermediate_transcript", "matric_certificate"]:
        for doc in docs:
            if doc.canonical_category == preferred:
                val = doc.field_value("obtained_marks")
                if isinstance(val, (int, float)):
                    return int(val)
    for doc in docs:
        val = doc.field_value("obtained_marks")
        if isinstance(val, (int, float)):
            return int(val)
    return None


def _pick_aggregate(docs: list[ExtractedDocument], warnings: list[str]) -> float | None:
    """Pick the aggregate from the latest academic document.

    We avoid taking the max across all aggregates because a Matric percentage
    should not silently overwrite an FSc aggregate. Falls back to any document
    with an aggregate value when no properly-classified academic document has
    one, to handle misclassified marksheets.
    """
    aggregates: list[tuple[float, str, str | None]] = []
    for doc in docs:
        if doc.canonical_category in ACADEMIC_CATEGORIES:
            val = doc.field_value("aggregate")
            if isinstance(val, (int, float)):
                aggregates.append((float(val), doc.filename, doc.canonical_category))

    if not aggregates:
        # Fallback: check any document for an aggregate value (handles misclassified docs).
        for doc in docs:
            val = doc.field_value("aggregate")
            if isinstance(val, (int, float)):
                aggregates.append((float(val), doc.filename, doc.canonical_category))

    if not aggregates:
        return None

    # Prefer intermediate_transcript aggregate; if absent, fall back to matric.
    intermediate = [a for a in aggregates if a[2] == "intermediate_transcript"]
    if intermediate:
        chosen = max(intermediate, key=lambda x: x[0])
        return chosen[0]

    matric = [a for a in aggregates if a[2] == "matric_certificate"]
    if matric:
        chosen = max(matric, key=lambda x: x[0])
        return chosen[0]

    return max(aggregates, key=lambda x: x[0])[0]


def _pick_split_percentages(docs: list[ExtractedDocument]) -> dict[str, float | None]:
    """Pull HSSC/SSC split percentages from the academically-relevant documents.

    Returns ``{"hssc_percentage": ..., "ssc_percentage": ...}`` with either
    value possibly ``None``. Falls back to any document with these fields when
    no properly-classified academic document has them, to handle misclassified
    marksheets.
    """
    hssc: float | None = None
    ssc: float | None = None

    for doc in docs:
        if doc.canonical_category == "intermediate_transcript" and hssc is None:
            val = doc.field_value("hssc_percentage")
            if isinstance(val, (int, float)):
                hssc = float(val)
        elif doc.canonical_category == "matric_certificate" and ssc is None:
            val = doc.field_value("ssc_percentage")
            if isinstance(val, (int, float)):
                ssc = float(val)

    # Fallback: check any document for split percentages (handles misclassified docs).
    if hssc is None:
        for doc in docs:
            val = doc.field_value("hssc_percentage")
            if isinstance(val, (int, float)):
                hssc = float(val)
                break
    if ssc is None:
        for doc in docs:
            val = doc.field_value("ssc_percentage")
            if isinstance(val, (int, float)):
                ssc = float(val)
                break

    return {"hssc_percentage": hssc, "ssc_percentage": ssc}


def merge_documents(docs: list[ExtractedDocument]) -> MergeProposal:
    """Merge documents into a proposed student profile, detecting conflicts."""
    warnings: list[str] = []
    conflicts = _detect_conflicts(docs)

    # Build a conflict-aware warning for the user.
    for conflict in conflicts:
        warnings.append(
            f"Conflicting {conflict.field} values found: "
            f"{', '.join(str(v) for v in conflict.values)}. "
            "Please review on the Profile page."
        )

    documents: list[str] = []
    for doc in docs:
        label = doc.document_type
        has_fields = bool(doc.fields)
        if (doc.validation.valid or has_fields) and doc.canonical_category and label not in documents:
            documents.append(label)

    # Collect test scores extracted from score-card documents. Keyed by the
    # normalised test name so merge_profile can merge them without dropping
    # previously-recorded scores.
    test_scores: dict[str, str] = {}
    for doc in docs:
        ts = doc.field_value("test_score")
        if isinstance(ts, dict) and ts.get("test"):
            test_scores[ts["test"]] = ts.get("score", "")

    profile: dict[str, Any] = {
        "name": _pick_name(docs) or "",
        "father_name": _pick_father_name(docs),
        "qualification": _pick_qualification(docs),
        "board": _pick_board(docs),
        "aggregate": _pick_aggregate(docs, warnings),
        "total_marks": _pick_total_marks(docs),
        "obtained_marks": _pick_obtained_marks(docs),
        "roll_number": _pick_roll_number(docs),
        "hssc_group": _pick_hssc_group(docs),
        **_pick_split_percentages(docs),
        "documents": documents,
        "test_scores": test_scores,
    }

    # Surface a warning if no academic aggregate could be extracted.
    if profile["aggregate"] is None and any(doc.field_value("aggregate") is not None for doc in docs):
        warnings.append(
            "Aggregate values were found but none were from a recognized academic transcript. "
            "Please verify your aggregate on the Profile page."
        )

    return MergeProposal(
        profile=profile,
        documents=documents,
        conflicts=conflicts,
        warnings=warnings,
    )
