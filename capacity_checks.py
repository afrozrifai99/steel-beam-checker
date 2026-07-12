"""
AS 4100 capacity checks for hot-rolled I-sections (Universal Beams).

Mirrors the MATLAB reference logic for:
- Section moment capacity (Cl 5.2) with compactness classification
- Shear capacity (Cl 5.11) with slenderness / buckling reduction
- Serviceability deflection check

Shear-moment interaction (Cl 5.12) is implemented but NOT currently
applied in check_section() - see note there. All forces in kN, kNm.
All section dimensions in mm. Stresses in MPa.
"""

import math

# AS 4100 Table 5.2 slenderness limits for BENDING (compact / non-compact / slender), hot-rolled sections
LAMBDA_EP_FLANGE = 9
LAMBDA_EY_FLANGE = 16
LAMBDA_EP_WEB = 82
LAMBDA_EY_WEB = 115

# section is meant to read from ub_sections.csv, which gives section properties for hot-rolled I-sections
# design is meant to read from ub_design_300plus.csv, which gives thickness-dependent yield stress for flanges and web


def moment_capacity(section, design, phi=0.9):
    """
    Section moment capacity per AS 4100 Cl 5.2, including compactness
    classification (compact / non-compact / slender) for both the
    flange outstand and the web, taking the governing (more slender) element.

    section: a row from ub_sections.csv (bf_mm, tf_mm, tw_mm, d1_mm, Zx_1e3mm3, Sx_1e3mm3)
    design: a row from ub_design_300plus.csv (fy_flange_300plus, fy_web_300plus)
    phi: capacity factor (0.9 per AS 4100)

    Returns a dict with all intermediate values plus phi_Ms (kNm).
    """

    fy_flange = design["fy_flange_300plus"]
    fy_web = design["fy_web_300plus"]

    bf = section["bf_mm"]
    tf = section["tf_mm"]
    tw = section["tw_mm"]
    dw = section["d1_mm"]  # clear web depth between flanges
    Zx = section["Zx_1e3mm3"] * 1e3  # mm^3
    Sx = section["Sx_1e3mm3"] * 1e3  # mm^3

    # --- Flange outstand slenderness ---
    b_outstand = (bf - tw) / 2
    lambda_e_flange = (b_outstand / tf) * math.sqrt(fy_flange / 250)

    # --- Web slenderness (bending) ---
    lambda_e_web = (dw / tw) * math.sqrt(fy_web / 250)

    ratio_flange = lambda_e_flange / LAMBDA_EY_FLANGE
    ratio_web = lambda_e_web / LAMBDA_EY_WEB

    if ratio_flange >= ratio_web:
        lambda_e = lambda_e_flange
        lambda_ep = LAMBDA_EP_FLANGE
        lambda_ey = LAMBDA_EY_FLANGE
        governing_element = "Flange outstand"
        fy_moment = fy_flange
    else:
        lambda_e = lambda_e_web
        lambda_ep = LAMBDA_EP_WEB
        lambda_ey = LAMBDA_EY_WEB
        governing_element = "Web"
        fy_moment = fy_web

    Zc = min(Sx, 1.5 * Zx)

    if lambda_e <= lambda_ep:
        compactness = "Compact"
        Ze = Zc
    elif lambda_e <= lambda_ey:
        compactness = "Non-compact"
        Ze = Zx + ((lambda_ey - lambda_e) / (lambda_ey - lambda_ep)) * (Zc - Zx)
    else:
        compactness = "Slender"
        # Simplified conservative treatment (same as MATLAB reference).
        # A full AS 4100 slender-section treatment differs depending on
        # which element (flange/web) is slender - revisit if this case
        # actually occurs for sections you're checking.
        Ze = Zx * (lambda_ey / lambda_e)  # For I-section (Clause 5.2.5)

    Ms_kNm = fy_moment * Ze / 1e6
    phi_Ms = phi * Ms_kNm

    return {
        "governing_element": governing_element,
        "lambda_e_flange": lambda_e_flange,
        "lambda_e_web": lambda_e_web,
        "compactness": compactness,
        "Ze_mm3": Ze,
        "Ms_kNm": Ms_kNm,
        "phi_Ms_kNm": phi_Ms,
    }


def shear_capacity(section, design, phi=0.9):
    """
    Shear capacity per AS 4100 Cl 5.11, with web slenderness check for
    shear buckling reduction.

    Returns a dict with intermediate values plus phi_Vv (kN).
    """
    dw = section["d1_mm"]
    tw = section["tw_mm"]
    fy = design["fy_web_300plus"]

    web_slenderness_shear = (dw / tw) * math.sqrt(fy / 250)

    Aw = dw * tw  # mm^2
    Vw_kN = 0.6 * Aw * fy / 1000  # web shear yield capacity, kN

    if web_slenderness_shear <= 82:
        shear_mode = "Shear yielding governs"
        Vv_kN = Vw_kN
    else:
        shear_mode = "Shear buckling governs (reduced)"
        alpha_v = min((82 / web_slenderness_shear) ** 2, 1.0)
        Vv_kN = min(alpha_v * Vw_kN, Vw_kN)  # kN

    phi_Vv = phi * Vv_kN

    return {
        "web_slenderness_shear": web_slenderness_shear,
        "shear_mode": shear_mode,
        "Vv_kN": Vv_kN,
        "phi_Vv_kN": phi_Vv,
    }


def shear_moment_interaction(M_star, V_star, phi_Ms, Vv_kN, phi=0.9):
    """
    Shear-moment interaction per AS 4100 Cl 5.12. Only reduces shear
    capacity if M* > 0.75 * phi_Ms.

    NOTE: Not currently called from check_section() - reserved as a
    future addition. Kept here, tested and ready to wire back in.
    """
    interaction_limit = 0.75 * phi_Ms

    if M_star <= interaction_limit:
        Vvm_kN = Vv_kN
        interaction_applied = False
    else:
        interaction_factor = max(2.2 - (1.6 * M_star) / phi_Ms, 0.0)
        Vvm_kN = interaction_factor * Vv_kN
        interaction_applied = True

    phi_Vvm = phi * Vvm_kN

    return {
        "interaction_applied": interaction_applied,
        "interaction_limit_kNm": interaction_limit,
        "Vvm_kN": Vvm_kN,
        "phi_Vvm_kN": phi_Vvm,
    }


def deflection_check(w_service, L_m, E, Ix_mm4, limit_ratio=250):
    """
    Serviceability deflection check for a simply supported beam under UDL.

    w_service: unfactored (service) UDL, kN/m
    L_m: span, m
    E: elastic modulus, MPa (steel = 200,000 MPa)
    Ix_mm4: second moment of area, mm^4
    limit_ratio: deflection limit as span/limit_ratio (default 250)

    Returns a dict with delta_max (mm), limit (mm), and pass/fail.
    """
    L_mm = L_m * 1000
    w_N_per_mm = w_service  # kN/m == N/mm numerically

    delta_max = (5 * w_N_per_mm * L_mm ** 4) / (384 * E * Ix_mm4)
    limit_mm = L_mm / limit_ratio

    return {
        "delta_max_mm": delta_max,
        "limit_mm": limit_mm,
        "passes": delta_max <= limit_mm,
    }


def check_section(section, design, M_star, V_star, w_service, L_m,
                   phi=0.9, E=200000, defl_limit_ratio=250):
    """
    Runs moment, shear, and deflection checks for one trial section
    against the given design actions. Returns a combined result dict,
    including overall pass/fail and the governing check.

    Note: shear-moment interaction (Cl 5.12) is NOT currently applied -
    shear capacity is checked independently of moment. See
    shear_moment_interaction() above for the AS 4100 formula; it's kept
    ready to wire in as a future addition.

    section: a row from ub_sections.csv
    design: a row from ub_design_300plus.csv (same designation as section)
    """
    mom = moment_capacity(section, design, phi=phi)
    shr = shear_capacity(section, design, phi=phi)
    Ix_mm4 = section["Ix_1e6mm4"] * 1e6
    defl = deflection_check(w_service, L_m, E, Ix_mm4, defl_limit_ratio)

    m_util = M_star / mom["phi_Ms_kNm"]
    v_util = V_star / shr["phi_Vv_kN"]
    d_util = defl["delta_max_mm"] / defl["limit_mm"]

    utils = {"Moment": m_util, "Shear": v_util, "Deflection": d_util}
    governing_check = max(utils, key=utils.get)
    governing_util = utils[governing_check]

    passes = m_util <= 1.0 and v_util <= 1.0 and defl["passes"]

    return {
        "designation": section["designation"],
        "mass_kg_m": section["mass_kg_m"],
        "moment": mom,
        "shear": shr,
        "deflection": defl,
        "m_util": m_util,
        "v_util": v_util,
        "d_util": d_util,
        "governing_check": governing_check,
        "governing_util": governing_util,
        "passes": passes,
    }