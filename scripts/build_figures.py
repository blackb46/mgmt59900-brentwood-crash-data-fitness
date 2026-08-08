"""Build the MPO-derived and cross-source-validation figures for the final report.

House palette sampled from the existing figures so the new plates sit alongside
fig_jurisdiction and fig_coverage without a visible seam.
"""
import math
import os

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
from shapely.geometry import Point

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

NAVY = "#1D3557"
RED = "#C1272D"
ORANGE = "#E08A1E"
GREEN = "#2E7D32"
MUTED = "#9AA7B4"
GRID = "#E8ECEF"
SUB = "#555555"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DER = os.path.join(ROOT, "data", "derived")
GIS = os.path.join(ROOT, "data", "gis")
OUT = os.path.join(ROOT, "figures")

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.edgecolor": NAVY,
    "axes.labelcolor": NAVY,
    "xtick.color": SUB,
    "ytick.color": SUB,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 1.0,
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
})


def titles(ax, title, subtitle):
    ax.set_title(title, color=NAVY, fontsize=17, fontweight="bold",
                 loc="left", pad=26)
    ax.text(0, 1.015, subtitle, transform=ax.transAxes, color=SUB,
            fontsize=12.5, va="bottom", ha="left")


def finish(fig, name):
    path = os.path.join(OUT, name)
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("wrote", name)


# ---------------------------------------------------------------- load
mpo = pd.read_csv(os.path.join(DER, "mpo_crashes_unified.csv"), low_memory=False)
mpo_city = mpo[mpo.in_city == True]  # noqa: E712

lim = gpd.read_file(os.path.join(GIS, "brentwood_city_limits.geojson")).to_crs(4326)
poly = lim.union_all()
fars = pd.read_csv(os.path.join(DER, "fars_tn.csv"), low_memory=False)
fars = fars.dropna(subset=["latitude", "longitude"])
fars_g = gpd.GeoDataFrame(
    fars, geometry=[Point(x, y) for x, y in zip(fars.longitude, fars.latitude)],
    crs=4326)
fars_city = fars_g[fars_g.within(poly)].copy()


# ------------------------------------------- 1. cross-source fatal agreement
years = [2017, 2018, 2019, 2020]
mpo_fatal = [int(((mpo_city.crash_year == y) & (mpo_city.fatalities > 0)).sum())
             for y in years]
fars_fatal = [int((fars_city.year == y).sum()) for y in years]
assert mpo_fatal == fars_fatal, (mpo_fatal, fars_fatal)

fig, ax = plt.subplots(figsize=(7.4, 3.3))
x = np.arange(len(years))
w = 0.38
b1 = ax.bar(x - w / 2, mpo_fatal, w, label="GNRC MPO", color=NAVY,
            edgecolor=NAVY)
b2 = ax.bar(x + w / 2, fars_fatal, w, label="NHTSA FARS", color=ORANGE,
            edgecolor=NAVY, linewidth=0.6)
for bars in (b1, b2):
    for r in bars:
        ax.annotate(f"{int(r.get_height())}",
                    (r.get_x() + r.get_width() / 2, r.get_height()),
                    ha="center", va="bottom", color=NAVY, fontsize=12,
                    xytext=(0, 2), textcoords="offset points")
ax.set_xticks(x)
ax.set_xticklabels(years, fontsize=12)
ax.set_ylabel("Fatal crashes", fontsize=11.5)
ax.set_ylim(0, max(mpo_fatal) + 1.6)
ax.yaxis.set_major_locator(MaxNLocator(integer=True))
ax.set_axisbelow(True)
ax.grid(axis="x", visible=False)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.legend(frameon=False, fontsize=11, loc="upper right", labelcolor=NAVY)
titles(ax,
       "Two independent sources agree on fatal crashes, year by year",
       "Fatal crashes inside the corporate limits in the years both sources "
       "cover. Counts match 4 for 4.")
finish(fig, "fig_fatal_agreement.png")


# ------------------------------------------------ 2. GNRC layer schema gap
common = ["record_no", "collision_ts", "crash_year", "latitude", "longitude",
          "fatalities", "non_motorists"]
old_only = ["truck_involved"]
new_only = ["serious_injuries", "pedestrian", "bicycle", "crash_type",
            "manner_of_collision", "lighting", "weather", "first_harmful_event"]
fields = common + old_only + new_only
labels = [f.replace("_", " ") for f in fields]

old = mpo[mpo.source_layer == "Crashes_2010_2019_MPO"]
new = mpo[mpo.source_layer == "Crashes_MPO_2020"]
grid_vals = np.array([[old[f].notna().any(), new[f].notna().any()]
                      for f in fields], dtype=float)

fig, ax = plt.subplots(figsize=(6.6, 5.0))
ax.grid(False)
for i in range(len(fields)):
    for j in range(2):
        present = grid_vals[i, j] > 0
        ax.add_patch(plt.Rectangle(
            (j, len(fields) - 1 - i), 1, 1,
            facecolor=(GREEN if present else "#F2F2F2"),
            edgecolor="white", linewidth=2))
        ax.text(j + 0.5, len(fields) - 1 - i + 0.5,
                "present" if present else "absent",
                ha="center", va="center", fontsize=9.5,
                color=("white" if present else "#999999"),
                fontweight=("bold" if present else "normal"))
ax.set_xlim(0, 2)
ax.set_ylim(0, len(fields))
ax.set_xticks([0.5, 1.5])
ax.set_xticklabels(["2010-2019 layer\n28,590 rows",
                    "2020 layer\n2,932 rows"], fontsize=11, color=NAVY)
ax.xaxis.tick_top()
ax.set_yticks([len(fields) - 1 - i + 0.5 for i in range(len(fields))])
ax.set_yticklabels(labels, fontsize=10.5)
for s in ax.spines.values():
    s.set_visible(False)
ax.tick_params(length=0)
ax.set_title("The two GNRC layers share only 7 of 16 fields",
             color=NAVY, fontsize=16, fontweight="bold", loc="left", pad=52)
ax.text(0, 1.105,
        "Attribute coverage by source layer. Collision manner and injury "
        "severity exist only for 2020.",
        transform=ax.transAxes, color=SUB, fontsize=11.5, va="bottom")
finish(fig, "fig_mpo_schema_gap.png")


# ------------------------------------------- 3. manner of collision, 2020 only
sub = mpo_city[mpo_city.manner_of_collision.notna()]
n = len(sub)
vc = sub.manner_of_collision.value_counts()
vc = vc[vc.index != "Unknown"]
top = vc.head(7)[::-1]
short = {"Not Collision with Motor Vehicle in Transport": "Not a collision with\nanother vehicle",
         "Sideswipe, Same Direction": "Sideswipe, same direction",
         "Sideswipe, Opposite Direction": "Sideswipe, opposite direction",
         "HeadOn": "Head on"}
names = [short.get(i, i) for i in top.index]

fig, ax = plt.subplots(figsize=(7.4, 3.6))
colors = [MUTED] * len(top)
colors[-1] = NAVY
bars = ax.barh(range(len(top)), top.values, color=colors, edgecolor=NAVY,
               linewidth=0.6)
for i, (r, v) in enumerate(zip(bars, top.values)):
    ax.annotate(f"{int(v)}  ({100 * v / n:.1f}%)",
                (r.get_width(), r.get_y() + r.get_height() / 2),
                xytext=(6, 0), textcoords="offset points",
                va="center", color=NAVY, fontsize=11.5)
ax.set_yticks(range(len(top)))
ax.set_yticklabels(names, fontsize=11)
ax.set_xlabel("Crashes", fontsize=11.5)
ax.set_xlim(0, top.max() * 1.28)
ax.set_axisbelow(True)
ax.grid(axis="y", visible=False)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
titles(ax,
       "Collision manner is knowable for one year only",
       f"{n} crashes inside the corporate limits in 2020, the only year GNRC "
       "publishes this attribute.")
finish(fig, "fig_mpo_manner.png")

print("\nmanner base n =", n, "of", len(mpo_city), "in-city MPO rows")
print("fatal by year MPO", dict(zip(years, mpo_fatal)))
print("fatal by year FARS", dict(zip(years, fars_fatal)))
