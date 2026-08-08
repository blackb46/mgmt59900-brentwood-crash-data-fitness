# -*- coding: utf-8 -*-
"""Pull Nashville Area MPO crash records inside the Brentwood envelope.

Source: Greater Nashville Regional Council open data (data_GNRC), which
publishes police-reported crashes for the MPO region. Used here as an
independent completeness benchmark against the US Accidents dataset.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

sys.stdout.reconfigure(encoding='utf-8')

ROOT = (r"C:/Users/kevin/OneDrive - City of Brentwood/Documents/COWORK_MASTER/projects/"
        r"purdue_ai/current_courses/MGMT59900_BigDataCloud/Portfolio_Project")
OUT = ROOT + '/Dataset/mpo'
os.makedirs(OUT, exist_ok=True)

BASE = 'https://services3.arcgis.com/pXGyp7DHTIE4RXOJ/arcgis/rest/services/'
LAYERS = [('Crashes_2010_2019_MPO', 'Crashes_2010_2019_MPO/FeatureServer/0'),
          ('Crashes_MPO_2020', 'Crashes_MPO_2020/FeatureServer/0')]

lim = gpd.read_file(ROOT + '/Dataset/gis/brentwood_city_limits.geojson')
minx, miny, maxx, maxy = lim.total_bounds
env = '%f,%f,%f,%f' % (minx - 0.01, miny - 0.01, maxx + 0.01, maxy + 0.01)
print('Brentwood envelope:', env)

H = {'User-Agent': 'Mozilla/5.0'}


def fetch(path, label, page=1000):
    feats, offset = [], 0
    while True:
        q = {'where': '1=1', 'outFields': '*', 'outSR': '4326', 'f': 'geojson',
             'geometry': env, 'geometryType': 'esriGeometryEnvelope', 'inSR': '4326',
             'spatialRel': 'esriSpatialRelIntersects',
             'resultOffset': str(offset), 'resultRecordCount': str(page)}
        url = BASE + path + '/query?' + urllib.parse.urlencode(q)
        for a in range(3):
            try:
                r = urllib.request.Request(url, headers=H)
                with urllib.request.urlopen(r, timeout=180) as x:
                    d = json.load(x)
                break
            except Exception as e:
                if a == 2:
                    raise
                print('   retry after', type(e).__name__)
                time.sleep(3)
        got = d.get('features', [])
        feats.extend(got)
        print('   %s +%d (total %d)' % (label, len(got), len(feats)), flush=True)
        if len(got) < page:
            break
        offset += page
    return feats


frames = []
for label, path in LAYERS:
    print(label)
    fs = fetch(path, label)
    if not fs:
        continue
    rows = []
    for f in fs:
        a = dict(f.get('properties') or {})
        g = f.get('geometry') or {}
        if g.get('type') == 'Point':
            a['lon'], a['lat'] = g['coordinates'][0], g['coordinates'][1]
        a['src_layer'] = label
        rows.append(a)
    df = pd.DataFrame(rows)
    frames.append(df)
    print('   -> %d rows, %d cols' % (len(df), df.shape[1]))

mpo = pd.concat(frames, ignore_index=True)
# unify the pieces the two layers name differently
if 'Year' not in mpo.columns:
    mpo['Year'] = None
mpo['CollisionD'] = pd.to_datetime(mpo.get('CollisionD'), errors='coerce', unit='ms')
mpo['year'] = mpo['Year'].fillna(mpo['CollisionD'].dt.year)
mpo = mpo[mpo['lat'].notna() & mpo['lon'].notna()]

g = gpd.GeoDataFrame(mpo, geometry=[Point(x, y) for x, y in zip(mpo['lon'], mpo['lat'])], crs=4326)
g['in_city'] = g.geometry.within(lim.geometry.iloc[0])

p = OUT + '/mpo_crashes_brentwood_envelope.csv'
pd.DataFrame(g.drop(columns='geometry')).to_csv(p, index=False)
print()
print('saved %s  rows=%d  (%.1f MB)' % (os.path.basename(p), len(g), os.path.getsize(p) / 1048576))
print('  inside Brentwood city limits: %d' % int(g['in_city'].sum()))
print()
print('  by year, inside the limits:')
print(g[g['in_city']].groupby(g['year'].astype('Int64')).size().to_string())
