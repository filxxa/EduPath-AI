"""Personalized action plan dashboard."""
from __future__ import annotations

import streamlit as st

from backend.advisor import generate_action_plan
from backend.data_loader import get_program, get_university, load_universities
from backend.eligibility import check_eligibility
from ui import init_session_state, inject_theme, nav_row, page_header, render_sidebar

st.set_page_config(page_title="Action Plan | EduPath AI", page_icon="🚀", layout="wide")
init_session_state()
inject_theme()
render_sidebar()

profile = st.session_state["student_profile"]
name = profile.get("name") or "Student"

page_header(
    f"Welcome back, {name}!",
    "Your Admission Hub — track your progress and next steps.",
    "🚀",
)

uni_id = st.session_state.get("selected_university_id")
prog_id = st.session_state.get("selected_program_id")

if not uni_id or not prog_id:
    with st.container(border=True):
        st.warning("You have not selected a program yet.")
        if st.button("Start Application", type="primary", key="start_app_empty"):
            st.switch_page("pages/1_Upload_Documents.py")
    st.stop()

data = load_universities()
uni = get_university(data, uni_id)
prog = get_program(uni, prog_id)
prog_display = {**prog, "university_name": uni["name"]}

result = st.session_state.get("eligibility_result")
if result is None:
    result = check_eligibility(profile, prog)
    st.session_state["eligibility_result"] = result

plan = generate_action_plan(result, prog_display)

# Progress summary
with st.container(border=True):
    st.markdown(f"### Your Path to {prog['name']}")
    completed_steps = sum(1 for p in plan if p["status"] == "completed")
    progress_value = completed_steps / len(plan) if plan else 0.0
    st.progress(progress_value, text=f"{completed_steps} of {len(plan)} milestones complete")

# Milestones
st.markdown("### Milestones")
status_icon = {"completed": "✅", "current_action": "🔵", "upcoming": "⬜"}
status_label = {"completed": "Completed", "current_action": "Current Action", "upcoming": "Upcoming"}

for idx, step in enumerate(plan):
    with st.container(border=True):
        st.markdown(
            f"""
            <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.5rem;">
                <span style="font-size:1.25rem;">{status_icon[step['status']]}</span>
                <div>
                    <div style="font-weight:700;color:#1E1B34;">{step['step']}: {step['title']}</div>
                    <div style="font-size:0.8rem;color:#5B5876;">{status_label[step['status']]}</div>
                </div>
            </div>
            <p style="margin:0;color:#5B5876;">{step['description']}</p>
            """,
            unsafe_allow_html=True,
        )

st.divider()

# Detail cards
left, right = st.columns(2)

with left:
    with st.container(border=True):
        st.markdown("### Current Action")
        current = next((p for p in plan if p["status"] == "current_action"), None)
        if current:
            st.info(f"**{current['title']}**\n\n{current['description']}")
        else:
            st.success("All actionable steps are complete — submit your application!")

with right:
    with st.container(border=True):
        st.markdown("### Missing Documents")
        missing = result.get("missing_documents", [])
        if missing:
            for doc in missing:
                st.markdown(f'<div class="ep-list-item" style="color:#B91C1C;">❌ {doc["name"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(
                '<div class="ep-list-item" style="color:#047857;font-weight:600;">✅ No missing required documents.</div>',
                unsafe_allow_html=True,
            )

st.divider()

with st.container(border=True):
    st.markdown("### Program Snapshot")
    st.markdown(
        f"""
        <div class="ep-list-item">🏫 University: <strong>{uni['name']}</strong></div>
        <div class="ep-list-item">🎓 Program: <strong>{prog['name']}</strong></div>
        <div class="ep-list-item">📅 Deadline: <strong>{prog.get('requirements', {}).get('application_deadline', 'N/A')}</strong></div>
        <div class="ep-list-item">📝 Admission Test: <strong>{prog.get('requirements', {}).get('admission_test', 'N/A')}</strong></div>
        <div class="ep-list-item">💰 Estimated Fee: <strong>PKR {prog.get('requirements', {}).get('fee_estimate_pkr', 'N/A'):,}</strong></div>
        """,
        unsafe_allow_html=True,
    )

st.divider()
if st.button("Start Application", type="primary", use_container_width=True, key="start_app_cta"):
    st.success("In a full implementation, this would redirect to the university's online application portal.")

nav_row(
    back_page="pages/5_AI_Advisor.py",
    back_label="← Back to Advisor",
)
