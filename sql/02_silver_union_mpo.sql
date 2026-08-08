-- ============================================================================
-- MGMT 59900 Final Project  |  Group 15  |  Kevin Blackburn
-- SILVER LAYER: reconcile the two GNRC MPO crash layers
--
-- The two published layers carry different attributes. Both are landed in the
-- bronze zone exactly as delivered, and the reconciliation happens here in SQL
-- so the transformation is visible and reviewable rather than hidden in a
-- local script.
--
--   raw_mpo/mpo_2010_2019/   28,590 rows, 15 columns
--   raw_mpo/mpo_2020/         2,932 rows, 19 columns
--
-- Fields a layer does not publish stay NULL. They are not imputed, because a
-- missing attribute and a zero value mean different things.
-- ============================================================================


-- ---------------------------------------------------------------- bronze
DROP TABLE IF EXISTS crash_db.mpo_2010_2019_raw;
CREATE EXTERNAL TABLE crash_db.mpo_2010_2019_raw (
  `fid` string, `mstrrecnbr` string, `countystat` string, `collisiond` string,
  `year` string, `nbrfatalit` string, `nbrnonmoto` string, `commercial` string,
  `latdecimal` string, `longdecima` string, `fatal_c` string, `nonmotor_c` string,
  `truck_c` string, `mod_date` string, `mod_by` string
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES ('separatorChar'=',', 'quoteChar'='"')
STORED AS TEXTFILE
LOCATION 's3://mgmt59900-blackburn-project/raw_mpo/mpo_2010_2019/'
TBLPROPERTIES ('skip.header.line.count'='1');


DROP TABLE IF EXISTS crash_db.mpo_2020_raw;
CREATE EXTERNAL TABLE crash_db.mpo_2020_raw (
  `fid` string, `mstrrecnbr` string, `collisiond` string, `nbrfatalit` string,
  `nbrnonmoto` string, `latdecimal` string, `longdecima` string, `objectid` string,
  `county` string, `crash` string, `crash_type` string, `lighting_c` string,
  `manner_of` string, `weather` string, `first_harm` string, `fatalc` string,
  `si_c` string, `ped` string, `bike` string
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES ('separatorChar'=',', 'quoteChar'='"')
STORED AS TEXTFILE
LOCATION 's3://mgmt59900-blackburn-project/raw_mpo/mpo_2020/'
TBLPROPERTIES ('skip.header.line.count'='1');


-- ---------------------------------------------------------------- sanity
-- Confirm both bronze tables read before unioning them.
SELECT 'mpo_2010_2019' AS layer, COUNT(*) AS row_count FROM crash_db.mpo_2010_2019_raw
UNION ALL
SELECT 'mpo_2020', COUNT(*) FROM crash_db.mpo_2020_raw;
-- expect 28,590 and 2,932


-- ---------------------------------------------------------------- silver
-- Conform both layers onto one schema and write partitioned Parquet.
-- 11 distinct years, well inside the 100-partition CTAS limit.
DROP TABLE IF EXISTS crash_db.mpo_curated;
CREATE TABLE crash_db.mpo_curated
WITH (
  format = 'PARQUET',
  parquet_compression = 'SNAPPY',
  external_location = 's3://mgmt59900-blackburn-project/curated_mpo/',
  partitioned_by = ARRAY['crash_year']
) AS
WITH unified AS (

  -- 2010-2019: publishes truck involvement, does not publish injury detail
  SELECT
    mstrrecnbr                                            AS record_no,
    'mpo_2010_2019'                                       AS source_layer,
    CAST(date_parse(collisiond, '%Y-%m-%d') AS DATE)      AS collision_date,
    CAST(latdecimal AS DOUBLE)                            AS latitude,
    CAST(longdecima AS DOUBLE)                            AS longitude,
    CAST(COALESCE(NULLIF(nbrfatalit,''),'0') AS INTEGER)  AS fatalities,
    CAST(COALESCE(NULLIF(nbrnonmoto,''),'0') AS INTEGER)  AS non_motorists,
    -- GNRC publishes these flags as '0.0'/'1.0', so the double cast is required
    CAST(CAST(COALESCE(NULLIF(truck_c,''),'0') AS DOUBLE) AS INTEGER)
                                                          AS truck_involved,
    CAST(NULL AS INTEGER)                                 AS serious_injuries,
    CAST(NULL AS INTEGER)                                 AS pedestrian,
    CAST(NULL AS INTEGER)                                 AS bicycle,
    CAST(NULL AS VARCHAR)                                 AS crash_type,
    CAST(NULL AS VARCHAR)                                 AS manner_of_collision,
    CAST(NULL AS VARCHAR)                                 AS lighting,
    CAST(NULL AS VARCHAR)                                 AS weather,
    CAST(NULL AS VARCHAR)                                 AS first_harmful_event,
    CAST(CAST("year" AS DOUBLE) AS INTEGER)               AS crash_year
  FROM crash_db.mpo_2010_2019_raw
  WHERE latdecimal <> '' AND longdecima <> '' AND collisiond <> ''

  UNION ALL

  -- 2020: publishes injury detail and collision circumstances, no truck flag.
  -- No year column, so it is derived from the collision date.
  SELECT
    mstrrecnbr                                            AS record_no,
    'mpo_2020'                                            AS source_layer,
    CAST(date_parse(collisiond, '%Y-%m-%d') AS DATE)      AS collision_date,
    CAST(latdecimal AS DOUBLE)                            AS latitude,
    CAST(longdecima AS DOUBLE)                            AS longitude,
    CAST(COALESCE(NULLIF(nbrfatalit,''),'0') AS INTEGER)  AS fatalities,
    CAST(COALESCE(NULLIF(nbrnonmoto,''),'0') AS INTEGER)  AS non_motorists,
    CAST(NULL AS INTEGER)                                 AS truck_involved,
    -- same '0.0'/'1.0' encoding as the truck flag in the other layer
    CAST(CAST(COALESCE(NULLIF(si_c,''),'0') AS DOUBLE) AS INTEGER)
                                                          AS serious_injuries,
    CAST(CAST(COALESCE(NULLIF(ped,''),'0')  AS DOUBLE) AS INTEGER)
                                                          AS pedestrian,
    CAST(CAST(COALESCE(NULLIF(bike,''),'0') AS DOUBLE) AS INTEGER)
                                                          AS bicycle,
    NULLIF(crash_type,'')                                 AS crash_type,
    NULLIF(manner_of,'')                                  AS manner_of_collision,
    NULLIF(lighting_c,'')                                 AS lighting,
    NULLIF(weather,'')                                    AS weather,
    NULLIF(first_harm,'')                                 AS first_harmful_event,
    year(date_parse(collisiond, '%Y-%m-%d'))              AS crash_year
  FROM crash_db.mpo_2020_raw
  WHERE latdecimal <> '' AND longdecima <> '' AND collisiond <> ''
)
SELECT * FROM unified;


-- ---------------------------------------------------------------- validate
-- 1. Row count must reconcile against the two bronze tables.
SELECT source_layer, COUNT(*) AS row_count, MIN(crash_year) AS first_yr, MAX(crash_year) AS last_yr
FROM crash_db.mpo_curated
GROUP BY source_layer;

-- 2. No duplicate master record numbers, within or across layers.
SELECT COUNT(*) AS total_rows,
       COUNT(DISTINCT record_no) AS distinct_records,
       COUNT(*) - COUNT(DISTINCT record_no) AS duplicates
FROM crash_db.mpo_curated;
-- expect duplicates = 0

-- 3. Field availability, which constrains what can be analysed for which years.
SELECT source_layer,
       COUNT(*)                        AS row_count,
       COUNT(truck_involved)           AS has_truck_flag,
       COUNT(serious_injuries)         AS has_serious_injury,
       COUNT(manner_of_collision)      AS has_manner,
       COUNT(weather)                  AS has_weather
FROM crash_db.mpo_curated
GROUP BY source_layer;
-- expect the 2010-2019 layer to have the truck flag only, and 2020 the rest


-- ---------------------------------------------------------------- geo, in Athena
-- Point-in-polygon against the Brentwood corporate limits, done natively in
-- Athena rather than locally. The boundary is stored as a single WKT string.
DROP TABLE IF EXISTS crash_db.brentwood_limits_wkt;
CREATE EXTERNAL TABLE crash_db.brentwood_limits_wkt (`name` string, `wkt` string)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES ('separatorChar'=',', 'quoteChar'='"')
STORED AS TEXTFILE
LOCATION 's3://mgmt59900-blackburn-project/raw_gis/'
TBLPROPERTIES ('skip.header.line.count'='1');

-- Crashes inside the corporate limits, computed in the cloud.
SELECT c.crash_year,
       COUNT(*) AS crashes_in_city
FROM crash_db.mpo_curated c
CROSS JOIN crash_db.brentwood_limits_wkt b
WHERE ST_Contains(ST_GeometryFromText(b.wkt), ST_Point(c.longitude, c.latitude))
GROUP BY c.crash_year
ORDER BY c.crash_year;
-- should match the local geopandas result: 9,837 in-city rows across 2010-2020
