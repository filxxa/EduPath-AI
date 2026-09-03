"""Student profile management.

The canonical profile is the single source of truth for student information
across all pages. Field provenance (ocr/manual/missing) is tracked in a
parallel ``field_sources`` map so that OCR results never silently overwrite
values a student has manually corrected.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


# Fields whose change should trigger an eligibility recomputation.
ELIGIBILITY_FIELDS: tuple[str, ...] = (
    "qualification",
    "board",
    "aggregate",
    "hssc_percentage",
    "ssc_percentage",
    "hssc_group",
    "documents",
    "test_scores",
)


# Default empty profile. ``aggregate`` remains the canonical number consumed by
# the eligibility engine; HSSC/SSC split is preserved alongside it so OCR
# output does not lose fidelity.
def default_profile() -> dict[str, Any]:
    return {
        "name": "",
        "qualification": None,
        "board": None,
        "aggregate": None,
        "ssc_percentage": None,
        "hssc_percentage": None,
        "hssc_group": None,
        "roll_number": None,
        "subjects": [],
        "target_university": None,
        "target_program": None,
        "documents": [],
        "test_scores": {},
        "notes": "",
        "field_sources": {},
    }


def is_profile_complete(profile: dict[str, Any]) -> bool:
    return bool(
        profile.get("qualification")
        and (
            profile.get("hssc_percentage") is not None
            or profile.get("aggregate") is not None
        )
    )


def effective_aggregate(profile: dict[str, Any]) -> float | None:
    """Return the aggregate number eligibility should evaluate against.

    Prefers HSSC percentage when present (most universities key off the
    intermediate result); falls back to the legacy aggregate field.
    """
    hssc = profile.get("hssc_percentage")
    if isinstance(hssc, (int, float)):
        return float(hssc)
    agg = profile.get("aggregate")
    if isinstance(agg, (int, float)):
        return float(agg)
    return None


def profile_fingerprint(profile: dict[str, Any]) -> str:
    """Stable hash of eligibility-relevant fields for cheap change detection."""
    payload = {k: profile.get(k) for k in ELIGIBILITY_FIELDS}
    payload["__effective__"] = effective_aggregate(profile)
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


# --- merge ---------------------------------------------------------------


def _source_priority(source: str) -> int:
    return {"ocr": 1, "manual": 2}.get(source, 0)


def merge_profile(
    profile: dict[str, Any],
    updates: dict[str, Any],
    source: str = "manual",
) -> dict[str, Any]:
    """Merge ``updates`` into ``profile`` preserving provenance.

    * Manual updates always win over OCR.
    * OCR updates only overwrite fields whose current source is not manual.
    * Documents are accumulated (not replaced) preserving insertion order.
    * ``test_scores`` dicts are merged key-wise respecting the same source rule.
    """
    new_profile = dict(profile)
    sources = dict(new_profile.get("field_sources") or {})

    docs_existing = list(new_profile.get("documents") or [])
    docs_incoming = updates.get("documents")
    if isinstance(docs_incoming, list):
        seen = set(docs_existing)
        for d in docs_incoming:
            if d and d not in seen:
                docs_existing.append(d)
                seen.add(d)
        new_profile["documents"] = docs_existing

    test_existing = dict(new_profile.get("test_scores") or {})
    test_incoming = updates.get("test_scores")
    if isinstance(test_incoming, dict):
        for name, value in test_incoming.items():
            prev_source = sources.get(f"test_scores.{name}")
            if source == "manual" or prev_source != "manual":
                test_existing[name] = value
                sources[f"test_scores.{name}"] = source
        new_profile["test_scores"] = test_existing

    skip = {"documents", "test_scores", "field_sources"}
    for key, value in updates.items():
        if key in skip:
            continue
        prev_source = sources.get(key)
        if source == "manual" or prev_source != "manual":
            new_profile[key] = value
            sources[key] = source

    new_profile["field_sources"] = sources
    return new_profile


# --- single-field helpers ------------------------------------------------


def set_field_source(profile: dict[str, Any], field: str, source: str) -> dict[str, Any]:
    sources = dict(profile.get("field_sources") or {})
    sources[field] = source
    profile["field_sources"] = sources
    return profile


def add_document(
    profile: dict[str, Any],
    doc_type: str,
    source: str = "manual",
) -> dict[str, Any]:
    docs = list(profile.get("documents") or [])
    if doc_type and doc_type not in docs:
        docs.append(doc_type)
    profile["documents"] = docs
    set_field_source(profile, "documents", source)
    return profile


def add_test_score(
    profile: dict[str, Any],
    test_name: str,
    score: float | str,
    source: str = "manual",
) -> dict[str, Any]:
    scores = dict(profile.get("test_scores") or {})
    scores[test_name] = score
    profile["test_scores"] = scores
    set_field_source(profile, f"test_scores.{test_name}", source)
    return profile
