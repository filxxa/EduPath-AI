"""Verified student profile page."""
from __future__ import annotations

import streamlit as st

from backend.state import (
    add_manual_document,
    add_manual_test_score,
    get_document_labels,
    get_profile,
    set_document_label,
    update_profile,
)
from backend.documents.categories import (
    DISPLAY_ORDER,
    UPLOAD_CATEGORIES,
    UPLOAD_GROUPS,
)
from backend.document_status import (
    get_document_records,
    get_document_status,
    get_uploaded_categories,
)
from backend.documents.classification import DOCUMENT_LABELS
from ui import init_session_state, inject_theme, nav_row, page_header, render_sidebar

st.set_page_config(page_title="Profile | EduPath AI", page_icon="👤", layout="wide")
init_session_state()
inject_theme()
render_sidebar()

page_header(
    "Student Profile",
    "Review and verify your academic information. This data drives your eligibility checks.",
    "👤",
)

feedback = st.session_state.pop("_profile_feedback", None)
if feedback:
    st.success(feedback)

profile = get_profile()

QUALIFICATIONS = ["FSc Pre-Engineering", "ICS", "A-Levels", "FA", "FSc", "Other"]
BOARDS = ["FBISE Islamabad", "BISE Lahore", "BISE Karachi", "BISE Rawalpindi", "Other"]
GROUPS = ["Pre-Engineering", "Pre-Medical", "General Science", "Humanities", "Commerce", "Other"]


def _selectbox_index(options: list[str], value: str | None) -> int:
    try:
        return options.index(value) if value in options else 0
    except ValueError:
        return 0


with st.container(border=True):
    with st.form("profile_form"):
        col1, col2 = st.columns(2)
        name = col1.text_input("Full Name", value=profile.get("name", ""))
        father_name = col2.text_input("Father's Name", value=profile.get("father_name") or "")
        qualification = col1.selectbox(
            "Qualification",
            QUALIFICATIONS,
            index=_selectbox_index(QUALIFICATIONS, profile.get("qualification")),
        )
        board = col2.selectbox(
            "Board / Examination Authority",
            BOARDS,
            index=_selectbox_index(BOARDS, profile.get("board")),
        )
        aggregate = col1.number_input(
            "Aggregate / Percentage (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(profile.get("aggregate") or 0.0),
            step=0.1,
        )
        roll_number = col2.text_input(
            "Roll Number",
            value=profile.get("roll_number") or "",
        )

        st.markdown("#### Academic Breakdown (optional)")
        acol1, acol2 = st.columns(2)
        hssc_percentage = acol1.number_input(
            "HSSC / Intermediate Percentage (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(profile.get("hssc_percentage") or 0.0),
            step=0.1,
            help="FSc / ICS / FA / A-Levels final percentage. This is the number most universities key off.",
        )
        ssc_percentage = acol2.number_input(
            "SSC / Matric Percentage (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(profile.get("ssc_percentage") or 0.0),
            step=0.1,
            help="Matric / O-Levels final percentage.",
        )
        hssc_group = acol1.selectbox(
            "HSSC Group",
            GROUPS,
            index=_selectbox_index(GROUPS, profile.get("hssc_group")),
        )
        mcol1, mcol2 = acol2.columns(2)
        obtained_marks = mcol1.number_input(
            "Obtained Marks",
            min_value=0,
            max_value=1500,
            value=int(profile.get("obtained_marks") or 0),
            step=1,
        )
        total_marks = mcol2.number_input(
            "Total Marks",
            min_value=0,
            max_value=1500,
            value=int(profile.get("total_marks") or 0),
            step=1,
        )

        notes = st.text_area("Notes", value=profile.get("notes", ""))

        save = st.form_submit_button("Save Changes", type="primary")
        if save:
            updated = {
                "name": name,
                "father_name": father_name or None,
                "qualification": qualification,
                "board": board,
                "aggregate": aggregate,
                "hssc_percentage": hssc_percentage or None,
                "ssc_percentage": ssc_percentage or None,
                "hssc_group": hssc_group,
                "roll_number": roll_number or None,
                "obtained_marks": obtained_marks or None,
                "total_marks": total_marks or None,
                "notes": notes,
            }
            update_profile(updated, source="manual")
            st.session_state["_profile_feedback"] = "Profile updated."
            st.rerun()

c1, c2 = st.columns(2)

with c1:
    with st.container(border=True):
        st.markdown("### 📎 Uploaded Documents")
        records = get_document_records(profile)
        uploaded_cats = get_uploaded_categories(profile)

        if records or uploaded_cats:
            for group_name, cat_keys in UPLOAD_GROUPS.items():
                group_cats = [k for k in cat_keys if k in uploaded_cats or any(r.get("category") == k for r in records)]
                if not group_cats:
                    continue
                st.markdown(f"**{group_name}**")
                for cat_key in group_cats:
                    status = get_document_status(profile, cat_key)
                    cat_label = UPLOAD_CATEGORIES.get(cat_key, {}).get("label", cat_key)
                    if status["uploaded"]:
                        filenames = ", ".join(status["filenames"])
                        extraction = status["extraction_status"]
                        icon = "✅" if extraction in ("extracted", "partial") else "⚠️"
                        st.markdown(
                            f'<div class="ep-list-item">{icon} <strong>{cat_label}</strong>: {filenames}'
                            f' <em>({extraction})</em></div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        legacy_docs = profile.get("documents", [])
                        from backend.eligibility import _normalize_document
                        for doc_name in legacy_docs:
                            canonical = _normalize_document(doc_name)
                            if canonical == cat_key:
                                st.markdown(
                                    f'<div class="ep-list-item">✅ <strong>{cat_label}</strong>: {doc_name} <em>(legacy)</em></div>',
                                    unsafe_allow_html=True,
                                )
        else:
            st.info("No documents uploaded yet.")

        with st.expander("Add a document type manually"):
            doc_type = st.text_input("Document type", key="manual_doc")
            if st.button("Add Document", key="add_doc") and doc_type.strip():
                add_manual_document(doc_type)
                st.session_state["_profile_feedback"] = f"Added {doc_type.strip()}."
                st.rerun()

with c2:
    with st.container(border=True):
        st.markdown("### 📝 Admission Test Scores")
        test_scores = profile.get("test_scores", {})
        if test_scores:
            for test, score in test_scores.items():
                st.markdown(f'<div class="ep-list-item">✅ <strong>{test}</strong>: {score}</div>', unsafe_allow_html=True)
        else:
            st.info("No test scores added yet.")

        with st.expander("Add a test score"):
            tcol1, tcol2 = st.columns(2)
            test_name = tcol1.text_input("Test name", key="test_name")
            test_score = tcol2.text_input("Score / Roll number", key="test_score")
            if st.button("Add Test Score", key="add_test") and test_name.strip():
                add_manual_test_score(test_name, test_score)
                st.session_state["_profile_feedback"] = f"Added {test_name.strip()}."
                st.rerun()

nav_row(
    back_page="pages/1_Upload_Documents.py",
    next_page="pages/3_Select_Program.py",
    back_label="← Back to Upload",
    next_label="Next: Select Program →",
)
