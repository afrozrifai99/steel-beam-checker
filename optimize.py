"""
Loads the section/design tables and runs the optimization loop:
tries UB sections lightest-to-heaviest, returns the first that passes
all AS 4100 checks (moment, shear, deflection) for the given beam.
"""

import pandas as pd
from capacity_checks import check_section


def load_data(sections_path="ub_sections.csv", design_path="ub_design_300plus.csv"):
    """
    Loads and merges section geometry + design yield stresses on
    'designation', sorted lightest to heaviest.
    """
    sections = pd.read_csv(sections_path)
    design = pd.read_csv(design_path)
    merged = sections.merge(design, on="designation")
    return merged.sort_values("mass_kg_m").reset_index(drop=True)


def find_lightest_section(beams, M_star, V_star, w_service, L_m, defl_limit_ratio=250):
    """
    Iterates through beams (lightest first). Returns (winner, all_results).
    winner is None if nothing in the table passes.
    """
    all_results = []
    winner = None

    for _, row in beams.iterrows():
        result = check_section(
            section=row,
            design=row,  # merged table has both section + design columns
            M_star=M_star,
            V_star=V_star,
            w_service=w_service,
            L_m=L_m,
            defl_limit_ratio=defl_limit_ratio,
        )
        all_results.append(result)
        if result["passes"]:
            winner = result
            break  # lightest passing section found - stop searching

    return winner, all_results


def print_summary(all_results, winner):
    """Prints a compact pass/fail table plus the final recommendation."""
    print(f'{"Section":<12}{"Mass":>7}{"M util":>9}{"V util":>9}{"D util":>9}{"Governs":>12}{"Result":>8}')
    for r in all_results:
        status = "PASS" if r["passes"] else "fail"
        print(f'{r["designation"]:<12}{r["mass_kg_m"]:>7.1f}'
              f'{r["m_util"]:>9.2f}{r["v_util"]:>9.2f}{r["d_util"]:>9.2f}'
              f'{r["governing_check"]:>12}{status:>8}')

    print()
    if winner:
        print(f'>>> Recommended section: {winner["designation"]} '
              f'({winner["mass_kg_m"]} kg/m) — lightest section satisfying all checks')
        print(f'>>> Governing check: {winner["governing_check"]} '
              f'(utilisation = {winner["governing_util"]:.2f})')
    else:
        print(">>> No section in the database passes all checks for these design actions.")


if __name__ == "__main__":
    # --- Example design scenario ---
    L = 6.0            # span, m
    w_star = 20.0       # factored design UDL, kN/m
    w_service = 14.0    # unfactored (service) UDL, kN/m, for deflection

    M_star = w_star * L**2 / 8   # kNm
    V_star = w_star * L / 2      # kN

    print(f"Design actions: M* = {M_star:.1f} kNm, V* = {V_star:.1f} kN\n")

    beams = load_data()
    winner, all_results = find_lightest_section(beams, M_star, V_star, w_service, L)
    print_summary(all_results, winner)