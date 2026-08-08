"""Recompute every headline number in the final report and assert it.

Run this to reproduce the reported findings from the derived extracts and the
City GIS. Every assertion below corresponds to a figure quoted in the report or
the presentation. If any assertion fails, a number in the writeup is wrong.

    python scripts/verify_findings.py

Expects the repository layout:
    data/derived/*.csv
    data/gis/*.geojson
"""
import math
import os
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DER = os.path.join(ROOT, "data", "derived")
GIS = os.path.join(ROOT, "data", "gis")

PASS, FAIL = [], []


def check(label, actual, expected, tol=0):
    ok = (abs(actual - expected) <= tol) if isinstance(expected, (int, float)) \
        else (actual == expected)
    (PASS if ok else FAIL).append((label, actual, expected))
    print(("  PASS  " if ok else "  FAIL  ") + f"{label}: {actual} (expected {expected})")
    return ok


print("=" * 72)
print("MGMT 59900 Final Project - verification of reported findings")
print("=" * 72)

# ------------------------------------------------------------------ load
limits = gpd.read_file(os.path.join(GIS, "brentwood_city_limits.geojson")).to_crs(4326)
poly = limits.union_all()
streets = gpd.read_file(os.path.join(GIS, "brentwood_streets.geojson")).to_crs(4326)
ua = pd.read_csv(os.path.join(DER, "brentwood_crashes_classified.csv"), low_memory=False)
mpo = pd.read_csv(os.path.join(DER, "mpo_crashes_unified.csv"), low_memory=False)
fars = pd.read_csv(os.path.join(DER, "fars_tn.csv"), low_memory=False)

# --------------------------------------------------------- 1. spatial base
print("\n[1] Spatial ground truth")
area_sqmi = limits.to_crs(3857).area.sum() / 2.59e6
check("city limits polygon count", len(limits), 1)
check("street segments", len(streets), 4010)
check("accepted YES segments", int((streets.ACCEPTED == "YES").sum()), 3316)
check("interstate segments", int((streets.ROUTE_STAT == "INTERSTATE").sum()), 73)

# ------------------------------------------------------ 2. name filter error
print("\n[2] Name-based filtering versus the corporate limits polygon")
# The name filter reproduces the Athena drill-down exactly:
#   state = TN  ->  county = Williamson  ->  city = Brentwood
# Scoping to the county matters. The extract also covers Davidson County, where
# thousands of crashes carry a Brentwood mailing address on the shared border.
by_name = (ua.City.astype(str).str.strip().str.upper() == "BRENTWOOD") & \
          (ua.County.astype(str).str.strip().str.upper() == "WILLIAMSON")
name_hits = ua[by_name]
in_city = ua[ua.in_city == True]  # noqa: E712
check("crashes matching Brentwood by name", len(name_hits), 837)
check("crashes inside the corporate limits", len(in_city), 637)
wrong = int((by_name & (ua.in_city != True)).sum())  # noqa: E712
missed = int(((ua.in_city == True) & ~by_name).sum())  # noqa: E712
check("wrongly included by the name filter", wrong, 225)
check("missed by the name filter", missed, 25)
check("net filter error percent", round(100 * (wrong + missed) / len(name_hits), 1), 29.9)
top = ua[by_name & (ua.in_city != True)].Street.value_counts().head(3)  # noqa: E712
print(f"    top wrongly included: {', '.join(f'{s} {n}' for s, n in top.items())}")

# ------------------------------------------------------- 3. jurisdiction
print("\n[3] Jurisdiction inside the corporate limits")
agency = in_city.agency.value_counts()
check("TDOT interstate", int(agency.get("TDOT interstate", 0)), 528)
check("TDOT state route", int(agency.get("TDOT state route", 0)), 84)
check("City of Brentwood", int(agency.get("City of Brentwood", 0)), 24)
tdot = int(agency.get("TDOT interstate", 0)) + int(agency.get("TDOT state route", 0))
check("TDOT combined", tdot, 612)
check("TDOT share percent", round(100 * tdot / len(in_city), 1), 96.1)
serious = in_city[in_city.Severity >= 3].agency.value_counts()
check("serious on interstate", int(serious.get("TDOT interstate", 0)), 177)
check("serious on city streets", int(serious.get("City of Brentwood", 0)), 1)
cls = in_city.CLASS.value_counts()
check("freeway class", int(cls.get("FREEWAY_EXPRESSWAY", 0)), 528)
check("arterial class", int(cls.get("ARTERIAL", 0)), 90)

# --------------------------------------------------------- 4. MPO benchmark
print("\n[4] GNRC MPO coverage benchmark")
mpo_city = mpo[mpo.in_city == True]  # noqa: E712
check("MPO rows in the Brentwood envelope", len(mpo), 31522)
check("MPO rows inside the limits", len(mpo_city), 9837)
check("MPO duplicate record numbers",
      len(mpo_city) - mpo_city.record_no.nunique(), 0)
ua["yr"] = pd.to_datetime(ua.Start_Time, format="ISO8601").dt.year
win = range(2016, 2021)
mpo_win = int(mpo_city[mpo_city.crash_year.isin(win)].shape[0])
ua_win = int(in_city[pd.to_datetime(in_city.Start_Time, format="ISO8601")
                     .dt.year.isin(win)].shape[0])
check("MPO crashes 2016-2020", mpo_win, 6394)
check("US Accidents crashes 2016-2020", ua_win, 281)
check("coverage percent", round(100 * ua_win / mpo_win, 1), 4.4)
check("missing crashes", mpo_win - ua_win, 6113)

# -------------------------------------------------------- 5. FARS benchmark
print("\n[5] NHTSA FARS fatal-crash benchmark")
f = fars.dropna(subset=["latitude", "longitude"])
fg = gpd.GeoDataFrame(f, geometry=[Point(x, y) for x, y in
                                   zip(f.longitude, f.latitude)], crs=4326)
fars_city = fg[fg.within(poly)].copy()
check("FARS fatal crashes inside the limits", len(fars_city), 16)
check("FARS fatalities inside the limits", int(fars_city.fatalities.sum()), 16)
route = fars_city.route_type.value_counts()
check("fatal crashes on municipal streets",
      int(route.get("Local Street - Municipality", 0)), 6)

fars_city["d"] = pd.to_datetime(dict(year=fars_city.year, month=fars_city.month,
                                     day=fars_city.day)).dt.date
ua["d"] = pd.to_datetime(ua.Start_Time, format="ISO8601").dt.date
matched, nearest = 0, []
for _, r in fars_city.iterrows():
    cand = ua[ua.d == r["d"]]
    if len(cand) == 0:
        continue
    dy = (cand.Start_Lat - r.latitude) * 111320.0
    dx = (cand.Start_Lng - r.longitude) * 111320.0 * math.cos(math.radians(r.latitude))
    mn = float(np.sqrt(dx ** 2 + dy ** 2).min())
    nearest.append(mn)
    if mn <= 250:
        matched += 1
check("fatal crashes present in US Accidents", matched, 2)
check("percent of fatal crashes missing",
      round(100 * (len(fars_city) - matched) / len(fars_city), 1), 87.5)
under = sorted(x for x in nearest if x <= 250)
over = sorted(x for x in nearest if x > 250)
print(f"    matches at {[round(x, 1) for x in under]} m; "
      f"next nearest {round(over[0], 1)} m -> the 250 m threshold is not load bearing")

# ------------------------------------------- 6. cross-source fatal agreement
print("\n[6] Cross-source agreement, GNRC versus FARS")
years = [2017, 2018, 2019, 2020]
m_fatal = [int(((mpo_city.crash_year == y) & (mpo_city.fatalities > 0)).sum())
           for y in years]
f_fatal = [int((fars_city.year == y).sum()) for y in years]
check("MPO fatal by year 2017-2020", m_fatal, [4, 2, 2, 3])
check("FARS fatal by year 2017-2020", f_fatal, [4, 2, 2, 3])
check("the two sources agree year by year", m_fatal == f_fatal, True)

# ------------------------------------------------ 7. MPO data quality issues
print("\n[7] GNRC data-quality findings")
old = mpo[mpo.source_layer == "Crashes_2010_2019_MPO"]
flagged = ((old.fatalities.fillna(0) > 0) | (old.truck_involved.fillna(0) == 1)
           | (old.non_motorists.fillna(0) > 0))
check("percent of the 2010-2019 layer carrying none of the advertised flags",
      round(100 * (~flagged).sum() / len(old), 1), 96.9)
shared = [c for c in mpo.columns if c not in ("source_layer", "in_city")
          and old[c].notna().any()
          and mpo[mpo.source_layer == "Crashes_MPO_2020"][c].notna().any()]
check("fields shared by both GNRC layers", len(shared), 7)
check("crashes with a knowable collision manner",
      int(mpo_city.manner_of_collision.notna().sum()), 811)

# --------------------------------------------------------------- summary
print("\n" + "=" * 72)
print(f"{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("\nFAILURES:")
    for label, actual, expected in FAIL:
        print(f"  {label}: got {actual}, expected {expected}")
print("=" * 72)
sys.exit(1 if FAIL else 0)
