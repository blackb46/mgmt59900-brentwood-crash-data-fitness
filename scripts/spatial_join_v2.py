# -*- coding: utf-8 -*-
"""Brentwood crash classification, name-aware spatial join.

Two spatial tests against the City of Brentwood's authoritative GIS:
  1. point-in-polygon against the corporate limits  -> in_city
  2. nearest centerline within 100 ft, preferring a segment whose name matches
     the reported street, to avoid mis-assigning cross-street crashes to the
     interstate at grade separations                -> maintaining agency

Projected to EPSG:2274 (NAD83 / Tennessee State Plane, US ft).
"""
import os
import re
import sys

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

sys.stdout.reconfigure(encoding='utf-8')

ROOT = (r"C:/Users/kevin/OneDrive - City of Brentwood/Documents/COWORK_MASTER/projects/"
        r"purdue_ai/current_courses/MGMT59900_BigDataCloud/Portfolio_Project")
GIS, OUT = ROOT + '/Dataset/gis', ROOT + '/Dataset/derived'
os.makedirs(OUT, exist_ok=True)
SNAP_FT = 100.0

STOPWORDS = {'N', 'S', 'E', 'W', 'NORTH', 'SOUTH', 'EAST', 'WEST', 'RD', 'DR', 'LN',
             'ST', 'AVE', 'BLVD', 'CIR', 'CT', 'PIKE', 'WAY', 'PL', 'TRL', 'PKWY',
             'HWY', 'THE'}


def norm(s):
    s = re.sub(r'[^A-Z0-9 ]', ' ', str(s).upper())
    toks = [t for t in s.split() if t and t not in STOPWORDS]
    return toks


def key(s):
    t = norm(s)
    return ' '.join(t) if t else ''


print('loading crashes...')
USE = ['ID', 'Severity', 'Start_Time', 'Start_Lat', 'Start_Lng', 'Street', 'City',
       'County', 'State', 'Zipcode', 'Sunrise_Sunset', 'Weather_Condition',
       'Junction', 'Crossing', 'Traffic_Signal', 'Stop']
parts = []
for ch in pd.read_csv(ROOT + '/Dataset/raw/US_Accidents_March23.csv',
                      usecols=USE, chunksize=500_000, low_memory=False):
    t = ch[ch['State'] == 'TN']
    if len(t):
        parts.append(t)
tn = pd.concat(parts).reset_index(drop=True)
for c in ['Street', 'City', 'County']:
    tn[c] = tn[c].astype(str).str.strip()

limits = gpd.read_file(GIS + '/brentwood_city_limits.geojson').to_crs(2274)
streets = gpd.read_file(GIS + '/brentwood_streets.geojson').to_crs(2274)
streets['seg_key'] = streets['NAME'].apply(key)

minx, miny, maxx, maxy = gpd.read_file(GIS + '/brentwood_city_limits.geojson').total_bounds
pad = 0.02
box = tn[(tn['Start_Lng'].between(minx - pad, maxx + pad)) &
         (tn['Start_Lat'].between(miny - pad, maxy + pad))].copy()
pts = gpd.GeoDataFrame(box, geometry=[Point(xy) for xy in zip(box['Start_Lng'], box['Start_Lat'])],
                       crs=4326).to_crs(2274)
pts['crash_key'] = pts['Street'].apply(key)
pts['in_city'] = pts.geometry.within(limits.geometry.union_all())
print('  bbox crashes %d | inside limits %d' % (len(pts), int(pts['in_city'].sum())))

# ---- every candidate segment within tolerance ---------------------------
print('building candidate pairs within %.0f ft...' % SNAP_FT)
buf = pts.copy()
buf['geometry'] = buf.geometry.buffer(SNAP_FT)
cand = gpd.sjoin(buf, streets[['NAME', 'seg_key', 'CLASS', 'ROUTE_NO', 'ROUTE_STAT',
                               'ACCEPTED', 'SPDLIMIT', 'LANES', 'geometry']],
                 how='inner', predicate='intersects')
print('  candidate pairs: %d' % len(cand))

# true distance from the point (not the buffer) to each candidate segment
seg_geom = streets.geometry
cand['dist_ft'] = [pts.geometry.loc[i].distance(seg_geom.loc[j])
                   for i, j in zip(cand.index, cand['index_right'])]
cand['name_match'] = cand['crash_key'] == cand['seg_key']

# prefer a name match, then the closest segment
cand = cand.sort_values(['name_match', 'dist_ft'], ascending=[False, True])
best = cand[~cand.index.duplicated(keep='first')]
print('  matched crashes: %d  (name-matched %d, nearest-only %d)'
      % (len(best), int(best['name_match'].sum()), int((~best['name_match']).sum())))

res = pts.drop(columns='geometry').join(
    best[['NAME', 'CLASS', 'ROUTE_NO', 'ROUTE_STAT', 'ACCEPTED', 'SPDLIMIT',
          'LANES', 'dist_ft', 'name_match']], how='left')


def agency(r):
    if pd.isna(r['ACCEPTED']):
        return 'Unmatched'
    rs = str(r['ROUTE_STAT'] or '').strip()
    if rs == 'INTERSTATE':
        return 'TDOT interstate'
    if rs in ('STATE_HIGHWAY', 'US_HIGHWAY'):
        return 'TDOT state route'
    if str(r['ACCEPTED']).upper() == 'YES':
        return 'City of Brentwood'
    return 'Other / not accepted'


res['agency'] = res.apply(agency, axis=1)
city = res[res['in_city']]

print()
print('=' * 68)
print('INSIDE THE CORPORATE LIMITS: %d crashes' % len(city))
print('=' * 68)
g = city.groupby('agency').size().sort_values(ascending=False)
for k, v in g.items():
    print('  %-22s %5d  %5.1f%%' % (k, v, 100 * v / len(city)))

print()
print('BY FUNCTIONAL CLASS')
for k, v in city.groupby('CLASS').size().sort_values(ascending=False).items():
    print('  %-22s %5d  %5.1f%%' % (k, v, 100 * v / len(city)))

print()
print('CITY-MAINTAINED STREETS INSIDE THE LIMITS')
cm = city[city['agency'] == 'City of Brentwood']
print('  %d crashes across %d streets' % (len(cm), cm['NAME'].nunique()))
print(cm.groupby('NAME').size().sort_values(ascending=False).head(12).to_string())

print()
print('NAME-AWARE FIX: crashes moved off the interstate')
old_it = 552
new_it = int((city['agency'] == 'TDOT interstate').sum())
print('  interstate before name-aware matching: %d' % old_it)
print('  interstate after                    : %d' % new_it)
print('  reassigned                          : %d' % (old_it - new_it))

print()
print('COMPARISON WITH THE NAME-BASED FILTER')
old = tn[(tn['County'] == 'Williamson') & (tn['City'] == 'Brentwood')]
o, n = set(old['ID']), set(city['ID'])
print('  county+city filter : %d' % len(old))
print('  spatial (in limits): %d' % len(city))
print('  agree              : %d' % len(o & n))
print('  filter false-yes   : %d' % len(o - n))
print('  filter missed      : %d' % len(n - o))

cols = ['ID', 'Severity', 'Start_Time', 'Start_Lat', 'Start_Lng', 'Street', 'City',
        'County', 'Zipcode', 'Sunrise_Sunset', 'Weather_Condition', 'Junction',
        'Crossing', 'Traffic_Signal', 'Stop', 'in_city', 'agency', 'NAME', 'CLASS',
        'ROUTE_NO', 'ROUTE_STAT', 'ACCEPTED', 'SPDLIMIT', 'LANES', 'dist_ft', 'name_match']
p = OUT + '/brentwood_crashes_classified.csv'
pd.DataFrame(res[[c for c in cols if c in res.columns]]).to_csv(p, index=False)
print()
print('saved %s (%d rows)' % (os.path.basename(p), len(res)))
