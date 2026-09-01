"""Eligibility check and gap analysis."""
from __future__ import annotations

import streamlit as st

from backend.data_loader import get_program, get_university, load_universities
from backend.eligibility import check_eligibility
from ui import init_session_state, missing_docs_card, render_sidebar, requirements_card, verdict_card

st.set_page_config(page_title="Eligibility | EduPath AI", page_icon="✅", layout="wide")
init_session_state()
render_sidebar()

st.title("Personalized Eligibility Check & Gap Analysis")

uni_id = st.session_state.get("selected_university_id")
prog_id = st.session_state.get("selected_program_id")

if not uni_id or not prog_id:
    st.warning("Please select a university and program first.")
    if st.button("Go to Program Selection"):
        st.switch_page("pages/3_Select_Program.py")
    st.stop()

data = load_universities()
uni = get_university(data, uni_id)
prog = get_program(uni, prog_id)
profile = st.session_state["student_profile"]

# Enrich program with university name for display
prog_display = {**prog, "university_name": uni["name"]}

st.subheader(f"{uni['name']} — {prog['name']}")

c1, c2 = st.columns([2, 1])

with c1:
    st.write(uni.get("description", ""))
    requirements_card(prog)

with c2:
    if st.button("Run Eligibility Check", type="primary", use_container_width=True):
        result = check_eligibility(profile, prog)
        st.session_state["eligibility_result"] = result

    result = st.session_state.get("eligibility_result")
    if result:
        verdict_card(result)

if result:
    st.divider()

    a1, a2 = st.columns([2, 1])

    with a1:
        st.subheader("Aggregate Match")
        student_agg = profile.get("aggregate") or 0
        min_agg = result["minimum_aggregate"]
        cutoff = result["estimated_cutoff"] or min_agg
        st.progress(min(student_agg / 100, 1.0), text=f"Your aggregate: {student_agg}%")
        st.markdown(
            f"**{student_agg}%** (You) / **~{cutoff}%** (Estimated Cutoff) / **{min_agg}%** (Minimum Required)"
        )

    with a2:
        st.subheader("Application Deadline")
        deadline = result["application_deadline"]
        days = result["days_remaining"]
        st.metric("Deadline", deadline or "N/A", delta=f"{days} days left" if days is not None else None)

    st.divider()

    st.subheader("Required Documents")
    req_docs = prog.get("requirements", {}).get("required_documents", [])
    student_docs = [d.lower() for d in profile.get("documents", [])]
    for doc in req_docs:
        name = doc["name"]
        found = any(name.lower() in sd or sd in name.lower() for sd in student_docs)
        icon = "✅" if found else "❌"
        st.markdown(f"{icon} {name}")

    st.divider()

    st.subheader("AI Explanation")
    from backend.advisor import explain_eligibility
    explanation = explain_eligibility(result, prog_display)
    st.info(explanation)

st.divider()
c1, c2, c3 = st.columns(3)
if c1.button("← Back to Selection", use_container_width=True):
    st.switch_page("pages/3_Select_Program.py")
if c2.button("Talk to AI Advisor", use_container_width=True):
    st.switch_page("pages/5_AI_Advisor.py")
if c3.button("View Action Plan →", type="primary", use_container_width=True):
    st.switch_page("pages/6_Action_Plan.py")
