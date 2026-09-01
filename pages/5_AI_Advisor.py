"""Integrated AI admission assistant."""
from __future__ import annotations

import streamlit as st

from backend.advisor import answer_question, explain_eligibility
from backend.data_loader import get_program, get_university, load_universities
from backend.eligibility import check_eligibility
from ui import init_session_state, inject_theme, nav_row, page_header, render_sidebar

st.set_page_config(page_title="AI Advisor | EduPath AI", page_icon="🤖", layout="wide")
init_session_state()
inject_theme()
render_sidebar()

page_header(
    "EduPath Advisor",
    "Ask anything about your admission journey. The advisor uses your profile and selected program to give grounded answers.",
    "🤖",
)

uni_id = st.session_state.get("selected_university_id")
prog_id = st.session_state.get("selected_program_id")
profile = st.session_state["student_profile"]

if not uni_id or not prog_id:
    with st.container(border=True):
        st.warning("Select a program first to get grounded advice.")
        if st.button("Select Program", type="primary", key="goto_select"):
            st.switch_page("pages/3_Select_Program.py")
    st.stop()

data = load_universities()
uni = get_university(data, uni_id)
prog = get_program(uni, prog_id)
prog_display = {**prog, "university_name": uni["name"]}

# Ensure eligibility result exists
result = st.session_state.get("eligibility_result")
if result is None:
    result = check_eligibility(profile, prog)
    st.session_state["eligibility_result"] = result

with st.container(border=True):
    st.markdown(
        f"""
        <div class="ep-list-item">🏫 Answering based on: <strong>{uni['name']} — {prog['name']}</strong></div>
        <div class="ep-list-item">👤 Profile: <strong>{profile.get('qualification', 'N/A')}, {profile.get('aggregate', 'N/A')}% aggregate</strong></div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("### Quick Questions")
quick_questions = [
    "What is my eligibility verdict?",
    "What documents are missing?",
    "When is the application deadline?",
    "How do I register for the admission test?",
    "What is the minimum aggregate required?",
]

# Render quick questions in rows of 3 to avoid cramped buttons
for row_start in range(0, len(quick_questions), 3):
    row_questions = quick_questions[row_start:row_start + 3]
    cols = st.columns(len(row_questions))
    for idx, qq in enumerate(row_questions):
        if cols[idx].button(qq, key=f"qq_{row_start + idx}", use_container_width=True):
            reply = answer_question(qq, profile, result, prog_display)
            st.session_state["chat_history"].append({"role": "user", "content": qq})
            st.session_state["chat_history"].append({"role": "assistant", "content": reply})
            st.rerun()

st.divider()

st.markdown("### Chat")
for msg in st.session_state["chat_history"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("Ask a question about your admission...")
if user_input:
    reply = answer_question(user_input, profile, result, prog_display)
    st.session_state["chat_history"].append({"role": "user", "content": user_input})
    st.session_state["chat_history"].append({"role": "assistant", "content": reply})
    st.rerun()

nav_row(
    back_page="pages/4_Eligibility_Check.py",
    next_page="pages/6_Action_Plan.py",
    back_label="← Back to Eligibility",
    next_label="Next: Action Plan →",
)
