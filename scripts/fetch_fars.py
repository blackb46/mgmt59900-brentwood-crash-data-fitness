# -*- coding: utf-8 -*-
"""Download NHTSA FARS annual national files, keep only the accident table,
filter to Tennessee, and save a single tidy CSV.

FARS is a census of fatal motor-vehicle crashes on public roads, compiled from
police reports. It is used here as an independent completeness benchmark
against the API-sourced US Accidents dataset.
Source: https://www.nhtsa.gov/research-data/fatality-analysis-reporting-system-fars
"""
import io
import os
import sys
import urllib.request
import zipfile

import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

ROOT = (r"C:/Users/kevin/OneDrive - City of Brentwood/Documents/COWORK_MASTER/projects/"
        r"purdue_ai/current_courses/MGMT59900_BigDataCloud/Portfolio_Project")
OUT = ROOT + '/Dataset/fars'
os.makedirs(OUT, exist_ok=True)

TN = 47
YEARS = range(2016, 2023)          # 2023 FARS not final at time of writing
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
KEEP = ['STATE', 'ST_CASE', 'COUNTY', 'COUNTYNAME', 'CITY', 'CITYNAME', 'YEAR',
        'MONTH', 'DAY', 'HOUR', 'MINUTE', 'LATITUDE', 'LONGITUD', 'FATALS',
        'ROUTE', 'ROUTENAME', 'TWAY_ID', 'TWAY_ID2', 'FUNC_SYS', 'FUNC_SYSNAME',
        'HARM_EV', 'HARM_EVNAME', 'LGT_COND', 'LGT_CONDNAME', 'WEATHERNAME']

frames = []
for y in YEARS:
    url = ('https://static.nhtsa.gov/nhtsa/downloads/FARS/%d/National/'
           'FARS%dNationalCSV.zip' % (y, y))
    print('%d  downloading...' % y, flush=True)
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=300) as r:
            blob = r.read()
        print('     %.1f MB' % (len(blob) / 1048576), flush=True)
        z = zipfile.ZipFile(io.BytesIO(blob))
        name = next((n for n in z.namelist()
                     if os.path.basename(n).lower() in ('accident.csv',)), None)
        if not name:
            print('     accident.csv not found; members:', z.namelist()[:6], flush=True)
            continue
        # 2021+ files carry a UTF-8 BOM on the first column name
        try:
            with z.open(name) as fh:
                df = pd.read_csv(fh, encoding='utf-8-sig', low_memory=False)
        except UnicodeDecodeError:
            with z.open(name) as fh:
                df = pd.read_csv(fh, encoding='latin-1', low_memory=False)
        df.columns = [c.replace('﻿', '').strip().upper() for c in df.columns]
        tn = df[df['STATE'] == TN].copy()
        tn = tn[[c for c in KEEP if c in tn.columns]]
        tn['SRC_YEAR'] = y
        frames.append(tn)
        print('     TN fatal crashes: %d  (national %d)' % (len(tn), len(df)), flush=True)
    except Exception as e:
        print('     FAILED %s: %s' % (type(e).__name__, str(e)[:110]), flush=True)

if not frames:
    raise SystemExit('no FARS data retrieved')

fars = pd.concat(frames, ignore_index=True)
# FARS codes missing coordinates as 77.7777 / 88.8888 / 99.9999
for c, bad in (('LATITUDE', (77.7777, 88.8888, 99.9999)),
               ('LONGITUD', (777.7777, 888.8888, 999.9999))):
    if c in fars.columns:
        fars.loc[fars[c].isin(bad), c] = None
if 'LONGITUD' in fars.columns:
    fars.loc[fars['LONGITUD'] > 0, 'LONGITUD'] *= -1     # west longitudes

p = OUT + '/fars_tn_2016_2022.csv'
fars.to_csv(p, index=False)
print()
print('saved %s  rows=%d  (%.1f MB)' % (os.path.basename(p), len(fars),
                                        os.path.getsize(p) / 1048576))
print('  years        :', sorted(fars['SRC_YEAR'].unique()))
print('  usable coords: %d of %d' % (fars['LATITUDE'].notna().sum(), len(fars)))
if 'COUNTYNAME' in fars.columns:
    w = fars[fars['COUNTYNAME'].astype(str).str.upper().str.contains('WILLIAMSON', na=False)]
    print('  Williamson County fatal crashes: %d' % len(w))
    print('  Williamson fatalities          : %d' % int(w['FATALS'].sum()))
