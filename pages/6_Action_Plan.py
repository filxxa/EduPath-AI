"""Personalized action plan dashboard — driven by application state."""
from __future__ import annotations

from typing import Any

import streamlit as st

from backend.state import build_checklist, build_next_actions, get_profile, get_selection
from ui import init_session_state, inject_theme, nav_row, page_header, render_sidebar

st.set_page_config(page_title="Action Plan | EduPath AI", page_icon="🚀", layout="wide")
init_session_state()
inject_theme()
render_sidebar()

profile = get_profile()
name = profile.get("name") or "Student"

page_header(
    f"Welcome back, {name}!",
    "Your Admission Hub — track your progress and next steps.",
    "🚀",
)

uni, prog, prog_display, result = get_selection()

if prog is None or uni is None:
    with st.container(border=True):
        st.warning("You have not selected a program yet.")
        if st.button("Start Application", type="primary", key="start_app_empty"):
            st.switch_page("pages/1_Upload_Documents.py")
    st.stop()

checklist = build_checklist()
next_actions = build_next_actions()

# Progress bar from checklist.
done = sum(1 for item in checklist if item["done"])
total = len(checklist)
with st.container(border=True):
    st.markdown(f"### Your Path to {prog['name']}")
    progress_value = done / total if total else 0.0
    st.progress(progress_value, text=f"{done} of {total} items complete")

# Checklist — grouped by category.
CATEGORY_LABELS = {
    "profile": "👤 Profile",
    "selection": "🎯 Selection",
    "document": "📎 Documents",
    "test": "📝 Admission Test",
}

st.markdown("### Checklist")
for category in ("profile", "selection", "document", "test"):
    items = [it for it in checklist if it.get("category") == category]
    if not items:
        continue
    with st.container(border=True):
        st.markdown(f"**{CATEGORY_LABELS.get(category, category.title())}**")
        for item in items:
            icon = "✅" if item["done"] else "❌"
            color = "#047857" if item["done"] else "#B91C1C"
            st.markdown(
                f'<div class="ep-list-item" style="color:{color};">{icon} {item["label"]}</div>',
                unsafe_allow_html=True,
            )

# Next actions — top 3, priority-ordered.
st.divider()
st.markdown("### Next Actions")
if next_actions:
    for index, action in enumerate(next_actions[:3]):
        with st.container(border=True):
            st.markdown(f"**{action['title']}**")
            st.markdown(action["description"])
            if action.get("target"):
                if st.button(
                    "Go →",
                    key=f"goto_{index}_{action['priority']}_{action['target']}",
                ):
                    st.switch_page(action["target"])
else:
    st.success("You are up to date. Submit your application when ready.")

# Detail cards.
st.divider()
left, right = st.columns(2)

with left:
    with st.container(border=True):
        st.markdown("### Current Focus")
        focus = next_actions[0] if next_actions else None
        if focus:
            st.info(f"**{focus['title']}**\n\n{focus['description']}")
        else:
            st.success("All actionable steps are complete — submit your application!")

with right:
    with st.container(border=True):
        st.markdown("### Missing Documents")
        missing = (result or {}).get("missing_documents") or []
        if missing:
            for doc in missing:
                st.markdown(
                    f'<div class="ep-list-item" style="color:#B91C1C;">❌ {doc["name"]}</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                '<div class="ep-list-item" style="color:#047857;font-weight:600;">✅ No missing required documents.</div>',
                unsafe_allow_html=True,
            )

st.divider()

with st.container(border=True):
    st.markdown("### Program Snapshot")
    reqs = prog.get("requirements", {})
    fee_raw = reqs.get("fee_estimate_pkr")
    fee_display = f"PKR {fee_raw:,}" if isinstance(fee_raw, (int, float)) else "PKR N/A"
    deadline = reqs.get("application_deadline") or "N/A"
    test = reqs.get("admission_test") or "N/A"
    st.markdown(
        f"""
        <div class="ep-list-item">🏫 University: <strong>{uni['name']}</strong></div>
        <div class="ep-list-item">🎓 Program: <strong>{prog['name']}</strong></div>
        <div class="ep-list-item">📅 Deadline: <strong>{deadline}</strong></div>
        <div class="ep-list-item">📝 Admission Test: <strong>{test}</strong></div>
        <div class="ep-list-item">💰 Estimated Fee: <strong>{fee_display}</strong></div>
        """,
        unsafe_allow_html=True,
    )

nav_row(
    back_page="pages/5_AI_Advisor.py",
    next_page="app.py",
    back_label="← Back to Advisor",
    next_label="Back to Dashboard →",
)
