"""EduPath AI — home / dashboard."""
from __future__ import annotations

import streamlit as st

from ui import (
    STEP_PAGES,
    app_footer,
    app_header,
    feature_card,
    inject_theme,
    init_session_state,
    progress_steps,
    progress_summary,
    render_sidebar,
    step_card,
    trust_note,
)

st.set_page_config(
    page_title="EduPath AI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_session_state()
inject_theme()
render_sidebar()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
app_header()

# ---------------------------------------------------------------------------
# Hero
# ---------------------------------------------------------------------------
with st.container():
    st.markdown(
        """
        <div class="ep-hero">
            <div class="ep-eyebrow">Pakistani university admissions</div>
            <h1 class="ep-h1">Your university journey, simplified.</h1>
            <p class="ep-sub">
                EduPath AI helps you upload and understand your academic documents,
                compare Pakistani university programs, check your eligibility against
                real admission requirements, and follow a clear step-by-step plan to
                meet deadlines with confidence.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cta_col1, cta_col2, _ = st.columns([1, 1, 2])
    with cta_col1:
        if st.button(
            "Start Your Application",
            type="primary",
            use_container_width=True,
            key="hero_start",
        ):
            st.switch_page("pages/1_Upload_Documents.py")
    with cta_col2:
        if st.button(
            "Explore Programs",
            use_container_width=True,
            key="hero_explore",
        ):
            st.switch_page("pages/3_Select_Program.py")

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Progress card
# ---------------------------------------------------------------------------
completed, total, ratio = progress_summary()
steps = progress_steps()

with st.container(border=True):
    st.markdown("### Application Progress")
    st.progress(ratio)
    st.markdown(f"**{completed} of {total} steps completed**")

    step_cols = st.columns(total)
    for col, (label, done) in zip(step_cols, steps):
        icon = "✅" if done else "⬜"
        with col:
            st.caption(f"{icon} {label}")

    st.markdown("<br>", unsafe_allow_html=True)

    if completed == total:
        st.success("All steps are complete — review your Action Plan.")
        if st.button(
            "View Action Plan",
            type="primary",
            use_container_width=True,
            key="progress_action_plan",
        ):
            st.switch_page("pages/6_Action_Plan.py")
    else:
        next_step_index = next((i for i, (_, done) in enumerate(steps) if not done), 0)
        next_page = STEP_PAGES[next_step_index]
        if st.button(
            "Continue where you left off →",
            type="primary",
            use_container_width=True,
            key="progress_continue",
        ):
            st.switch_page(next_page)

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Feature cards
# ---------------------------------------------------------------------------
st.markdown("### Everything you need, in one place")
feat_cols = st.columns(4, gap="large")

features = [
    ("📄", "Document Analysis", "Upload your academic documents and build your student profile.", "pages/1_Upload_Documents.py", "feat_docs"),
    ("✅", "Eligibility Checker", "See whether you meet a university program's requirements.", "pages/4_Eligibility_Check.py", "feat_elig"),
    ("🤖", "AI Admission Advisor", "Get personalized answers grounded in admission requirements.", "pages/5_AI_Advisor.py", "feat_advisor"),
    ("🚀", "Action Plan", "Know exactly what to do next.", "pages/6_Action_Plan.py", "feat_plan"),
]

for col, (icon, title, desc, page, btn_key) in zip(feat_cols, features):
    with col:
        feature_card(icon, title, desc)
        if st.button(f"Go to {title}", use_container_width=True, key=btn_key):
            st.switch_page(page)

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# How it works
# ---------------------------------------------------------------------------
st.markdown("### How it works")
how_cols = st.columns(3, gap="large")
how_steps = [
    (1, "Upload your documents", "Add your FSc, A-Levels, entry test, and other academic documents."),
    (2, "Check your eligibility", "Compare your profile against real university program requirements."),
    (3, "Follow your personalized plan", "Get clear next steps, deadlines, and document reminders."),
]
for col, (num, title, desc) in zip(how_cols, how_steps):
    with col:
        step_card(num, title, desc)

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Trust section
# ---------------------------------------------------------------------------
trust_note(
    "Eligibility results are generated from university-provided requirements stored in EduPath AI "
    "and are for guidance only. EduPath AI does not perform official verification — always confirm "
    "criteria, deadlines, and fees on the university's official admissions portal before applying."
)

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
app_footer()
