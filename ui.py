"""Shared Streamlit UI helpers."""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import streamlit as st

from backend.data_loader import load_universities
from backend.profile import default_profile, is_profile_complete


def init_session_state() -> None:
    defaults = {
        "student_profile": default_profile(),
        "parsed_docs": [],
        "selected_university_id": None,
        "selected_program_id": None,
        "eligibility_result": None,
        "selected_program_with_university": None,
        "chat_history": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_universities_data() -> dict[str, Any]:
    return load_universities()


def render_sidebar() -> None:
    with st.sidebar:
        st.title("EduPath AI")
        st.caption("Smart University Admission Assistant")
        st.divider()

        completed, total, ratio = progress_summary()

        st.markdown("**Progress**")
        st.progress(ratio)
        st.caption(f"{completed} of {total} steps completed")

        for label, done in progress_steps():
            icon = "✅" if done else "⬜"
            st.markdown(f"{icon} {label}")

        st.divider()
        st.markdown("[About](#)")


def verdict_color(verdict: str) -> str:
    if verdict.startswith("ELIGIBLE - Conditional"):
        return "#f0ad4e"
    if verdict == "ELIGIBLE":
        return "#5cb85c"
    return "#d9534f"


def verdict_card(result: dict[str, Any]) -> None:
    color = verdict_color(result["verdict"])
    st.markdown(
        f"""
        <div style="background-color:{color}; padding:1rem; border-radius:0.5rem; color:white; text-align:center;">
            <h3 style="margin:0;">{result['verdict']}</h3>
        </div>
        """,
        unsafe_allow_html=True,
    )


def missing_docs_card(missing: list[dict[str, Any]]) -> None:
    if not missing:
        st.success("All required documents are present.")
        return
    st.warning("Missing required documents")
    for doc in missing:
        st.markdown(f"- ❌ {doc['name']}")


def requirements_card(program: dict[str, Any]) -> None:
    req = program.get("requirements", {})
    st.markdown("**Requirements**")
    st.markdown(f"- Qualification: {', '.join(req.get('qualification', []))}")
    st.markdown(f"- Minimum aggregate: {req.get('minimum_aggregate')}%")
    if req.get("estimated_cutoff"):
        st.markdown(f"- Estimated cutoff: {req.get('estimated_cutoff')}%")
    st.markdown(f"- Admission test: {req.get('admission_test', 'N/A')}")
    st.markdown(f"- Deadline: {req.get('application_deadline', 'N/A')}")
