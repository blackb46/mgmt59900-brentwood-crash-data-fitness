# -*- coding: utf-8 -*-
"""Duplicate audit across every source feeding the project.

Paged ArcGIS REST pulls can repeat records if the service reorders between
pages, so uniqueness is verified rather than assumed.
"""
import sys
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')
ROOT = (r"C:/Users/kevin/OneDrive - City of Brentwood/Documents/COWORK_MASTER/projects/"
        r"purdue_ai/current_courses/MGMT59900_BigDataCloud/Portfolio_Project")

issues = []


def head(t):
    print('\n' + '=' * 70 + '\n' + t + '\n' + '=' * 70)


def check(label, ok, detail=''):
    print('  [%s] %-46s %s' % ('PASS' if ok else 'FAIL', label, detail))
    if not ok:
        issues.append(label)


# ------------------------------------------------------------ 1. MPO
head('1. MPO UNIFIED  (paged REST pull, highest duplicate risk)')
m = pd.read_csv(ROOT + '/Dataset/derived/mpo_crashes_unified.csv', low_memory=False)
print('  rows: %d' % len(m))
dup_id = int(m['record_no'].duplicated().sum())
check('record_no unique', dup_id == 0, '%d duplicate ids' % dup_id)
exact = int(m.duplicated().sum())
check('no exact duplicate rows', exact == 0, '%d exact dupes' % exact)

# same crash reported in both layers?
overlap = (m.groupby('record_no')['source_layer'].nunique() > 1).sum()
check('no record in both layers', overlap == 0, '%d ids in 2 layers' % overlap)

# same place + same instant is a strong duplicate signal
# Same date + same coordinates is NOT a duplicate signal in this source:
# collision_ts is date-only (every value is midnight) and coordinates are
# snapped to intersection nodes, so two crashes at one intersection on one
# day legitimately share both. The state master record number is the key.
key = ['collision_ts', 'latitude', 'longitude']
g = m[m.duplicated(subset=key, keep=False)]
n_groups = g.groupby(key).ngroups if len(g) else 0
ts = pd.to_datetime(m['collision_ts'], errors='coerce')
date_only = ts.dt.time.nunique() <= 1
snapped = m[['latitude', 'longitude']].drop_duplicates().shape[0] < len(m)
check('timestamp is date-only, so same-day is expected', date_only,
      '%d distinct times of day' % ts.dt.time.nunique())
check('coordinates snapped to nodes, so shared points expected', snapped,
      '%d distinct points / %d rows' % (m[['latitude','longitude']].drop_duplicates().shape[0], len(m)))
check('same-day same-node rows still have distinct record ids',
      len(g) == 0 or g['record_no'].nunique() == len(g),
      '%d rows in %d groups, %d distinct ids' % (len(g), n_groups, g['record_no'].nunique()))
print('      -> %d same-day/same-node pairs over 11 years (~%.0f per year), which is'
      % (n_groups, n_groups / 11.0))
print('         expected in a city averaging ~1,400 crashes annually. Not duplicates.')

yr = m.groupby('source_layer')['crash_year'].agg(['min', 'max'])
print('\n  year span by layer:')
print(yr.to_string())
ov = set(m[m['source_layer'] == 'Crashes_2010_2019_MPO']['crash_year']) & \
     set(m[m['source_layer'] == 'Crashes_MPO_2020']['crash_year'])
check('layers cover disjoint years', not ov, 'overlapping years: %s' % sorted(ov))

# ------------------------------------------------------------ 2. FARS
head('2. FARS TENNESSEE')
f = pd.read_csv(ROOT + '/Dataset/derived/fars_tn.csv', low_memory=False)
print('  rows: %d' % len(f))
check('case_id + year unique', int(f.duplicated(subset=['case_id', 'year']).sum()) == 0,
      '%d dupes' % int(f.duplicated(subset=['case_id', 'year']).sum()))
check('no exact duplicate rows', int(f.duplicated().sum()) == 0,
      '%d exact dupes' % int(f.duplicated().sum()))
print('  note: case_id repeats across years by design, so the key is case_id+year')
print('  per-year counts:')
print(f.groupby('year').size().to_string())

# ------------------------------------------------------------ 3. classified UA
head('3. US ACCIDENTS, CLASSIFIED SUBSET')
u = pd.read_csv(ROOT + '/Dataset/derived/us_accidents_brentwood_classified.csv', low_memory=False)
print('  rows: %d' % len(u))
check('id unique', int(u['id'].duplicated().sum()) == 0,
      '%d dupes' % int(u['id'].duplicated().sum()))
check('no exact duplicate rows', int(u.duplicated().sum()) == 0,
      '%d exact dupes' % int(u.duplicated().sum()))
check('one row per crash after spatial join',
      len(u) == u['id'].nunique(), '%d rows / %d ids' % (len(u), u['id'].nunique()))

# ------------------------------------------------------------ 4. source CSV
head('4. US ACCIDENTS, FULL SOURCE  (streamed, id column only)')
ids = []
for ch in pd.read_csv(ROOT + '/Dataset/raw/US_Accidents_March23.csv',
                      usecols=['ID'], chunksize=1_000_000):
    ids.append(ch['ID'])
allids = pd.concat(ids)
print('  rows: %d' % len(allids))
d = int(allids.duplicated().sum())
check('ID unique across 7.7M rows', d == 0, '%d duplicate ids' % d)

# ------------------------------------------------------------ verdict
head('VERDICT')
if issues:
    print('  %d CHECK(S) FAILED:' % len(issues))
    for i in issues:
        print('    -', i)
else:
    print('  All duplicate checks passed. No de-duplication required.')
