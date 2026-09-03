"""Centralised Streamlit session-state helpers.

Pages route profile writes, selection changes, eligibility refreshes, and
reset flows through this module so the application behaves like one
connected assistant rather than a set of independent pages.

The eligibility engine (`backend.eligibility.check_eligibility`) remains the
source of truth for verdicts. This module only decides *when* to recompute
and how to surface the result to the UI.

Architecture:
    OCR ──► Profile (merge_profile) ──► state.update_profile()
                                              │
                                    invalidates eligibility if fingerprint changed
                                              │
                            ┌─────────────────┴─────────────────┐
                            ▼                                   ▼
                    check_eligibility()                     build_checklist()
                    (rule-based engine)                     build_next_actions()
                            │                                   │
                            └─────────────┬─────────────────────┘
                                          ▼
                                       UI pages
"""
from __future__ import annotations

from typing import Any

import streamlit as st

from backend.data_loader import get_program, get_university, load_universities
from backend.eligibility import check_eligibility
from backend.profile import (
    default_profile,
    effective_aggregate,
    merge_profile,
    profile_fingerprint,
)


# ---------------------------------------------------------------------------
# Session initialization
# ---------------------------------------------------------------------------


def session_defaults() -> dict[str, Any]:
    """Return fresh defaults for all canonical application state."""
    return {
        "student_profile": default_profile(),
        "parsed_docs": [],
        "selected_university_id": None,
        "selected_program_id": None,
        "eligibility_result": None,
        "selected_program_with_university": None,
        "chat_history": [],
        "chat_history_sources": [],
    }


def init_session_state() -> None:
    """Seed any missing canonical application state keys."""
    for key, value in session_defaults().items():
        st.session_state.setdefault(key, value)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


def get_profile() -> dict[str, Any]:
    """Return the canonical student profile from session state."""
    init_session_state()
    return st.session_state["student_profile"]


def update_profile(
    updates: dict[str, Any],
    source: str = "manual",
) -> dict[str, Any]:
    """Merge ``updates`` into the profile and invalidate eligibility if needed.

    ``source`` is either ``"manual"`` or ``"ocr"``. Manual updates always
    override OCR values (see :func:`backend.profile.merge_profile`).

    If the eligibility-relevant fingerprint changes, the cached eligibility
    result is cleared so the next page that needs it will recompute.
    """
    profile = get_profile()
    previous_fp = profile_fingerprint(profile)

    new_profile = merge_profile(profile, updates, source=source)
    _sync_aggregate(new_profile)
    st.session_state["student_profile"] = new_profile

    if profile_fingerprint(new_profile) != previous_fp:
        invalidate_eligibility()

    return new_profile


def add_manual_document(document_type: str) -> dict[str, Any]:
    """Add a manually confirmed document and invalidate eligibility if needed."""
    document_type = document_type.strip()
    if not document_type:
        return get_profile()
    return update_profile({"documents": [document_type]}, source="manual")


def add_manual_test_score(test_name: str, score: float | str) -> dict[str, Any]:
    """Add a manually confirmed admission-test score through canonical state."""
    test_name = test_name.strip()
    if not test_name:
        return get_profile()
    return update_profile({"test_scores": {test_name: score}}, source="manual")


def _sync_aggregate(profile: dict[str, Any]) -> None:
    """Keep the legacy ``aggregate`` field aligned with HSSC/SSC inputs.

    The eligibility engine reads ``profile["aggregate"]``. When OCR (or a
    manual edit) supplies an HSSC percentage, we mirror it into aggregate
    so downstream logic does not have to know about the split.
    """
    agg = effective_aggregate(profile)
    if agg is not None:
        profile["aggregate"] = agg


def invalidate_eligibility() -> None:
    """Clear the cached eligibility result so it will recompute on next read."""
    st.session_state["eligibility_result"] = None


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


def set_selection(university_id: str, program_id: str) -> None:
    """Record the chosen university/program and mirror it into the profile.

    Writing into ``profile.target_university`` / ``target_program`` keeps the
    canonical profile self-describing, so the AI advisor and action plan can
    read the target from a single place.
    """
    st.session_state["selected_university_id"] = university_id
    st.session_state["selected_program_id"] = program_id

    data = load_universities()
    uni = get_university(data, university_id)
    prog = get_program(uni, program_id) if uni else None

    profile = get_profile()
    profile["target_university"] = uni["name"] if uni else None
    profile["target_program"] = prog["name"] if prog else None

    # Cache a joined view for pages that need program + university name.
    if prog and uni:
        st.session_state["selected_program_with_university"] = {
            **prog,
            "university_name": uni["name"],
            "university_id": uni["id"],
        }
    else:
        st.session_state["selected_program_with_university"] = None

    invalidate_eligibility()


def get_selection() -> tuple[Any, Any, Any, Any]:
    """Return (university, program, prog_display, result_or_None).

    Any of the returned values may be ``None`` when selection or data is
    incomplete — callers should branch on that.
    """
    uni_id = st.session_state.get("selected_university_id")
    prog_id = st.session_state.get("selected_program_id")
    if not uni_id or not prog_id:
        return None, None, None, None

    data = load_universities()
    uni = get_university(data, uni_id)
    prog = get_program(uni, prog_id) if uni else None
    prog_display = {**prog, "university_name": uni["name"]} if (uni and prog) else None
    result = st.session_state.get("eligibility_result")
    return uni, prog, prog_display, result


# ---------------------------------------------------------------------------
# Eligibility
# ---------------------------------------------------------------------------


def recalculate_eligibility() -> dict[str, Any] | None:
    """Recompute eligibility from the current profile + selection.

    Returns the result dict (also stored on session state) or ``None`` when
    no program has been selected.
    """
    uni, prog, prog_display, _ = get_selection()
    if prog is None:
        return None
    profile = get_profile()
    result = check_eligibility(profile, prog)
    st.session_state["eligibility_result"] = result
    return result


def ensure_eligibility() -> dict[str, Any] | None:
    """Return the current result, recomputing lazily if missing."""
    result = st.session_state.get("eligibility_result")
    if result is None:
        result = recalculate_eligibility()
    return result


# ---------------------------------------------------------------------------
# Checklist & next actions
# ---------------------------------------------------------------------------


def build_checklist() -> list[dict[str, Any]]:
    """Build a dynamic checklist driven by program requirements + profile state.

    Each item is ``{"key", "label", "done", "category"}``. Categories are
    ``"document"``, ``"test"``, ``"profile"``, ``"selection"`` so the UI can
    group them visually if desired.
    """
    items: list[dict[str, Any]] = []
    profile = get_profile()

    # Profile completeness
    items.append({
        "key": "profile_qualification",
        "label": "Qualification recorded",
        "done": bool(profile.get("qualification")),
        "category": "profile",
    })
    items.append({
        "key": "profile_aggregate",
        "label": "Aggregate / HSSC percentage recorded",
        "done": effective_aggregate(profile) is not None,
        "category": "profile",
    })

    uni, prog, _, result = get_selection()
    if prog is None:
        items.append({
            "key": "selection",
            "label": "University and program selected",
            "done": False,
            "category": "selection",
        })
        return items

    items.append({
        "key": "selection",
        "label": "University and program selected",
        "done": True,
        "category": "selection",
    })

    # Required documents — use the same taxonomy-aware check as the engine.
    from backend.eligibility import (
        _normalize_document,
        _student_document_categories,
    )

    student_cats = _student_document_categories(
        [d for d in profile.get("documents", []) if isinstance(d, str)]
    )
    for doc in prog.get("requirements", {}).get("required_documents", []):
        name = doc.get("name", "")
        category = _normalize_document(name)
        done = bool(category and category in student_cats)
        items.append({
            "key": f"doc_{category or name}",
            "label": name,
            "done": done,
            "category": "document",
            "required": bool(doc.get("required", False)),
        })

    # Admission test
    test_name = (result or {}).get("admission_test") or prog.get("requirements", {}).get("admission_test")
    if test_name:
        test_done = test_name in (profile.get("test_scores") or {})
        items.append({
            "key": f"test_{test_name}",
            "label": f"{test_name} score recorded",
            "done": test_done,
            "category": "test",
        })

    return items


def build_next_actions() -> list[dict[str, Any]]:
    """Return the prioritized list of next actions for the student.

    Actions are derived from real state — missing profile fields, missing
    documents, missing test scores, and the eligibility verdict. Nothing is
    fabricated: if a deadline or fee is not present in the dataset it is
    reported as "not on file" rather than guessed.
    """
    actions: list[dict[str, Any]] = []
    profile = get_profile()

    if not profile.get("qualification"):
        actions.append({
            "priority": 1,
            "title": "Record your qualification",
            "description": "Add your intermediate qualification (FSc/ICS/A-Levels/FA) on the Profile page.",
            "target": "pages/2_Profile.py",
        })
    if effective_aggregate(profile) is None:
        actions.append({
            "priority": 2,
            "title": "Record your aggregate / HSSC percentage",
            "description": "The eligibility engine needs a numeric aggregate to evaluate you.",
            "target": "pages/2_Profile.py",
        })

    uni, prog, prog_display, result = get_selection()
    if prog is None:
        actions.append({
            "priority": 3,
            "title": "Choose a university and program",
            "description": "Select the program you want to apply to.",
            "target": "pages/3_Select_Program.py",
        })
        return actions

    if result is None:
        result = recalculate_eligibility() or {}

    missing = result.get("missing_documents") or []
    for doc in missing:
        actions.append({
            "priority": 4,
            "title": f"Upload {doc.get('name', 'required document')}",
            "description": "This required document is still missing from your profile.",
            "target": "pages/1_Upload_Documents.py",
        })

    if result.get("test_missing"):
        test_name = result.get("admission_test") or "the required admission test"
        actions.append({
            "priority": 5,
            "title": f"Register for {test_name}",
            "description": "Add your official score to the Profile once you have it.",
            "target": "pages/2_Profile.py",
        })

    verdict = result.get("verdict")
    if verdict == "NOT ELIGIBLE":
        actions.append({
            "priority": 6,
            "title": "Review eligibility gaps",
            "description": "See exactly what disqualifies you and what alternatives exist.",
            "target": "pages/4_Eligibility_Check.py",
        })
    elif verdict == "ELIGIBLE - Conditional":
        actions.append({
            "priority": 6,
            "title": "Complete conditional items",
            "description": "You are conditionally eligible — finish the open items before applying.",
            "target": "pages/4_Eligibility_Check.py",
        })
    else:
        actions.append({
            "priority": 6,
            "title": "Submit your application",
            "description": "You appear eligible. Complete the university's application before the deadline.",
            "target": "pages/6_Action_Plan.py",
        })

    return actions


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------


def reset_application() -> None:
    """Wipe application and temporary upload state before starting fresh."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state.update(session_defaults())
