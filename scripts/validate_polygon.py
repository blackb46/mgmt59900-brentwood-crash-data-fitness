# -*- coding: utf-8 -*-
"""Sanity-check the corporate limits polygon before trusting any count."""
import sys
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

sys.stdout.reconfigure(encoding='utf-8')
GIS = (r"C:/Users/kevin/OneDrive - City of Brentwood/Documents/COWORK_MASTER/projects/"
       r"purdue_ai/current_courses/MGMT59900_BigDataCloud/Portfolio_Project/Dataset/gis")

g = gpd.read_file(GIS + '/brentwood_city_limits.geojson')
print('crs        :', g.crs)
print('features   :', len(g))
geom = g.geometry.iloc[0]
print('geom type  :', geom.geom_type)
print('valid      :', geom.is_valid)
if geom.geom_type == 'MultiPolygon':
    print('parts      :', len(geom.geoms))
    for i, p in enumerate(geom.geoms):
        print('   part %d area %.3f sq mi, interior rings %d'
              % (i, gpd.GeoSeries([p], crs=4326).to_crs(2274).area.iloc[0] / 27878400, len(p.interiors)))
else:
    print('interior rings (holes):', len(geom.interiors))
gm = g.to_crs(2274)
print('area       : %.2f sq mi   (Brentwood is about 41.5)' % (gm.area.sum() / 27878400))
print('perimeter  : %.1f mi' % (gm.length.sum() / 5280))
print('bounds     :', [round(v, 5) for v in g.total_bounds])

print()
print('KNOWN-POINT TESTS  (lon, lat)')
tests = [
    ('Brentwood City Hall, 5211 Maryland Way', -86.78280, 36.03310, True),
    ('Maryland Farms office park',             -86.79000, 36.03600, True),
    ('Brentwood High School',                  -86.77500, 35.98500, True),
    ('Cool Springs / Franklin',                -86.81500, 35.93000, False),
    ('Downtown Nashville',                     -86.78440, 36.16270, False),
    ('Nolensville town center',                -86.66900, 35.95200, False),
]
poly = geom
for name, lon, lat, expect in tests:
    got = Point(lon, lat).within(poly)
    flag = 'OK ' if got == expect else 'MISMATCH'
    print('  [%s] %-40s inside=%-5s expected=%s' % (flag, name, got, expect))

print()
print('CRASH DENSITY CONTEXT')
csv = (r"C:/Users/kevin/OneDrive - City of Brentwood/Documents/COWORK_MASTER/projects/"
       r"purdue_ai/current_courses/MGMT59900_BigDataCloud/Portfolio_Project/Dataset/derived/"
       r"brentwood_crashes_classified.csv")
d = pd.read_csv(csv, low_memory=False)
inc = d[d['in_city'] == True]
print('  crashes in bbox      : %d' % len(d))
print('  crashes inside limits: %d' % len(inc))
print('  per year inside      : %.0f' % (len(inc) / 8.0))
print('  per sq mi per year   : %.1f' % (len(inc) / 8.0 / 42.31))
d['yr'] = pd.to_datetime(d['Start_Time'], errors='coerce', format='mixed').dt.year
print()
print('  inside-limits crashes by year:')
print(d[d['in_city'] == True].groupby('yr').size().to_string())
