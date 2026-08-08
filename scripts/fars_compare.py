# -*- coding: utf-8 -*-
"""Benchmark the US Accidents dataset against FARS, the fatal-crash census."""
import sys

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

sys.stdout.reconfigure(encoding='utf-8')
ROOT = (r"C:/Users/kevin/OneDrive - City of Brentwood/Documents/COWORK_MASTER/projects/"
        r"purdue_ai/current_courses/MGMT59900_BigDataCloud/Portfolio_Project")

fars = pd.read_csv(ROOT + '/Dataset/fars/fars_tn_2016_2022.csv', low_memory=False)
fars = fars[fars['LATITUDE'].notna() & fars['LONGITUD'].notna()]
lim = gpd.read_file(ROOT + '/Dataset/gis/brentwood_city_limits.geojson')
poly = lim.geometry.iloc[0]

fg = gpd.GeoDataFrame(fars, geometry=[Point(x, y) for x, y in
                                      zip(fars['LONGITUD'], fars['LATITUDE'])], crs=4326)
fg['in_city'] = fg.geometry.within(poly)
bw = fg[fg['in_city']]

print('=' * 68)
print('FARS FATAL CRASHES INSIDE THE BRENTWOOD CORPORATE LIMITS')
print('=' * 68)
print('  TN fatal crashes, 2016-2022      : %d' % len(fg))
print('  Williamson County (by county code): %d'
      % int(fg['COUNTYNAME'].astype(str).str.upper().str.contains('WILLIAMSON').sum()))
print('  Inside Brentwood city limits      : %d' % len(bw))
print('  Fatalities in those crashes       : %d' % int(bw['FATALS'].sum()))
print()
print('  by year:')
print(bw.groupby('SRC_YEAR').agg(crashes=('ST_CASE', 'size'), fatalities=('FATALS', 'sum')).to_string())
print()
if 'ROUTENAME' in bw.columns:
    print('  by route type:')
    print(bw.groupby('ROUTENAME').size().sort_values(ascending=False).to_string())
print()
if 'TWAY_ID' in bw.columns:
    print('  roadway:')
    print(bw.groupby('TWAY_ID').size().sort_values(ascending=False).head(10).to_string())

# ---- what does US Accidents have in the same footprint? -----------------
ua = pd.read_csv(ROOT + '/Dataset/derived/brentwood_crashes_classified.csv', low_memory=False)
ua = ua[ua['in_city'] == True].copy()
ts = pd.to_datetime(ua['Start_Time'], errors='coerce', format='mixed')
ua['yr'] = ts.dt.year
ua_1622 = ua[ua['yr'].between(2016, 2022)]

print()
print('=' * 68)
print('COMPLETENESS BENCHMARK, 2016-2022, same geographic footprint')
print('=' * 68)
print('  FARS fatal crashes in Brentwood        : %d' % len(bw))
print('  US Accidents crashes in Brentwood      : %d' % len(ua_1622))
print('  US Accidents records flagged as fatal  : 0  (no injury or fatality field exists)')
print()
print('  US Accidents severity is a traffic-impact scale, not an injury scale,')
print('  so a fatal crash and a minor delay are indistinguishable in it.')
print()
sev = ua_1622.groupby('Severity').size()
print('  US Accidents severity distribution in Brentwood:')
for k, v in sev.items():
    print('     severity %s : %4d' % (k, v))

# can we even locate the FARS fatalities in US Accidents?
print()
print('  Attempting to match FARS fatal crashes to US Accidents records')
print('  (same day, within 250 m):')
uag = gpd.GeoDataFrame(ua_1622, geometry=[Point(x, y) for x, y in
                                          zip(ua_1622['Start_Lng'], ua_1622['Start_Lat'])],
                       crs=4326).to_crs(2274)
uag['date'] = pd.to_datetime(ua_1622['Start_Time'], errors='coerce', format='mixed').dt.date
bwm = bw.to_crs(2274).copy()
bwm['date'] = pd.to_datetime(dict(year=bwm['SRC_YEAR'], month=bwm['MONTH'], day=bwm['DAY']),
                             errors='coerce').dt.date
hits = 0
for _, f in bwm.iterrows():
    same_day = uag[uag['date'] == f['date']]
    if len(same_day) and same_day.distance(f.geometry).min() <= 820:   # 250 m in ft
        hits += 1
print('     matched: %d of %d FARS fatal crashes' % (hits, len(bwm)))
print('     unmatched: %d' % (len(bwm) - hits))
