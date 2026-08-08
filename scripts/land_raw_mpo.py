# -*- coding: utf-8 -*-
"""Land the two GNRC MPO layers in the bronze zone as delivered.

Each layer keeps its own columns exactly as the service published them. The
schemas differ, and reconciling them is deliberately left to Athena so the
transformation is visible in SQL rather than hidden in a local script.
"""
import os
import re
import sys

import boto3
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')
ROOT = (r"C:/Users/kevin/OneDrive - City of Brentwood/Documents/COWORK_MASTER/projects/"
        r"purdue_ai/current_courses/MGMT59900_BigDataCloud/Portfolio_Project")
BRONZE = ROOT + '/Dataset/mpo/bronze'
os.makedirs(BRONZE, exist_ok=True)
BUCKET = 'mgmt59900-blackburn-project'

src = pd.read_csv(ROOT + '/Dataset/mpo/mpo_crashes_brentwood_envelope.csv', low_memory=False)

# columns the fetch added; everything else is as the service delivered it
ADDED = {'lon', 'lat', 'src_layer', 'year', 'in_city'}

out = {}
for layer, key in [('Crashes_2010_2019_MPO', 'mpo_2010_2019'),
                   ('Crashes_MPO_2020', 'mpo_2020')]:
    s = src[src['src_layer'] == layer].copy()
    # keep only columns this layer actually publishes
    cols = [c for c in s.columns if c not in ADDED and s[c].notna().any()]
    s = s[cols]
    s.columns = [re.sub(r'[^0-9a-zA-Z]+', '_', c).strip('_').lower() for c in s.columns]
    p = os.path.join(BRONZE, key + '.csv')
    s.to_csv(p, index=False)
    out[key] = (p, len(s), list(s.columns))
    print('%-14s %6d rows  %2d cols  -> %s (%.2f MB)'
          % (key, len(s), s.shape[1], os.path.basename(p), os.path.getsize(p) / 1048576))
    print('   columns: %s' % ', '.join(s.columns))
    print()

session = boto3.Session(profile_name='mgmt59900')
s3 = session.client('s3', region_name='us-east-1')
s3.head_bucket(Bucket=BUCKET)

# clear the previously-unified object so bronze holds only as-delivered data
for stale in ['raw_mpo/mpo_crashes_unified.csv', 'raw_mpo/mpo_field_availability.csv']:
    try:
        s3.delete_object(Bucket=BUCKET, Key=stale)
        print('removed stale object', stale)
    except Exception as e:
        print('skip', stale, e)

for key, (p, n, _) in out.items():
    dest = 'raw_mpo/%s/%s.csv' % (key, key)
    s3.upload_file(p, BUCKET, dest)
    print('uploaded %-40s %6d rows  %.2f MB' % (dest, n, os.path.getsize(p) / 1048576))

print()
print('bronze zone now:')
r = s3.list_objects_v2(Bucket=BUCKET, Prefix='raw_mpo/')
for o in r.get('Contents', []):
    print('   %-46s %8.2f MB' % (o['Key'], o['Size'] / 1048576))
