"""Verified student profile page."""
from __future__ import annotations

import streamlit as st

from backend.profile import add_document, add_test_score, merge_profile
from ui import init_session_state, render_sidebar

st.set_page_config(page_title="Profile | EduPath AI", page_icon="👤", layout="wide")
init_session_state()
render_sidebar()

st.title("Student Profile")
st.markdown("Review and verify your academic information. This data drives your eligibility checks.")

profile = st.session_state["student_profile"]

with st.form("profile_form"):
    col1, col2 = st.columns(2)
    name = col1.text_input("Full Name", value=profile.get("name", ""))
    qualification_options = ["FSc Pre-Engineering", "ICS", "A-Levels", "FA", "FSc", "Other"]
    qualification = col2.selectbox(
        "Qualification",
        qualification_options,
        index=qualification_options.index(profile.get("qualification")) if profile.get("qualification") in qualification_options else 0,
    )
    board_options = ["FBISE Islamabad", "BISE Lahore", "BISE Karachi", "BISE Rawalpindi", "Other"]
    board = col1.selectbox(
        "Board / Examination Authority",
        board_options,
        index=board_options.index(profile.get("board")) if profile.get("board") in board_options else 0,
    )
    aggregate = col2.number_input(
        "Aggregate / Percentage (%)",
        min_value=0.0,
        max_value=100.0,
        value=float(profile.get("aggregate") or 0.0),
        step=0.1,
    )

    notes = st.text_area("Notes", value=profile.get("notes", ""))

    save = st.form_submit_button("Save Changes", type="primary")
    if save:
        updated = {
            "name": name,
            "qualification": qualification,
            "board": board,
            "aggregate": aggregate,
            "notes": notes,
        }
        st.session_state["student_profile"] = merge_profile(profile, updated)
        st.success("Profile updated.")

st.divider()

st.subheader("Uploaded Documents")
docs = profile.get("documents", [])
if docs:
    for doc in docs:
        st.markdown(f"✅ {doc}")
else:
    st.info("No documents uploaded yet.")

with st.expander("Add a document type manually"):
    doc_type = st.text_input("Document type", key="manual_doc")
    if st.button("Add Document"):
        st.session_state["student_profile"] = add_document(profile, doc_type)
        st.success(f"Added {doc_type}")

st.divider()

st.subheader("Admission Test Scores")
test_scores = profile.get("test_scores", {})
if test_scores:
    for test, score in test_scores.items():
        st.markdown(f"✅ **{test}**: {score}")
else:
    st.info("No test scores added yet.")

with st.expander("Add a test score"):
    tcol1, tcol2 = st.columns(2)
    test_name = tcol1.text_input("Test name", key="test_name")
    test_score = tcol2.text_input("Score / Roll number", key="test_score")
    if st.button("Add Test Score"):
        st.session_state["student_profile"] = add_test_score(profile, test_name, test_score)
        st.success(f"Added {test_name}")

st.divider()

c1, c2 = st.columns(2)
if c1.button("← Back to Upload", use_container_width=True):
    st.switch_page("pages/1_Upload_Documents.py")
if c2.button("Next: Select Program →", type="primary", use_container_width=True):
    st.switch_page("pages/3_Select_Program.py")
