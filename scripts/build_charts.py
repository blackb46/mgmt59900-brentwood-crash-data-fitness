# -*- coding: utf-8 -*-
"""Figures for the final report, all from the GIS-classified crash data."""
import os
import sys

import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
from shapely.geometry import Point

sys.stdout.reconfigure(encoding='utf-8')

ROOT = (r"C:/Users/kevin/OneDrive - City of Brentwood/Documents/COWORK_MASTER/projects/"
        r"purdue_ai/current_courses/MGMT59900_BigDataCloud/Portfolio_Project")
GIS, OUT = ROOT + '/Dataset/gis', ROOT + '/Final_Package/figures'
os.makedirs(OUT, exist_ok=True)

NAVY, INTER, STATE, CITY, MUTED = '#1D3557', '#C1272D', '#E08A1E', '#2E7D32', '#9AA7B4'
F = 'Arial'

d = pd.read_csv(ROOT + '/Dataset/derived/brentwood_crashes_classified.csv', low_memory=False)
ts = pd.to_datetime(d['Start_Time'], errors='coerce', format='mixed')
d['yr'], d['hr'] = ts.dt.year, ts.dt.hour
city = d[d['in_city'] == True].copy()
COL = {'TDOT interstate': INTER, 'TDOT state route': STATE,
       'City of Brentwood': CITY, 'Other / not accepted': MUTED}


def finish(ax, title, sub=None):
    ax.set_title(title, fontsize=12.5, fontweight='bold', color=NAVY, loc='left',
                 fontname=F, pad=14 if sub else 8)
    if sub:
        ax.text(0, 1.02, sub, transform=ax.transAxes, fontsize=8.6, color='#666666',
                fontname=F, va='bottom')
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    ax.tick_params(labelsize=8.5, colors='#555555')


# ---------------------------------------------------------- 1. jurisdiction
g = city.groupby('agency').size().sort_values(ascending=True)
fig, ax = plt.subplots(figsize=(8.4, 3.0), dpi=300)
bars = ax.barh(g.index, g.values, color=[COL.get(k, MUTED) for k in g.index], height=.62)
for b, v in zip(bars, g.values):
    ax.text(v + 8, b.get_y() + b.get_height() / 2, '%d  (%.1f%%)' % (v, 100 * v / len(city)),
            va='center', fontsize=9, color=NAVY, fontname=F)
ax.set_xlim(0, max(g.values) * 1.22)
ax.set_xlabel('Crashes', fontsize=9.5, color=NAVY, fontname=F)
finish(ax, 'Who maintains the roads where Brentwood crashes happen',
       '637 crashes inside the corporate limits, 2016-2023. 96.1 percent are on TDOT facilities.')
ax.xaxis.grid(True, color='#E8ECEF'); ax.set_axisbelow(True)
fig.savefig(OUT + '/fig_jurisdiction.png', bbox_inches='tight', facecolor='white')
plt.close(fig)

# ---------------------------------------------------------- 2. coverage
cy = city.groupby('yr').size()
fig, ax = plt.subplots(figsize=(8.4, 3.0), dpi=300)
cols = [MUTED if y == 2023 else NAVY for y in cy.index]
b = ax.bar(cy.index.astype(int), cy.values, color=cols, width=.66)
for r, v in zip(b, cy.values):
    ax.text(r.get_x() + r.get_width() / 2, v + 3, str(v), ha='center', fontsize=8.5,
            color=NAVY, fontname=F)
ax.annotate('2023 partial:\ndataset ends March', xy=(2023, 33), xytext=(2021.4, 96),
            fontsize=8.2, color='#666666', fontname=F,
            arrowprops=dict(arrowstyle='-|>', color='#888888', lw=1))
ax.set_ylim(0, 205)
ax.set_ylabel('Crashes recorded', fontsize=9.5, color=NAVY, fontname=F)
finish(ax, 'Recorded crashes grew 16-fold, which reflects coverage not risk',
       'Crashes inside the corporate limits by year. The source instruments highways progressively, so early years are sparse.')
ax.yaxis.grid(True, color='#E8ECEF'); ax.set_axisbelow(True)
fig.savefig(OUT + '/fig_coverage.png', bbox_inches='tight', facecolor='white')
plt.close(fig)

# ---------------------------------------------------------- 3. hour, TDOT
tdot = city[city['agency'].str.startswith('TDOT')]
hh = tdot.groupby('hr').size().reindex(range(24), fill_value=0)
fig, ax = plt.subplots(figsize=(8.8, 3.0), dpi=300)
cols = [INTER if 15 <= h <= 18 else (STATE if 6 <= h <= 9 else MUTED) for h in range(24)]
ax.bar(range(24), hh.values, color=cols, width=.8)
ax.annotate('17:00  %d crashes' % hh[17], xy=(17, hh[17]), xytext=(19.2, hh[17] - 4),
            fontsize=8.6, color=NAVY, fontname=F,
            arrowprops=dict(arrowstyle='-|>', color=NAVY, lw=1))
ax.set_xticks(range(24)); ax.set_xlim(-.7, 23.7)
ax.set_xlabel('Hour of day', fontsize=9.5, color=NAVY, fontname=F)
ax.set_ylabel('Crashes', fontsize=9.5, color=NAVY, fontname=F)
finish(ax, 'Crashes on TDOT facilities concentrate in the afternoon peak',
       'PM peak 15:00-18:00 holds 262 crashes (42.8%). AM peak 06:00-09:00 holds 143 (23.4%).')
ax.legend(handles=[Line2D([0], [0], color=INTER, lw=7, label='PM peak 15:00-18:00'),
                   Line2D([0], [0], color=STATE, lw=7, label='AM peak 06:00-09:00'),
                   Line2D([0], [0], color=MUTED, lw=7, label='All other hours')],
          fontsize=8, frameon=False, loc='upper left')
ax.yaxis.grid(True, color='#E8ECEF'); ax.set_axisbelow(True)
fig.savefig(OUT + '/fig_hour_tdot.png', bbox_inches='tight', facecolor='white')
plt.close(fig)

# ---------------------------------------------------------- 4. map
lim = gpd.read_file(GIS + '/brentwood_city_limits.geojson')
st = gpd.read_file(GIS + '/brentwood_streets.geojson')
pts = gpd.GeoDataFrame(city, geometry=[Point(x, y) for x, y in
                                       zip(city['Start_Lng'], city['Start_Lat'])], crs=4326)
fig, ax = plt.subplots(figsize=(7.0, 8.0), dpi=300)
st.plot(ax=ax, color='#D8DEE3', linewidth=.45, zorder=1)
st[st['ROUTE_STAT'].fillna('').str.strip() == 'INTERSTATE'].plot(
    ax=ax, color='#B9C2C9', linewidth=1.8, zorder=2)
lim.boundary.plot(ax=ax, color=NAVY, linewidth=1.6, zorder=3)
for k in ['TDOT interstate', 'TDOT state route', 'City of Brentwood']:
    s = pts[pts['agency'] == k]
    if len(s):
        s.plot(ax=ax, color=COL[k], markersize=9, alpha=.72, zorder=4,
               label='%s (%d)' % (k, len(s)))
ax.set_axis_off()
ax.set_title('Crash locations inside the Brentwood corporate limits',
             fontsize=13, fontweight='bold', color=NAVY, loc='left', fontname=F, pad=30)
ax.text(0, 1.004, '637 crashes, 2016-2023, classified by the maintaining agency of the nearest city centerline.',
        transform=ax.transAxes, fontsize=8.6, color='#666666', fontname=F, va='bottom')
ax.legend(fontsize=9, frameon=False, loc='lower left')
fig.savefig(OUT + '/fig_map.png', bbox_inches='tight', facecolor='white')
plt.close(fig)

# ---------------------------------------------------------- 5. filter error
fig, ax = plt.subplots(figsize=(8.4, 2.5), dpi=300)
cats = ['Correctly included\n(612)', 'Wrongly included\n(225)', 'Missed\n(25)']
vals, colors = [612, 225, 25], [CITY, INTER, STATE]
b = ax.barh([0], [612], color=CITY, height=.5, label='Correct')
ax.barh([0], [225], left=[612], color=INTER, height=.5)
ax.barh([0], [25], left=[837], color=STATE, height=.5)
ax.set_xlim(0, 900); ax.set_yticks([])
for x, w, t in [(306, 612, '612 correct'), (724, 225, '225 wrongly included'), (849, 25, '25 missed')]:
    ax.text(x, 0, t, ha='center', va='center', fontsize=9,
            color='white' if w > 100 else NAVY, fontweight='bold', fontname=F)
finish(ax, 'The name-based filter was wrong about 30 percent of the time',
       'County + city text filter returned 837 crashes. Point-in-polygon against the corporate limits returned 637.')
ax.set_xlabel('Crashes', fontsize=9.5, color=NAVY, fontname=F)
fig.savefig(OUT + '/fig_filter_error.png', bbox_inches='tight', facecolor='white')
plt.close(fig)

print('figures written to', OUT)
for f in sorted(os.listdir(OUT)):
    print('  ', f, '%.0f KB' % (os.path.getsize(OUT + '/' + f) / 1024))
