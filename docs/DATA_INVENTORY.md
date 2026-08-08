# Data Inventory — Cloud-Based Traffic Safety Analytics

MGMT 59900 Portfolio Project | Group 15 | Kevin Blackburn
Last updated: August 8, 2026

Four independent data sources. Every one is either public or authoritative city
GIS, and every one is reproducible from the scripts in `scripts/`.

---

## 1. US Accidents (primary pipeline source)

| | |
|---|---|
| File | `data/raw/US_Accidents_March23.csv` (not committed, see README) |
| Size | 3,058,183,727 bytes (3.06 GB) |
| Rows | 7,728,394 across 46 columns, 49 states, Feb 2016 – Mar 2023 |
| Source | Kaggle, Sobhan Moosavi, *US Accidents (2016–2023)* |
| License | CC BY-NC-SA 4.0 |
| Obtained by | Manual download from Kaggle |
| Role | The dataset under test. Drives the AWS pipeline |

**Known limitation, measured:** contains 4.4% of the crashes police recorded in
Brentwood. Severity is a traffic-impact scale with no injury or fatality field.

---

## 2. City of Brentwood GIS (authoritative geography)

| | |
|---|---|
| Files | `data/gis/brentwood_city_limits.geojson` (351 KB, 1 polygon, 42.31 sq mi) |
| | `data/gis/brentwood_streets.geojson` (3.7 MB, 4,010 segments, 396.4 centerline mi) |
| Source | `maps.brentwoodtn.gov/arcgis/rest/services/` — AdministrativeAreas/2, Transportation/12 |
| Obtained by | `scripts/fetch_gis.py`, ArcGIS REST query, reprojected to EPSG:4326 |
| Snapshot date | August 8, 2026 |
| Role | Point-in-polygon city-limits test; nearest-centerline maintaining-agency join |

Key attributes used: `ACCEPTED` (city acceptance), `ROUTE_STAT` (INTERSTATE /
STATE_HIGHWAY / US_HIGHWAY), `CLASS` (functional class), `NAME`.

---

## 3. Nashville Area MPO crashes (completeness benchmark and analysis base)

| | |
|---|---|
| Files | `data/derived/mpo_crashes_brentwood_envelope.csv` (raw pull, 31,522 rows) |
| | `data/derived/mpo_crashes_unified.csv` (unified schema, 18 columns) |
| | `data/derived/mpo_field_availability.csv` (which fields exist in which layer) |
| Source | Greater Nashville Regional Council open data, `services3.arcgis.com/pXGyp7DHTIE4RXOJ` |
| Layers | `Crashes_2010_2019_MPO` (438,655 regionally) and `Crashes_MPO_2020` (56,346) |
| Obtained by | `scripts/fetch_mpo.py`, ArcGIS REST envelope query |
| Role | Police-reported ground truth. 9,837 crashes inside the corporate limits |

**Schema caution.** The two layers publish different attributes and were unified
without filling gaps:

- Both layers: `fatalities`, `non_motorists`, coordinates, timestamp
- 2010–2019 only: `truck_involved`
- 2020 only: `serious_injuries`, `pedestrian`, `bicycle`, `manner_of_collision`,
  `lighting`, `weather`, `first_harmful_event`, `crash_type`

So fatality and non-motorist trends span 2010–2020, while injury severity and
collision manner are a 2020 cross-section only.

**Coverage caution.** MPO records also ramp early (7 crashes in 2010, 40 in 2011),
so **2016–2019 is the only clean comparison window**, averaging 1,396 per year.

**Metadata caution.** The portal describes the 2010–2019 layer as "Fatal, Truck,
and Non-Motorized crashes." It is not. 96.9% of its rows carry none of those
flags, so it is all reported crashes with flags marking special categories.

---

## 4. NHTSA FARS (independent fatal-crash census)

| | |
|---|---|
| Files | `data/derived/fars_tn_2016_2022.csv` (7,480 TN fatal crashes) |
| | `data/derived/fars_tn.csv` (cleaned for Athena) |
| Source | `static.nhtsa.gov/nhtsa/downloads/FARS/{year}/National/` annual national CSV |
| Obtained by | `scripts/fetch_fars.py`, seven annual archives, `accident` table only |
| Role | Independent validation. 16 fatal crashes inside the corporate limits |

FARS and MPO independently agree on 16 fatal crashes, which corroborates both
the boundary polygon and the spatial join.

**Note:** the NHTSA CrashAPI returns HTTP 403 from this environment, so the static
annual archives were used instead. 2021 and 2022 files carry a UTF-8 BOM on the
first column name and must be read with `utf-8-sig`.

---

## Derived outputs

| File | Contents |
|---|---|
| `data/derived/brentwood_crashes_classified.csv` | 6,982 US Accidents rows in the Brentwood envelope with `in_city`, `agency`, matched segment, snap distance |
| `data/derived/us_accidents_brentwood_classified.csv` | Same, column names normalised for Athena |
| `data/derived/mpo_crashes_unified.csv` | Unified MPO schema |
| `data/derived/fars_tn.csv` | FARS cleaned for Athena |

---

## In the cloud

Bucket `s3://mgmt59900-blackburn-project` (us-east-1):

```
raw/              US_Accidents_March23.csv          3.06 GB
raw_mpo/          mpo_crashes_unified.csv           2.85 MB
                  mpo_field_availability.csv
raw_fars/         fars_tn.csv                       1.25 MB
raw_classified/   us_accidents_brentwood_classified.csv
curated/          Parquet, 388 partitions, 443 MB
curated_mpo/      Parquet, partitioned by crash_year
athena-results/   Athena query output
```

Glue database `crash_db`. DDL and analysis SQL in
`Final_Package/sql/final_project_queries.sql`.

---

## Reproducibility

Every non-manual source is re-fetchable:

```
scripts/fetch_gis.py      City of Brentwood ArcGIS REST
scripts/fetch_mpo.py      GNRC ArcGIS REST
scripts/fetch_fars.py     NHTSA static archives
scripts/spatial_join.py   point-in-polygon + nearest centerline
scripts/unify_mpo.py      two MPO layers into one schema
```

Only the 3.06 GB Kaggle file requires a manual download, because Kaggle needs an
authenticated session.
