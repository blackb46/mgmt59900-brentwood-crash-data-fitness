# -*- coding: utf-8 -*-
"""GIS-only crash analysis for Brentwood.

Classification comes entirely from the City of Brentwood's authoritative GIS.
No manual street list is used anywhere in this script.
"""
import sys
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')
ROOT = (r"C:/Users/kevin/OneDrive - City of Brentwood/Documents/COWORK_MASTER/projects/"
        r"purdue_ai/current_courses/MGMT59900_BigDataCloud/Portfolio_Project")
d = pd.read_csv(ROOT + '/Dataset/derived/brentwood_crashes_classified.csv', low_memory=False)
ts = pd.to_datetime(d['Start_Time'], errors='coerce', format='mixed')
d['yr'], d['hr'] = ts.dt.year, ts.dt.hour
d['dow'] = ts.dt.day_name()
city = d[d['in_city'] == True].copy()
tdot = city[city['agency'].isin(['TDOT interstate', 'TDOT state route'])]
cty = city[city['agency'] == 'City of Brentwood']

H = lambda t: print('\n' + '=' * 70 + '\n' + t + '\n' + '=' * 70)

H('1. JURISDICTION OF CRASHES INSIDE THE CORPORATE LIMITS')
g = city.groupby('agency').agg(crashes=('ID', 'size'),
                               serious=('Severity', lambda s: int((s >= 3).sum())),
                               avg_sev=('Severity', 'mean')).sort_values('crashes', ascending=False)
g['share'] = (100 * g['crashes'] / len(city)).round(1)
g['avg_sev'] = g['avg_sev'].round(2)
print(g.to_string())
print('\n  TDOT combined: %d of %d  (%.1f%%)'
      % (len(tdot), len(city), 100 * len(tdot) / len(city)))

H('2. TDOT FACILITIES: WHERE THE CRASHES ARE  (advocacy targets)')
t = tdot.groupby(['NAME', 'ROUTE_STAT']).agg(
    crashes=('ID', 'size'),
    serious=('Severity', lambda s: int((s >= 3).sum())),
    avg_sev=('Severity', 'mean')).sort_values('crashes', ascending=False)
t['serious_pct'] = (100 * t['serious'] / t['crashes']).round(1)
t['avg_sev'] = t['avg_sev'].round(2)
print(t.head(14).to_string())

H('3. TDOT CRASHES BY YEAR  (trend for the funding case)')
py = tdot.groupby('yr').agg(crashes=('ID', 'size'),
                            serious=('Severity', lambda s: int((s >= 3).sum())))
print(py.to_string())

H('4. TDOT CRASHES BY HOUR  (peak exposure)')
hh = tdot.groupby('hr').size()
for h in range(24):
    n = int(hh.get(h, 0))
    print('  %02d:00  %4d  %s' % (h, n, '#' * int(n / 3)))
am, pm = int(hh.reindex(range(6, 10)).fillna(0).sum()), int(hh.reindex(range(15, 19)).fillna(0).sum())
print('\n  AM peak 06-09: %d (%.1f%%)   PM peak 15-18: %d (%.1f%%)'
      % (am, 100 * am / len(tdot), pm, 100 * pm / len(tdot)))

H('5. CONDITIONS ON TDOT FACILITIES')
print('  daylight vs dark:')
print(tdot.groupby('Sunrise_Sunset').size().to_string())
print('\n  top weather at time of crash:')
print(tdot.groupby('Weather_Condition').size().sort_values(ascending=False).head(8).to_string())
print('\n  roadway features present:')
for c in ['Junction', 'Crossing', 'Traffic_Signal', 'Stop']:
    if c in tdot.columns:
        print('    %-15s %d' % (c, int((tdot[c] == True).sum())))

H('6. CITY-MAINTAINED STREETS  (what the city itself controls)')
print('  %d crashes on %d distinct streets, %d serious'
      % (len(cty), cty['NAME'].nunique(), int((cty['Severity'] >= 3).sum())))
print(cty.groupby(['NAME', 'CLASS']).agg(
    crashes=('ID', 'size'), avg_sev=('Severity', 'mean')).round(2)
    .sort_values('crashes', ascending=False).to_string())

H('7. GIS CLASSIFICATION vs THE NAME-BASED FILTER')
old = d[(d['County'] == 'Williamson') & (d['City'] == 'Brentwood')]
o, n = set(old['ID']), set(city['ID'])
print('  name filter (county+city) : %d' % len(o))
print('  GIS point-in-polygon      : %d' % len(n))
print('  agree                     : %d' % len(o & n))
print('  filter wrongly included   : %d  (%.1f%% of its total)'
      % (len(o - n), 100 * len(o - n) / len(o)))
print('  filter missed             : %d' % len(n - o))
print('  net error rate            : %.1f%%' % (100 * (len(o - n) + len(n - o)) / len(o)))
print('\n  streets the filter wrongly included:')
print(d[d['ID'].isin(o - n)].groupby('Street').size().sort_values(ascending=False).head(8).to_string())
print('\n  where the missed ones were labeled:')
print(d[d['ID'].isin(n - o)].groupby(['County', 'City']).size().sort_values(ascending=False).to_string())

H('8. DATA COVERAGE LIMITATION')
cy = city.groupby('yr').size()
print(cy.to_string())
print('\n  2016 -> 2022 growth: %.1fx' % (cy.get(2022, 0) / max(cy.get(2016, 1), 1)))
print('  2022 is the most complete full year at %d crashes' % cy.get(2022, 0))
print('  2023 partial: dataset ends March 2023')
print('\n  functional class share of in-city crashes:')
fc = city.groupby('CLASS').size().sort_values(ascending=False)
for k, v in fc.items():
    print('    %-22s %4d  %5.1f%%' % (k, v, 100 * v / len(city)))
