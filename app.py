import streamlit as st
import pandas as pd

from capacity_checks import check_section
from optimize import load_data, find_lightest_section
from section_diagram import plot_section

st.set_page_config(page_title="Steel Beam Checker", layout="centered")

# --- Hide Streamlit Branding & Fork Toolbars ---
st.markdown(
    """
    <style>
    /* Hides the main menu hamburger icon and the top-right GitHub/Fork toolbar */
    #MainMenu, [data-testid="stToolbar"], .stAppDeployButton, [data-testid="stHeader"] {
        display: none !important;
        visibility: hidden !important;
    }
    /* Hides the default "Made with Streamlit" footer at the bottom */
    footer {
        display: none !important;
        visibility: hidden !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# --- Top-Left Author Badge (No Flash / Clean Layout) ---
st.markdown(
    """
    <div style="font-family: monospace; font-size: 1rem; margin-bottom: -10px;">
        <span style="color: #00fff2; font-weight: bold;">Afroz Rifai</span>
        <span style="color: #666;"> · </span>
        <a href="https://www.linkedin.com/in/afroz-rifai-4b872a2b4" target="_blank" style="color: #00fff2; text-decoration: none;">🔗 LinkedIn Profile</a>
    </div>
    """,
    unsafe_allow_html=True
)

st.title("Steel Beam Design Checker")
st.caption("Simply supported UB beam under UDL — AS 4100 / AS 1170.0")

st.write("1) Enter beam and loading conditions.")
st.write("2) Click the button below to find the lightest universal beam that passes the flexure, shear and serviceability checks based on the conditions provided.")

st.divider()

# --- Load section + design data once, cached across reruns ---
@st.cache_data
def get_beams():
    return load_data()

beams = get_beams()

# --- Sidebar Configuration ---
with st.sidebar:
    mode = st.sidebar.radio(
        "What do you want to do?",
        ["Suggest the lightest section", "Check a specific section"],
    )

# --- Shared inputs: span and loading ---

with st.expander("Assumptions and scope", expanded=True):
    st.markdown(
        """
        - Simply supported, single span
        - All beams are I-sections (Universal Beam, UB) with other sections being incorporated in the future
        - Steel grade: BHP-300PLUS used for yield stress (fy) and effective section modulus (Ze) values
        - Unstiffened web assumed (no shear-buckling stiffeners)
        - Bending capacity per AS 4100 Cl 5.2, with compact / non-compact / slender section classification
        - Deflection limit per AS 1170.0 Table C1 (selectable: span/250, span/300, span/360)
        - Elastic modulus assumed E = 200 GPa (200,000 MPa)
        - Shear-moment interaction (Cl 5.12) and stiffener design for shear buckling are to be implemented in the future
        - Strength (ULS) load combination: 1.2G + 1.5Q (AS 1170.0)
        - Deflection (serviceability) load combination: G + Q (unfactored)
        """
    )

st.subheader("Beam and loading")

col1, col2 = st.columns(2)
with col1:
    L = st.number_input("Span (m)", min_value=1.0, max_value=20.0, value=6.0, step=0.5)
    G = st.number_input("Dead load, G (kN/m)", min_value=0.0, value=5.0, step=0.5)
with col2:
    Q = st.number_input("Live load, Q (kN/m)", min_value=0.0, value=8.0, step=0.5)
    defl_ratio = st.selectbox("Deflection limit", [250, 300, 360],
                              format_func=lambda x: f"Span / {x}")

# AS 1170.0 basic ULS combination for permanent + imposed action
w_star = 1.2 * G + 1.5 * Q       # factored design load, kN/m
w_service = G + Q                 # unfactored, for deflection

M_star = w_star * L**2 / 8        # kNm
V_star = w_star * L / 2           # kN

st.write(f"**Design actions:** M\\* = {M_star:.1f} kNm, V\\* = {V_star:.1f} kN "
         f"(from w\\* = {w_star:.1f} kN/m)")

st.divider()

# --- Mode 1: Optimizer ---
if mode == "Suggest the lightest section":
    if st.button("Find lightest section", type="primary"):
        winner, all_results = find_lightest_section(
            beams, M_star, V_star, w_service, L, defl_limit_ratio=defl_ratio
        )

        if winner:
            st.success(
                f"**Recommended: {winner['designation']}** ({winner['mass_kg_m']} kg/m)\n\n"
                f"Governing check: **{winner['governing_check']}** "
                f"(utilisation = {winner['governing_util']:.2f})"
            )
            winner_row = beams[beams["designation"] == winner["designation"]].iloc[0]
            fig = plot_section(winner_row)
            st.pyplot(fig, width="content")
        else:
            st.error("No section in the database passes all checks for these design actions.")

        st.subheader("All sections tried")
        table = pd.DataFrame([
            {
                "Section": r["designation"],
                "Mass (kg/m)": r["mass_kg_m"],
                "Moment util": round(r["m_util"], 2),
                "Shear util": round(r["v_util"], 2),
                "Deflection util": round(r["d_util"], 2),
                "Governing": r["governing_check"],
                "Result": "PASS" if r["passes"] else "fail",
            }
            for r in all_results
        ])
        st.dataframe(table, hide_index=True, width="stretch")

# --- Mode 2: Checker ---
else:
    designation = st.selectbox("Select a UB section", beams["designation"])
    row = beams[beams["designation"] == designation].iloc[0]

    if st.button("Check this section", type="primary"):
        result = check_section(row, row, M_star, V_star, w_service, L,
                               defl_limit_ratio=defl_ratio)

        if result["passes"]:
            st.success(f"**PASS** — {designation} ({result['mass_kg_m']} kg/m)")
        else:
            st.error(f"**FAIL** — {designation} ({result['mass_kg_m']} kg/m)")

        fig = plot_section(row)
        st.pyplot(fig, width="content")

        st.write(f"Governing check: **{result['governing_check']}** "
                 f"(utilisation = {result['governing_util']:.2f})")

        c1, c2, c3 = st.columns(3)
        c1.metric("Moment utilisation", f"{result['m_util']:.2f}")
        c2.metric("Shear utilisation", f"{result['v_util']:.2f}")
        c3.metric("Deflection utilisation", f"{result['d_util']:.2f}")

        with st.expander("Detailed calculation breakdown"):
            st.write("**Moment capacity**")
            st.json(result["moment"])
            st.write("**Shear capacity**")
            st.json(result["shear"])
            st.write("**Deflection**")
            st.json(result["deflection"])
