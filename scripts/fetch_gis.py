# -*- coding: utf-8 -*-
"""Pull the City of Brentwood city-limits polygon and street centerlines from
the city's public ArcGIS REST services, as WGS84 GeoJSON."""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')

OUT = (r"C:/Users/kevin/OneDrive - City of Brentwood/Documents/COWORK_MASTER/projects/"
       r"purdue_ai/current_courses/MGMT59900_BigDataCloud/Portfolio_Project/Dataset/gis")
os.makedirs(OUT, exist_ok=True)

BOUNDARY = ('https://maps.brentwoodtn.gov/arcgis/rest/services/Datasets/'
            'AdministrativeAreas/MapServer/2')
STREETS = ('https://maps.brentwoodtn.gov/arcgis/rest/services/Datasets/'
           'Transportation/MapServer/12')

STREET_FIELDS = ('OBJECTID,NAME,LABEL,PREDIR,SUFDIR,TYPE,CLASS,ROUTE_NO,ROUTE_STAT,'
                 'ACCEPTED,STATUS,CITY_L,CITY_R,COUNTY_L,COUNTY_R,SPDLIMIT,SpeedLimit,'
                 'LANES,ONEWAY,ALT_NAME')


def fetch(base, out_fields, label, page=1000):
    """Page through a layer and return a single GeoJSON FeatureCollection."""
    feats, offset = [], 0
    while True:
        q = {
            'where': '1=1',
            'outFields': out_fields,
            'outSR': '4326',
            'f': 'geojson',
            'returnGeometry': 'true',
            'resultOffset': str(offset),
            'resultRecordCount': str(page),
        }
        url = base + '/query?' + urllib.parse.urlencode(q)
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url, timeout=120) as r:
                    d = json.load(r)
                break
            except Exception as e:
                if attempt == 2:
                    raise
                print('   retry %d after %s' % (attempt + 1, type(e).__name__))
                time.sleep(3)
        got = d.get('features', [])
        feats.extend(got)
        print('   %s: +%d (total %d)' % (label, len(got), len(feats)))
        if len(got) < page:
            break
        offset += page
    return {'type': 'FeatureCollection',
            'crs': {'type': 'name', 'properties': {'name': 'EPSG:4326'}},
            'features': feats}


print('Fetching city limits...')
b = fetch(BOUNDARY, 'OBJECTID,NAME,COUNTY_ID', 'boundary')
pb = os.path.join(OUT, 'brentwood_city_limits.geojson')
with open(pb, 'w', encoding='utf-8') as f:
    json.dump(b, f)
print('   saved %s (%.1f KB)' % (os.path.basename(pb), os.path.getsize(pb) / 1024))

print('Fetching street centerlines...')
s = fetch(STREETS, STREET_FIELDS, 'streets')
ps = os.path.join(OUT, 'brentwood_streets.geojson')
with open(ps, 'w', encoding='utf-8') as f:
    json.dump(s, f)
print('   saved %s (%.1f MB)' % (os.path.basename(ps), os.path.getsize(ps) / 1024 / 1024))

# ---------------------------------------------------------------- sanity
import geopandas as gpd

gb = gpd.read_file(pb)
gs = gpd.read_file(ps)
print()
print('BOUNDARY  crs=%s  features=%d' % (gb.crs, len(gb)))
print('  bounds  :', [round(v, 5) for v in gb.total_bounds])
print('  name    :', gb.iloc[0].get('NAME'))
gb_m = gb.to_crs(2274)
print('  area    : %.2f sq mi' % (gb_m.area.sum() / 27878400.0))

print()
print('STREETS   crs=%s  features=%d' % (gs.crs, len(gs)))
print('  bounds  :', [round(v, 5) for v in gs.total_bounds])
print('  ACCEPTED   :', gs['ACCEPTED'].value_counts(dropna=False).to_dict())
print('  ROUTE_STAT :', gs['ROUTE_STAT'].fillna('(null)').replace('', '(blank)').value_counts().to_dict())
print('  CLASS      :', gs['CLASS'].value_counts(dropna=False).to_dict())
gs_m = gs.to_crs(2274)
print('  total centerline miles: %.1f' % (gs_m.length.sum() / 5280.0))
