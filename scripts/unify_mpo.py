# -*- coding: utf-8 -*-
"""Unify the two GNRC MPO crash layers into one schema.

The 2010-2019 layer and the 2020 layer publish different attributes. Rather
than silently filling gaps, fields absent from a layer stay null and the
coverage is documented, because it constrains what can be analyzed for which
years.
"""
import os
import sys

import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')
ROOT = (r"C:/Users/kevin/OneDrive - City of Brentwood/Documents/COWORK_MASTER/projects/"
        r"purdue_ai/current_courses/MGMT59900_BigDataCloud/Portfolio_Project")
SRC = ROOT + '/Dataset/mpo/mpo_crashes_brentwood_envelope.csv'
OUT = ROOT + '/Dataset/derived'
os.makedirs(OUT, exist_ok=True)

d = pd.read_csv(SRC, low_memory=False)
d['collision_ts'] = pd.to_datetime(d['CollisionD'], errors='coerce')

num = lambda c: pd.to_numeric(d[c], errors='coerce') if c in d.columns else pd.Series(
    [pd.NA] * len(d), dtype='Float64')
txt = lambda c: d[c].astype('string').str.strip() if c in d.columns else pd.Series(
    [pd.NA] * len(d), dtype='string')

u = pd.DataFrame({
    'record_no':            txt('MstrRecNbr'),
    'source_layer':         txt('src_layer'),
    'collision_ts':         d['collision_ts'],
    'crash_year':           pd.to_numeric(d['year'], errors='coerce').astype('Int64'),
    'latitude':             num('lat'),
    'longitude':            num('lon'),
    'in_city':              d['in_city'].astype(str).str.lower().isin(['true', '1']),
    # present in both layers
    'fatalities':           num('NbrFatalit').astype('Int64'),
    'non_motorists':        num('NbrNonMoto').astype('Int64'),
    # 2010-2019 only
    'truck_involved':       num('Truck_C').astype('Int64'),
    # 2020 only
    'serious_injuries':     num('SI_C').astype('Int64'),
    'pedestrian':           num('Ped').astype('Int64'),
    'bicycle':              num('Bike').astype('Int64'),
    'crash_type':           txt('Crash_Type'),
    'manner_of_collision':  txt('Manner_of_'),
    'lighting':             txt('Lighting_C'),
    'weather':              txt('Weather'),
    'first_harmful_event':  txt('First_Harm'),
})
u = u[u['latitude'].notna() & u['longitude'].notna() & u['crash_year'].notna()]
u = u.sort_values(['crash_year', 'collision_ts']).reset_index(drop=True)

p = OUT + '/mpo_crashes_unified.csv'
u.to_csv(p, index=False)
print('unified MPO: %d rows, %d columns -> %s (%.1f MB)'
      % (len(u), u.shape[1], os.path.basename(p), os.path.getsize(p) / 1048576))
print('  years %d-%d | inside city limits %d'
      % (u['crash_year'].min(), u['crash_year'].max(), int(u['in_city'].sum())))

print()
print('FIELD AVAILABILITY BY SOURCE LAYER  (non-null counts)')
print('  %-22s %14s %14s' % ('field', '2010-2019', '2020'))
a = u[u['source_layer'] == 'Crashes_2010_2019_MPO']
b = u[u['source_layer'] == 'Crashes_MPO_2020']
matrix = []
for c in u.columns:
    if c in ('record_no', 'source_layer'):
        continue
    na, nb = int(a[c].notna().sum()), int(b[c].notna().sum())
    flag = '' if (na and nb) else ('   <- one layer only' if (na or nb) else '')
    print('  %-22s %14d %14d%s' % (c, na, nb, flag))
    matrix.append({'field': c, 'rows_2010_2019': na, 'rows_2020': nb,
                   'both_layers': bool(na and nb)})
pd.DataFrame(matrix).to_csv(OUT + '/mpo_field_availability.csv', index=False)

print()
print('ANALYTICAL CONSEQUENCE')
print('  fatalities and non-motorist counts span 2010-2020 and support trend analysis.')
print('  serious injuries, pedestrian, bicycle, manner of collision, lighting and')
print('  weather exist for 2020 only, so those are single-year cross-sections.')
print()
city = u[u['in_city']]
print('IN-CITY TOTALS BY YEAR')
g = city.groupby('crash_year').agg(crashes=('record_no', 'size'),
                                   fatalities=('fatalities', 'sum'),
                                   non_motorists=('non_motorists', 'sum'))
print(g.to_string())
