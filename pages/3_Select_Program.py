"""STEP 2: Choose university and program."""
from __future__ import annotations

import streamlit as st

from backend.data_loader import list_programs, list_universities, load_universities
from ui import init_session_state, render_sidebar

st.set_page_config(page_title="Select Program | EduPath AI", page_icon="🎓", layout="wide")
init_session_state()
render_sidebar()

st.title("STEP 2: Choose Your University and Program")
st.markdown("Select from a curated list of top Pakistani universities and programs.")

data = load_universities()
universities = list_universities(data)

cities = sorted({u.get("location", "Other") for u in universities})
fields = sorted({p.get("name", "") for u in universities for p in list_programs(u)})

fcol1, fcol2 = st.columns(2)
selected_city = fcol1.selectbox("Filter by City", ["All"] + cities)
selected_field = fcol2.selectbox("Filter by Field", ["All"] + fields)

for uni in universities:
    city_match = selected_city == "All" or uni.get("location") == selected_city
    programs = list_programs(uni)
    for prog in programs:
        field_match = selected_field == "All" or prog.get("name") == selected_field
        if not (city_match and field_match):
            continue

        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            c1.subheader(f"{uni['name']} — {prog['name']}")
            c1.caption(f"{uni.get('full_name')} · {uni.get('location')}")
            c1.write(uni.get("description", ""))

            req = prog.get("requirements", {})
            c1.markdown(
                f"""
                **Duration:** {prog.get('duration', 'N/A')}  
                **Min Aggregate:** {req.get('minimum_aggregate')}%  
                **Test:** {req.get('admission_test', 'N/A')}  
                **Deadline:** {req.get('application_deadline', 'N/A')}
                """
            )

            selected = (
                st.session_state.get("selected_university_id") == uni["id"]
                and st.session_state.get("selected_program_id") == prog["id"]
            )
            btn_label = "Selected ✓" if selected else "Select Program"
            if c2.button(btn_label, key=f"select_{uni['id']}_{prog['id']}", use_container_width=True):
                st.session_state["selected_university_id"] = uni["id"]
                st.session_state["selected_program_id"] = prog["id"]
                st.session_state["selected_program_with_university"] = {
                    **prog,
                    "university_name": uni["name"],
                    "university_id": uni["id"],
                }
                st.session_state["eligibility_result"] = None
                st.success(f"Selected {uni['name']} — {prog['name']}")
                st.rerun()

st.divider()
c1, c2 = st.columns(2)
if c1.button("← Back to Profile", use_container_width=True):
    st.switch_page("pages/2_Profile.py")
if c2.button("Next: Check Eligibility →", type="primary", use_container_width=True):
    st.switch_page("pages/4_Eligibility_Check.py")
