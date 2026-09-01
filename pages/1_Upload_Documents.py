"""STEP 1: Upload academic documents and build a student profile."""
from __future__ import annotations

import streamlit as st

from backend.parser import build_profile_from_parsed, parse_upload
from backend.profile import merge_profile
from ui import init_session_state, inject_theme, nav_row, page_header, render_sidebar

st.set_page_config(page_title="Upload Documents | EduPath AI", page_icon="📄", layout="wide")
init_session_state()
inject_theme()
render_sidebar()

page_header(
    "Upload Documents",
    "Upload FSc / A-Levels transcripts, entry test score cards, CNIC / B-Form, and other required documents. We'll extract key details to build your profile.",
    "📄",
)

with st.container(border=True):
    st.markdown("### 📤 Document Upload")
    uploaded_files = st.file_uploader(
        "Drag and drop files here",
        type=["txt", "md", "pdf", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        help="Text files (.txt/.md) are parsed automatically. PDFs and images need manual verification in this MVP.",
    )

if uploaded_files:
    parsed = []
    for file in uploaded_files:
        content = file.read()
        result = parse_upload(file.name, content)
        result["filename"] = file.name
        parsed.append(result)
    st.session_state["parsed_docs"] = parsed

    st.markdown("### 📑 Parsing Results")
    for doc in parsed:
        with st.expander(f"📄 {doc['filename']} — {doc['document_type']}"):
            cols = st.columns(3)
            cols[0].metric("Qualification", doc.get("qualification") or "—")
            cols[1].metric("Board", doc.get("board") or "—")
            cols[2].metric("Aggregate", f"{doc.get('aggregate')}%" if doc.get("aggregate") else "—")
            if doc.get("ocr_note"):
                st.info(doc["ocr_note"])

    if st.button("Build Profile from Documents", type="primary", key="build_profile"):
        auto_profile = build_profile_from_parsed(parsed)
        st.session_state["student_profile"] = merge_profile(
            st.session_state["student_profile"], auto_profile
        )
        st.success("Profile created. Review and edit it on the next page.")
        if st.button("Go to Profile →", key="go_to_profile"):
            st.switch_page("pages/2_Profile.py")

st.divider()

page_header("Or Enter Details Manually", "No documents? Fill in your academic information directly.", "✍️")

profile = st.session_state["student_profile"]

with st.container(border=True):
    with st.form("manual_profile_form"):
        col1, col2 = st.columns(2)
        name = col1.text_input("Full Name", value=profile.get("name", ""))
        qualification_options = ["FSc Pre-Engineering", "ICS", "A-Levels", "FA", "FSc", "Other"]
        qualification = col2.selectbox(
            "Qualification",
            qualification_options,
            index=0 if not profile.get("qualification") else qualification_options.index(profile.get("qualification")),
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

        submitted = st.form_submit_button("Save Profile", type="primary")
        if submitted:
            updated = {
                "name": name,
                "qualification": qualification,
                "board": board,
                "aggregate": aggregate,
            }
            st.session_state["student_profile"] = merge_profile(profile, updated)
            st.success("Profile saved.")

nav_row(next_page="pages/2_Profile.py", next_label="Next: Review Profile →")
