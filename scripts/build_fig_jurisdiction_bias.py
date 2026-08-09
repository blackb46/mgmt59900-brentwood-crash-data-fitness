"""What the unfit dataset claims about jurisdiction versus what the complete
data shows. Same 2016-2020 window, same street network, same method."""
import os

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
from shapely.geometry import Point

matplotlib.use("Agg")
import matplotlib.pyplot as plt

NAVY, RED, ORANGE, GREEN = "#1D3557", "#C1272D", "#E08A1E", "#2E7D32"
GRID, SUB = "#E8ECEF", "#555555"

ROOT = (r"C:/Users/kevin/OneDrive - City of Brentwood/Documents/COWORK_MASTER"
        r"/projects/purdue_ai/current_courses/MGMT59900_BigDataCloud"
        r"/Portfolio_Project/Final_Package/GitHub_Repo")
OUT = os.path.join(os.path.dirname(ROOT), "figures", "fig_jurisdiction_bias.png")

plt.rcParams.update({"font.family": "DejaVu Sans", "figure.facecolor": "white",
                     "savefig.facecolor": "white"})

streets = gpd.read_file(os.path.join(ROOT, "data/gis/brentwood_streets.geojson")).to_crs(2274)
S = streets[["ROUTE_STAT", "ACCEPTED", "geometry"]].rename(
    columns={"ROUTE_STAT": "s_route", "ACCEPTED": "s_acc"})


def split(df, lon, lat):
    g = gpd.GeoDataFrame(df[[lon, lat]].copy(),
                         geometry=[Point(x, y) for x, y in zip(df[lon], df[lat])],
                         crs=4326).to_crs(2274)
    j = gpd.sjoin_nearest(g, S, how="left", distance_col="d")
    j = j[~j.index.duplicated()]
    out = []
    for rt, ac in zip(j.s_route, j.s_acc):
        if rt == "INTERSTATE":
            out.append("Interstate")
        elif rt in ("STATE_HIGHWAY", "US_HIGHWAY"):
            out.append("State route")
        elif ac == "YES":
            out.append("City street")
        else:
            out.append("Other")
    vc = pd.Series(out).value_counts()
    n = len(j)
    return [100 * vc.get(k, 0) / n for k in
            ("Interstate", "State route", "City street", "Other")], n


mpo = pd.read_csv(os.path.join(ROOT, "data/derived/mpo_crashes_unified.csv"),
                  low_memory=False)
mpo = mpo[(mpo.in_city == True) & (mpo.crash_year.between(2016, 2020))]  # noqa: E712
ua = pd.read_csv(os.path.join(ROOT, "data/derived/brentwood_crashes_classified.csv"),
                 low_memory=False)
ua["yr"] = pd.to_datetime(ua.Start_Time, format="ISO8601").dt.year
ua = ua[(ua.in_city == True) & (ua.yr.between(2016, 2020))]  # noqa: E712

ua_pct, ua_n = split(ua, "Start_Lng", "Start_Lat")
mpo_pct, mpo_n = split(mpo, "longitude", "latitude")

labels = ["Interstate", "State route", "City street", "Other"]
colors = [RED, ORANGE, GREEN, "#9AA7B4"]

fig, ax = plt.subplots(figsize=(7.6, 3.0))
rows = [("US Accidents\nn = %s" % f"{ua_n:,}", ua_pct),
        ("GNRC MPO\nn = %s" % f"{mpo_n:,}", mpo_pct)]
for yi, (name, pct) in enumerate(rows):
    left = 0
    for v, c, lab in zip(pct, colors, labels):
        ax.barh(yi, v, left=left, color=c, edgecolor="white", linewidth=1.6,
                height=0.55)
        if v >= 6:
            ax.text(left + v / 2, yi, f"{v:.1f}%", ha="center", va="center",
                    color="white", fontsize=12, fontweight="bold")
        left += v

ax.set_yticks([0, 1])
ax.set_yticklabels([r[0] for r in rows], fontsize=11.5, color=NAVY)
ax.set_xlim(0, 100)
ax.set_xlabel("Share of crashes inside the corporate limits, 2016-2020",
              fontsize=11, color=NAVY)
ax.invert_yaxis()
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.tick_params(length=0)
ax.grid(False)

handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in colors]
ax.legend(handles, labels, frameon=False, fontsize=10.5, ncol=4,
          loc="lower center", bbox_to_anchor=(0.5, -0.62), labelcolor=NAVY)

ax.set_title("The unfit dataset does not just undercount, it points the wrong way",
             color=NAVY, fontsize=15.5, fontweight="bold", loc="left", pad=26)
ax.text(0, 1.06,
        "City-maintained streets carry 3.6% of crashes in the national dataset "
        "and 38.6% in the complete regional data.",
        transform=ax.transAxes, color=SUB, fontsize=11.5, va="bottom")

fig.savefig(OUT, dpi=300, bbox_inches="tight")
print("wrote", OUT)
print("US Accidents:", [round(x, 1) for x in ua_pct], "n =", ua_n)
print("GNRC MPO    :", [round(x, 1) for x in mpo_pct], "n =", mpo_n)
print("City share understated by %.1fx" % (mpo_pct[2] / ua_pct[2]))
