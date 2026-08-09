"""Side-by-side crash maps: what the national dataset sees versus what
actually happened. Same window, same polygon, same jurisdiction classification.
"""
import os

import geopandas as gpd
import matplotlib
import pandas as pd
from shapely.geometry import Point

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

NAVY, RED, ORANGE, GREEN, GREY = "#1D3557", "#C1272D", "#E08A1E", "#2E7D32", "#9AA7B4"
SUB = "#555555"

ROOT = (r"C:/Users/kevin/OneDrive - City of Brentwood/Documents/COWORK_MASTER"
        r"/projects/purdue_ai/current_courses/MGMT59900_BigDataCloud"
        r"/Portfolio_Project/Final_Package")
REPO = os.path.join(ROOT, "GitHub_Repo")
OUT = os.path.join(ROOT, "figures", "fig_map_comparison.png")

plt.rcParams.update({"font.family": "DejaVu Sans", "figure.facecolor": "white",
                     "savefig.facecolor": "white"})

lim = gpd.read_file(os.path.join(REPO, "data/gis/brentwood_city_limits.geojson")).to_crs(2274)
streets = gpd.read_file(os.path.join(REPO, "data/gis/brentwood_streets.geojson")).to_crs(2274)
S = streets[["ROUTE_STAT", "ACCEPTED", "geometry"]].rename(
    columns={"ROUTE_STAT": "s_route", "ACCEPTED": "s_acc"})


def prep(df, lon, lat):
    g = gpd.GeoDataFrame(df[[lon, lat]].copy(),
                         geometry=[Point(x, y) for x, y in zip(df[lon], df[lat])],
                         crs=4326).to_crs(2274)
    j = gpd.sjoin_nearest(g, S, how="left", distance_col="d")
    j = j[~j.index.duplicated()]
    lab = []
    for rt, ac in zip(j.s_route, j.s_acc):
        if rt == "INTERSTATE":
            lab.append(RED)
        elif rt in ("STATE_HIGHWAY", "US_HIGHWAY"):
            lab.append(ORANGE)
        elif ac == "YES":
            lab.append(GREEN)
        else:
            lab.append(GREY)
    j["c"] = lab
    return j


mpo = pd.read_csv(os.path.join(REPO, "data/derived/mpo_crashes_unified.csv"),
                  low_memory=False)
mpo = mpo[(mpo.in_city == True) & (mpo.crash_year.between(2016, 2020))]  # noqa: E712
ua = pd.read_csv(os.path.join(REPO, "data/derived/brentwood_crashes_classified.csv"),
                 low_memory=False)
ua["yr"] = pd.to_datetime(ua.Start_Time, format="ISO8601").dt.year
ua = ua[(ua.in_city == True) & (ua.yr.between(2016, 2020))]  # noqa: E712

ua_g = prep(ua, "Start_Lng", "Start_Lat")
mpo_g = prep(mpo, "longitude", "latitude")

fig, axes = plt.subplots(1, 2, figsize=(11.0, 3.9))
panels = [
    (axes[0], ua_g, f"US Accidents: {len(ua_g):,} crashes", ""),
    (axes[1], mpo_g, f"GNRC MPO: {len(mpo_g):,} crashes", ""),
]
for ax, pts, title, sub in panels:
    streets.plot(ax=ax, color="#DDE3E8", linewidth=0.45, zorder=1)
    lim.boundary.plot(ax=ax, color=NAVY, linewidth=1.9, zorder=3)
    ax.scatter(pts.geometry.x, pts.geometry.y, c=pts.c, s=7, alpha=0.75,
               linewidths=0, zorder=4)
    ax.set_title(title, color=NAVY, fontsize=14, fontweight="bold", pad=7)
    ax.set_aspect("equal")
    ax.set_axis_off()

minx, miny, maxx, maxy = lim.total_bounds
padx, pady = (maxx - minx) * 0.04, (maxy - miny) * 0.04
for ax, *_ in panels:
    ax.set_xlim(minx - padx, maxx + padx)
    ax.set_ylim(miny - pady, maxy + pady)

handles = [Line2D([], [], marker="o", linestyle="", markersize=8, color=c, label=t)
           for c, t in ((RED, "Interstate"), (ORANGE, "State route"),
                        (GREEN, "City street"))]
fig.legend(handles=handles, frameon=False, ncol=3, fontsize=12,
           loc="lower center", bbox_to_anchor=(0.5, -0.045), labelcolor=NAVY)

fig.subplots_adjust(wspace=0.10)
fig.savefig(OUT, dpi=300, bbox_inches="tight", pad_inches=0.12)
print("wrote", OUT)
for name, g in (("US Accidents", ua_g), ("GNRC MPO", mpo_g)):
    n = len(g)
    print(f"  {name}: n={n}, city-street points={sum(g.c == GREEN)} "
          f"({100*sum(g.c == GREEN)/n:.1f}%)")
