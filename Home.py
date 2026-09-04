"""EduPath AI — home / dashboard."""
from __future__ import annotations

import streamlit as st

from backend import state
from ui import (
    app_footer,
    app_header,
    feature_card,
    inject_theme,
    init_session_state,
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
# Application state card (derived from canonical state)
# ---------------------------------------------------------------------------
profile = state.get_profile()
uni, prog, prog_display, result = state.get_selection()
checklist = state.build_checklist()
next_actions = state.build_next_actions()

has_profile = bool(
    profile.get("name")
    or profile.get("qualification")
    or profile.get("aggregate")
    or profile.get("hssc_percentage") is not None
    or profile.get("ssc_percentage") is not None
    or profile.get("documents")
)
has_selection = prog is not None
is_empty = not has_profile and not has_selection

with st.container(border=True):
    st.markdown("### Your application")

    if is_empty:
        st.caption(
            "You have not started an application yet. Upload your documents or "
            "explore programs to get going."
        )
        empty_col1, empty_col2, _ = st.columns([1, 1, 2])
        with empty_col1:
            if st.button(
                "Start Your Application",
                type="primary",
                use_container_width=True,
                key="empty_start",
            ):
                st.switch_page("pages/1_Upload_Documents.py")
        with empty_col2:
            if st.button(
                "Explore Programs",
                use_container_width=True,
                key="empty_explore",
            ):
                st.switch_page("pages/3_Select_Program.py")
    else:
        # Student summary
        name = profile.get("name") or "Student"
        qualification = profile.get("qualification") or "—"
        agg = profile.get("aggregate")
        agg_label = f"{agg}%" if isinstance(agg, (int, float)) else "—"
        st.markdown(
            f"**{name}** · Qualification: {qualification} · Aggregate: {agg_label}"
        )

        # Selection summary
        if has_selection:
            st.markdown(
                f"**Target:** {uni['name']} — {prog['name']}"
            )
        else:
            st.caption("No university or program selected yet.")

        # Eligibility verdict pill
        if has_selection and result is not None:
            verdict = result.get("verdict", "UNKNOWN")
            pill_colors = {
                "ELIGIBLE": "#047857",
                "ELIGIBLE - Conditional": "#B45309",
                "NOT ELIGIBLE": "#B91C1C",
                "UNKNOWN": "#5B5876",
            }
            color = pill_colors.get(verdict, "#5B5876")
            st.markdown(
                f'<span style="background:{color};color:#fff;padding:0.25rem 0.6rem;'
                f'border-radius:999px;font-size:0.8rem;font-weight:700;">{verdict}</span>',
                unsafe_allow_html=True,
            )

        # Checklist compact
        if checklist:
            done = sum(1 for item in checklist if item.get("done"))
            total = len(checklist)
            st.progress(done / total if total else 0.0)
            st.caption(f"{done} of {total} milestones complete")

        # Next action
        if next_actions:
            top = next_actions[0]
            st.markdown(f"**Next:** {top['title']} — {top['description']}")
            action_cols = st.columns([1, 1, 2])
            with action_cols[0]:
                if st.button(
                    "Go →",
                    type="primary",
                    use_container_width=True,
                    key="dashboard_next_action",
                ):
                    st.switch_page(top["target"])
            with action_cols[1]:
                if st.button(
                    "View full plan",
                    use_container_width=True,
                    key="dashboard_full_plan",
                ):
                    st.switch_page("pages/6_Action_Plan.py")
        else:
            st.success("All actionable steps are complete — submit your application.")

        if has_selection:
            advisor_cols = st.columns([1, 3])
            with advisor_cols[0]:
                if st.button(
                    "Talk to AI Advisor",
                    use_container_width=True,
                    key="dashboard_advisor",
                ):
                    st.switch_page("pages/5_AI_Advisor.py")

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
