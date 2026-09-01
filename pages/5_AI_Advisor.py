"""Integrated AI admission assistant."""
from __future__ import annotations

import streamlit as st

from backend.advisor import answer_question, explain_eligibility
from backend.data_loader import get_program, get_university, load_universities
from backend.eligibility import check_eligibility
from ui import init_session_state, render_sidebar

st.set_page_config(page_title="AI Advisor | EduPath AI", page_icon="🤖", layout="wide")
init_session_state()
render_sidebar()

st.title("EduPath Advisor")

uni_id = st.session_state.get("selected_university_id")
prog_id = st.session_state.get("selected_program_id")
profile = st.session_state["student_profile"]

if not uni_id or not prog_id:
    st.warning("Select a program first to get grounded advice.")
    if st.button("Select Program"):
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

st.markdown(f"Advisor is answering based on **{uni['name']} — {prog['name']}** requirements.")

# Quick questions
st.subheader("Quick Questions")
quick_questions = [
    "What is my eligibility verdict?",
    "What documents are missing?",
    "When is the application deadline?",
    "How do I register for the admission test?",
    "What is the minimum aggregate required?",
]
cols = st.columns(len(quick_questions))
for idx, qq in enumerate(quick_questions):
    if cols[idx].button(qq, key=f"qq_{idx}", use_container_width=True):
        reply = answer_question(qq, profile, result, prog_display)
        st.session_state["chat_history"].append({"role": "user", "content": qq})
        st.session_state["chat_history"].append({"role": "assistant", "content": reply})
        st.rerun()

st.divider()

st.subheader("Chat")
for msg in st.session_state["chat_history"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("Ask a question about your admission...")
if user_input:
    reply = answer_question(user_input, profile, result, prog_display)
    st.session_state["chat_history"].append({"role": "user", "content": user_input})
    st.session_state["chat_history"].append({"role": "assistant", "content": reply})
    st.rerun()

st.divider()
if st.button("← Back to Eligibility", use_container_width=True):
    st.switch_page("pages/4_Eligibility_Check.py")
