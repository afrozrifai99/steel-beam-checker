"""
Draws a to-scale I-section (Universal Beam) cross-section diagram with
dimension annotations, sized from the beam's actual d, bf, tf, tw values.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches

SECTION_COLOR = "#4d7cfe"
DIM_COLOR = "#888888"


def plot_section(section):
    """
    section: a row from ub_sections.csv (needs d_mm, bf_mm, tf_mm, tw_mm)
    Returns a matplotlib Figure showing the cross-section to scale,
    with d, bf, tf, tw dimension lines.
    """
    d = section["d_mm"]
    bf = section["bf_mm"]
    tf = section["tf_mm"]
    tw = section["tw_mm"]

    fig, ax = plt.subplots(figsize=(4, 5))

    # --- Draw the I-section, centred on the origin ---
    top_flange = patches.Rectangle((-bf / 2, d / 2 - tf), bf, tf, color=SECTION_COLOR)
    bottom_flange = patches.Rectangle((-bf / 2, -d / 2), bf, tf, color=SECTION_COLOR)
    web = patches.Rectangle((-tw / 2, -d / 2 + tf), tw, d - 2 * tf, color=SECTION_COLOR)
    for patch in (top_flange, bottom_flange, web):
        ax.add_patch(patch)

    # --- Overall depth dimension line (left side) ---
    dim_x = -bf / 2 - bf * 0.28
    ax.annotate(
        "", xy=(dim_x, d / 2), xytext=(dim_x, -d / 2),
        arrowprops=dict(arrowstyle="<->", color=DIM_COLOR),
    )
    ax.text(dim_x - bf * 0.06, 0, f"d = {d:.0f} mm", rotation=90,
            va="center", ha="center", color=DIM_COLOR, fontsize=9)

    # --- Flange width dimension line (top) ---
    dim_y = d / 2 + d * 0.10
    ax.annotate(
        "", xy=(-bf / 2, dim_y), xytext=(bf / 2, dim_y),
        arrowprops=dict(arrowstyle="<->", color=DIM_COLOR),
    )
    ax.text(0, dim_y + d * 0.03, f"bf = {bf:.0f} mm",
            va="bottom", ha="center", color=DIM_COLOR, fontsize=9)

    # --- Flange thickness leader (right side, pointing at top flange) ---
    ax.annotate(
        f"tf = {tf:.1f} mm",
        xy=(bf / 2, d / 2 - tf / 2), xytext=(bf / 2 + bf * 0.18, d / 2 + d * 0.02),
        arrowprops=dict(arrowstyle="->", color=DIM_COLOR),
        va="center", ha="left", color=DIM_COLOR, fontsize=9,
    )

    # --- Web thickness leader (right side, pointing at web) ---
    ax.annotate(
        f"tw = {tw:.1f} mm",
        xy=(tw / 2, 0), xytext=(bf / 2 + bf * 0.18, -d * 0.15),
        arrowprops=dict(arrowstyle="->", color=DIM_COLOR),
        va="center", ha="left", color=DIM_COLOR, fontsize=9,
    )

    # --- Framing ---
    ax.set_xlim(-bf / 2 - bf * 0.55, bf / 2 + bf * 0.75)
    ax.set_ylim(-d / 2 - d * 0.1, d / 2 + d * 0.2)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout()

    return fig