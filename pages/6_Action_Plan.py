"""Personalized action plan dashboard."""
from __future__ import annotations

import streamlit as st

from backend.advisor import generate_action_plan
from backend.data_loader import get_program, get_university, load_universities
from backend.eligibility import check_eligibility
from ui import init_session_state, render_sidebar

st.set_page_config(page_title="Action Plan | EduPath AI", page_icon="🚀", layout="wide")
init_session_state()
render_sidebar()

profile = st.session_state["student_profile"]
name = profile.get("name") or "Student"

st.title(f"Welcome back, {name}!")
st.markdown("Your Admission Hub — track your progress and next steps.")

uni_id = st.session_state.get("selected_university_id")
prog_id = st.session_state.get("selected_program_id")

if not uni_id or not prog_id:
    st.warning("You have not selected a program yet.")
    if st.button("Start Application"):
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
st.subheader("Your Path to " + prog["name"])
progress_value = sum(1 for p in plan if p["status"] == "completed") / len(plan)
st.progress(progress_value, text=f"{int(progress_value * 100)}% complete")

# Milestones
cols = st.columns(len(plan))
status_icon = {"completed": "✅", "current_action": "🔵", "upcoming": "⬜"}
status_label = {"completed": "Completed", "current_action": "Current Action", "upcoming": "Upcoming"}

for idx, step in enumerate(plan):
    with cols[idx]:
        st.markdown(f"### {status_icon[step['status']]} {step['step']}")
        st.markdown(f"**{step['title']}**")
        st.caption(status_label[step["status"]])
        st.write(step["description"])

st.divider()

# Detail cards
left, right = st.columns(2)

with left:
    st.subheader("Current Action")
    current = next((p for p in plan if p["status"] == "current_action"), None)
    if current:
        st.info(f"**{current['title']}**\n\n{current['description']}")
    else:
        st.success("All actionable steps are complete — submit your application!")

with right:
    st.subheader("Missing Documents")
    missing = result.get("missing_documents", [])
    if missing:
        for doc in missing:
            st.error(f"❌ {doc['name']}")
    else:
        st.success("No missing required documents.")

st.divider()

st.subheader("Program Snapshot")
st.markdown(
    f"""
    **University:** {uni['name']}  
    **Program:** {prog['name']}  
    **Deadline:** {prog.get('requirements', {}).get('application_deadline', 'N/A')}  
    **Admission Test:** {prog.get('requirements', {}).get('admission_test', 'N/A')}  
    **Estimated Fee:** PKR {prog.get('requirements', {}).get('fee_estimate_pkr', 'N/A'):,}
    """
)

if st.button("Start Application", type="primary", use_container_width=True):
    st.success("In a full implementation, this would redirect to the university's online application portal.")
