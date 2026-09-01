"""Eligibility check and gap analysis."""
from __future__ import annotations

import streamlit as st

from backend.data_loader import get_program, get_university, load_universities
from backend.eligibility import check_eligibility
from ui import (
    init_session_state,
    inject_theme,
    missing_docs_card,
    page_header,
    render_sidebar,
    requirements_card,
    verdict_card,
)

st.set_page_config(page_title="Eligibility | EduPath AI", page_icon="✅", layout="wide")
init_session_state()
inject_theme()
render_sidebar()

page_header(
    "Eligibility Check & Gap Analysis",
    "Get a clear verdict on where you stand and what you still need for your chosen program.",
    "✅",
)

uni_id = st.session_state.get("selected_university_id")
prog_id = st.session_state.get("selected_program_id")

if not uni_id or not prog_id:
    with st.container(border=True):
        st.warning("Please select a university and program first.")
        if st.button("Go to Program Selection", type="primary", key="goto_select"):
            st.switch_page("pages/3_Select_Program.py")
    st.stop()

data = load_universities()
uni = get_university(data, uni_id)
prog = get_program(uni, prog_id)
profile = st.session_state["student_profile"]

# Enrich program with university name for display
prog_display = {**prog, "university_name": uni["name"]}

c1, c2 = st.columns([2, 1])

with c1:
    st.markdown(
        f"""
        <div class="ep-card">
            <h4 style="margin:0 0 0.4rem 0;color:#1E1B34;">{uni['name']} — {prog['name']}</h4>
            <p style="margin:0 0 0.75rem 0;color:#5B5876;">{uni.get('description', '')}</p>
            <div class="ep-list-item">📍 Location: <strong>{uni.get('location', 'N/A')}</strong></div>
            <div class="ep-list-item">⏱️ Duration: <strong>{prog.get('duration', 'N/A')}</strong></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c2:
    if st.button("Run Eligibility Check", type="primary", use_container_width=True, key="run_check"):
        result = check_eligibility(profile, prog)
        st.session_state["eligibility_result"] = result

    result = st.session_state.get("eligibility_result")
    if result:
        verdict_card(result)

if result:
    st.divider()

    a1, a2, a3 = st.columns(3)
    student_agg = profile.get("aggregate") or 0
    min_agg = result["minimum_aggregate"]
    cutoff = result["estimated_cutoff"] or min_agg

    with a1:
        st.markdown(
            f"""
            <div class="ep-metric">
                <div class="ep-metric-value">{student_agg}%</div>
                <div class="ep-metric-label">Your Aggregate</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with a2:
        st.markdown(
            f"""
            <div class="ep-metric">
                <div class="ep-metric-value">{cutoff}%</div>
                <div class="ep-metric-label">Estimated Cutoff</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with a3:
        deadline = result["application_deadline"] or "N/A"
        days = result["days_remaining"]
        delta = f"{days} days left" if days is not None else ""
        st.markdown(
            f"""
            <div class="ep-metric">
                <div class="ep-metric-value">{deadline}</div>
                <div class="ep-metric-label">{delta or 'Application Deadline'}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()

    st.markdown("### Required Documents")
    req_docs = prog.get("requirements", {}).get("required_documents", [])
    student_docs = [d.lower() for d in profile.get("documents", [])]
    for doc in req_docs:
        name = doc["name"]
        found = any(name.lower() in sd or sd in name.lower() for sd in student_docs)
        icon = "✅" if found else "❌"
        color = "#047857" if found else "#B91C1C"
        st.markdown(
            f'<div class="ep-list-item" style="color:{color};">{icon} {name}</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    st.markdown("### 🤖 AI Explanation")
    from backend.advisor import explain_eligibility
    explanation = explain_eligibility(result, prog_display)
    with st.container(border=True):
        st.info(explanation)

st.divider()
nc1, nc2, nc3 = st.columns(3)
if nc1.button("← Back to Selection", use_container_width=True, key="back_select"):
    st.switch_page("pages/3_Select_Program.py")
if nc2.button("Talk to AI Advisor", use_container_width=True, key="goto_advisor"):
    st.switch_page("pages/5_AI_Advisor.py")
if nc3.button("View Action Plan →", type="primary", use_container_width=True, key="goto_plan"):
    st.switch_page("pages/6_Action_Plan.py")
