# -*- coding: utf-8 -*-
"""US Accidents vs Nashville Area MPO police-reported crashes, Brentwood."""
import sys
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')
ROOT = (r"C:/Users/kevin/OneDrive - City of Brentwood/Documents/COWORK_MASTER/projects/"
        r"purdue_ai/current_courses/MGMT59900_BigDataCloud/Portfolio_Project")

mpo = pd.read_csv(ROOT + '/Dataset/mpo/mpo_crashes_brentwood_envelope.csv', low_memory=False)
mpo = mpo[mpo['in_city'] == True].copy()
mpo['year'] = pd.to_numeric(mpo['year'], errors='coerce').astype('Int64')

ua = pd.read_csv(ROOT + '/Dataset/derived/brentwood_crashes_classified.csv', low_memory=False)
ua = ua[ua['in_city'] == True].copy()
ua['year'] = pd.to_datetime(ua['Start_Time'], errors='coerce', format='mixed').dt.year.astype('Int64')

print('=' * 72)
print('COVERAGE: US Accidents vs MPO police-reported crashes, inside Brentwood')
print('=' * 72)
print('  %-6s %12s %12s %10s' % ('year', 'MPO', 'US Accidents', 'coverage'))
rows = []
for y in range(2016, 2021):
    m = int((mpo['year'] == y).sum())
    u = int((ua['year'] == y).sum())
    pct = (100.0 * u / m) if m else float('nan')
    rows.append((y, m, u, pct))
    print('  %-6d %12d %12d %9.1f%%' % (y, m, u, pct))
M = sum(r[1] for r in rows)
U = sum(r[2] for r in rows)
print('  %-6s %12d %12d %9.1f%%' % ('total', M, U, 100.0 * U / M))
print()
print('  The US Accidents dataset contains %.1f%% of the crashes the MPO recorded' % (100.0 * U / M))
print('  inside the Brentwood corporate limits over 2016-2020.')
print('  Missing: %d of %d crashes.' % (M - U, M))

print()
print('=' * 72)
print('WHAT THE MPO DATA ADDS: real injury severity')
print('=' * 72)
for col, label in [('NbrFatalit', 'fatalities'), ('SI_C', 'serious injuries'),
                   ('Ped', 'pedestrian involved'), ('Bike', 'bicycle involved'),
                   ('NbrNonMoto', 'non-motorist')]:
    if col in mpo.columns:
        s = pd.to_numeric(mpo[col], errors='coerce').fillna(0)
        print('  %-22s total=%6.0f   crashes with >0: %d' % (label, s.sum(), int((s > 0).sum())))

print()
print('  MPO crashes by year with a fatality:')
if 'NbrFatalit' in mpo.columns:
    f = mpo[pd.to_numeric(mpo['NbrFatalit'], errors='coerce').fillna(0) > 0]
    print(f.groupby('year').size().to_string())

print()
print('=' * 72)
print('SCALE OF THE CORRECTION')
print('=' * 72)
avg = mpo[mpo['year'].between(2016, 2019)].groupby('year').size().mean()
print('  MPO average, 2016-2019      : %.0f crashes per year in Brentwood' % avg)
print('  US Accidents average, same   : %.0f per year' % ua[ua['year'].between(2016, 2019)].groupby('year').size().mean())
print('  Ratio                        : %.0f to 1' % (avg / max(ua[ua['year'].between(2016, 2019)].groupby('year').size().mean(), 1)))
