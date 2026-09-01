"""EduPath AI — main entry point."""
from __future__ import annotations

import streamlit as st

from ui import init_session_state, render_sidebar

st.set_page_config(
    page_title="EduPath AI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_session_state()
render_sidebar()

st.title("EduPath AI: Your Personalized Path to Pakistani University Admission")
st.markdown(
    "Clean, friendly, modern educational guidance for Pakistani students. "
    "Upload your documents, verify your profile, choose a university and program, "
    "and get a personalized eligibility check with next steps."
)

st.divider()

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("1. Upload Documents")
    st.write("Upload your FSc, A-Levels, entry test score cards, and other academic documents.")
    if st.button("Start Upload", type="primary", use_container_width=True):
        st.switch_page("pages/1_Upload_Documents.py")

with col2:
    st.subheader("2. Select Program")
    st.write("Browse curated Pakistani universities and programs with verified requirements.")
    if st.button("Choose Program", use_container_width=True):
        st.switch_page("pages/3_Select_Program.py")

with col3:
    st.subheader("3. Check Eligibility")
    st.write("Get a rule-based eligibility verdict, missing document list, and AI guidance.")
    if st.button("Check Eligibility", use_container_width=True):
        st.switch_page("pages/4_Eligibility_Check.py")

st.divider()

st.info(
    "Use the sidebar to navigate through the steps. Your progress is saved during this session.",
    icon="💡",
)
