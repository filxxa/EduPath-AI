"""STEP 2: Choose university and program."""
from __future__ import annotations

import streamlit as st

from backend.data_loader import list_programs, list_universities, load_universities
from backend.state import set_selection
from ui import init_session_state, inject_theme, nav_row, page_header, render_sidebar

st.set_page_config(page_title="Select Program | EduPath AI", page_icon="🎓", layout="wide")
init_session_state()
inject_theme()
render_sidebar()

page_header(
    "Choose Your University & Program",
    "Select from a curated list of top Pakistani universities and programs.",
    "🎓",
)

data = load_universities()
universities = list_universities(data)

cities = sorted({u.get("location", "Other") for u in universities})
categories = sorted({p.get("category", "Other") for u in universities for p in list_programs(u)})

with st.container(border=True):
    st.markdown("### 🔍 Filters")
    fcol1, fcol2 = st.columns(2)
    selected_city = fcol1.selectbox("Filter by City", ["All"] + cities)
    selected_category = fcol2.selectbox("Filter by Category", ["All"] + categories)

match_count = 0
for uni in universities:
    city_match = selected_city == "All" or uni.get("location") == selected_city
    programs = list_programs(uni)
    for prog in programs:
        cat = prog.get("category", "Other")
        cat_match = selected_category == "All" or cat == selected_category
        if not (city_match and cat_match):
            continue

        match_count += 1
        selected = (
            st.session_state.get("selected_university_id") == uni["id"]
            and st.session_state.get("selected_program_id") == prog["id"]
        )

        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            c1.markdown(f"#### {uni['name']} — {prog['name']}")
            c1.caption(f"{uni.get('full_name')} · {uni.get('location')}")
            c1.write(uni.get("description", ""))

            req = prog.get("requirements", {})
            min_agg = req.get("minimum_aggregate")
            deadline = req.get("application_deadline")
            test = req.get("admission_test")
            c1.markdown(
                f"""
                <div style="margin-top:0.5rem;">
                    <span class="ep-chip">🏷️ {cat}</span>
                    <span class="ep-chip">⏱️ {prog.get('duration') or 'N/A'}</span>
                    <span class="ep-chip">✅ {'Min ' + str(min_agg) + '%' if min_agg else 'Min aggregate check'}</span>
                    <span class="ep-chip">📝 {test or 'N/A'}</span>
                    <span class="ep-chip">📅 {deadline or 'N/A'}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            btn_label = "Selected ✓" if selected else "Select Program"
            btn_type = "secondary" if selected else "primary"
            if c2.button(btn_label, key=f"select_{uni['id']}_{prog['id']}", use_container_width=True, type=btn_type):
                set_selection(uni["id"], prog["id"])
                st.switch_page("pages/4_Eligibility_Check.py")

if match_count == 0:
    st.info("No programs match your filters. Try selecting 'All' for city or field.")

nav_row(
    back_page="pages/2_Profile.py",
    next_page="pages/4_Eligibility_Check.py",
    back_label="← Back to Profile",
    next_label="Next: Check Eligibility →",
)
