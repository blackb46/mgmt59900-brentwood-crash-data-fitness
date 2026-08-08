-- ============================================================================
-- MGMT 59900 Final Project  |  Group 15  |  Kevin Blackburn
-- Athena DDL and analysis SQL, database crash_db, region us-east-1
--
-- Four sources land in the same S3 bucket and are queried through the same
-- Athena catalog, which is the point: the architecture generalizes.
--
--   raw/             US Accidents 2016-2023, 7,728,394 rows, 3.06 GB
--   raw_mpo/         Nashville Area MPO police-reported crashes (GNRC open data)
--   raw_fars/        NHTSA FARS Tennessee fatal crashes 2016-2022
--   raw_classified/  US Accidents rows classified by Brentwood GIS
--   raw_gis/         City of Brentwood corporate limits polygon as WKT
--
-- All external tables are declared as string and cast on read. The OpenCSV
-- SerDe does not type columns, and casting explicitly keeps the intent visible.
-- ============================================================================


-- ===================== 1. EXTERNAL TABLES ==========================

DROP TABLE IF EXISTS crash_db.mpo_raw;
CREATE EXTERNAL TABLE crash_db.mpo_raw (
  `record_no` string,
  `source_layer` string,
  `collision_ts` string,
  `crash_year` string,
  `latitude` string,
  `longitude` string,
  `in_city` string,
  `fatalities` string,
  `non_motorists` string,
  `truck_involved` string,
  `serious_injuries` string,
  `pedestrian` string,
  `bicycle` string,
  `crash_type` string,
  `manner_of_collision` string,
  `lighting` string,
  `weather` string,
  `first_harmful_event` string
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES ('separatorChar'=',', 'quoteChar'='"')
STORED AS TEXTFILE
LOCATION 's3://mgmt59900-blackburn-project/raw_mpo/'
TBLPROPERTIES ('skip.header.line.count'='1');


DROP TABLE IF EXISTS crash_db.fars_raw;
CREATE EXTERNAL TABLE crash_db.fars_raw (
  `case_id` string,
  `year` string,
  `year.1` string,
  `month` string,
  `day` string,
  `hour` string,
  `minute` string,
  `county` string,
  `county_name` string,
  `city` string,
  `city_name` string,
  `latitude` string,
  `longitude` string,
  `fatalities` string,
  `route_type` string,
  `roadway` string,
  `functional_system` string,
  `first_harmful_event` string,
  `lighting` string,
  `weather` string
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES ('separatorChar'=',', 'quoteChar'='"')
STORED AS TEXTFILE
LOCATION 's3://mgmt59900-blackburn-project/raw_fars/'
TBLPROPERTIES ('skip.header.line.count'='1');


DROP TABLE IF EXISTS crash_db.ua_classified_raw;
CREATE EXTERNAL TABLE crash_db.ua_classified_raw (
  `id` string,
  `severity` string,
  `start_time` string,
  `start_lat` string,
  `start_lng` string,
  `street` string,
  `city` string,
  `county` string,
  `zipcode` string,
  `sunrise_sunset` string,
  `weather_condition` string,
  `junction` string,
  `crossing` string,
  `traffic_signal` string,
  `stop` string,
  `in_city` string,
  `agency` string,
  `name` string,
  `class` string,
  `route_no` string,
  `route_stat` string,
  `accepted` string,
  `spdlimit` string,
  `lanes` string,
  `dist_ft` string,
  `name_match` string
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES ('separatorChar'=',', 'quoteChar'='"')
STORED AS TEXTFILE
LOCATION 's3://mgmt59900-blackburn-project/raw_classified/'
TBLPROPERTIES ('skip.header.line.count'='1');



-- ===================== 2. CURATED MPO TABLE ==========================
-- Same CTAS pattern used for the 7.7M-row source, applied to the MPO extract.
-- Only 31,522 rows, so this is about consistency of method, not scale.

DROP TABLE IF EXISTS crash_db.mpo_curated;
CREATE TABLE crash_db.mpo_curated
WITH (
  format = 'PARQUET',
  parquet_compression = 'SNAPPY',
  external_location = 's3://mgmt59900-blackburn-project/curated_mpo/',
  partitioned_by = ARRAY['crash_year']
) AS
SELECT
  record_no,
  CAST(latitude  AS DOUBLE)                    AS latitude,
  CAST(longitude AS DOUBLE)                    AS longitude,
  CAST(COALESCE(NULLIF(fatalities,''),'0') AS INTEGER)        AS fatalities,
  CAST(COALESCE(NULLIF(serious_injuries,''),'0') AS INTEGER) AS serious_injuries,
  CAST(COALESCE(NULLIF(non_motorists,''),'0') AS INTEGER)     AS non_motorists,
  CAST(COALESCE(NULLIF(truck_involved,''),'0') AS INTEGER)    AS truck_involved,
  CAST(COALESCE(NULLIF(ped,''),'0') AS INTEGER)              AS ped,
  CAST(COALESCE(NULLIF(bike,''),'0') AS INTEGER)             AS bike,
  manner_of_collision,
  lighting,
  weather,
  first_harmful_event,
  crash_type,
  lower(in_city) = 'true'                      AS in_city,
  source_layer,
  CAST(crash_year AS INTEGER)                  AS crash_year
FROM crash_db.mpo_raw
WHERE crash_year IS NOT NULL AND crash_year <> '';


-- ===================== 3. THE HEADLINE: COVERAGE ==========================
-- How much of Brentwood's actual crash experience does the popular open
-- dataset contain? Expected: about 4.4 percent.

WITH mpo AS (
  SELECT crash_year AS yr, COUNT(*) AS mpo_crashes
  FROM crash_db.mpo_curated
  WHERE in_city AND crash_year BETWEEN 2016 AND 2020
  GROUP BY crash_year
),
ua AS (
  SELECT year(from_iso8601_timestamp(replace(start_time,' ','T'))) AS yr,
         COUNT(*) AS ua_crashes
  FROM crash_db.ua_classified_raw
  WHERE lower(in_city) = 'true'
  GROUP BY 1
)
SELECT mpo.yr,
       mpo.mpo_crashes,
       COALESCE(ua.ua_crashes, 0)                                   AS ua_crashes,
       ROUND(100.0 * COALESCE(ua.ua_crashes,0) / mpo.mpo_crashes,1) AS coverage_pct
FROM mpo LEFT JOIN ua ON ua.yr = mpo.yr
ORDER BY mpo.yr;


-- ===================== 4. JURISDICTION OF THE BURDEN ==========================
-- Who maintains the roads where crashes happen inside the corporate limits.

SELECT agency,
       COUNT(*)                                                  AS crashes,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)        AS pct
FROM crash_db.ua_classified_raw
WHERE lower(in_city) = 'true'
GROUP BY agency
ORDER BY crashes DESC;


-- ===================== 5. MPO SEVERITY, WHICH THE OPEN DATA LACKS =============

SELECT crash_year,
       COUNT(*)                AS crashes,
       SUM(fatalities)         AS fatalities,
       SUM(serious_injuries)   AS serious_injuries,
       SUM(non_motorists)      AS non_motorists,
       SUM(ped)                AS pedestrian_involved
FROM crash_db.mpo_curated
WHERE in_city
GROUP BY crash_year
ORDER BY crash_year;


-- ===================== 6. MANNER OF COLLISION ==========================

SELECT manner_of_collision,
       COUNT(*)                                           AS crashes,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
FROM crash_db.mpo_curated
WHERE in_city AND manner_of_collision IS NOT NULL AND manner_of_collision <> ''
GROUP BY manner_of_collision
ORDER BY crashes DESC
LIMIT 12;


-- ===================== 7. FARS CROSS-VALIDATION ==========================
-- Fatal crashes inside the Brentwood bounding box, independent of the MPO.

SELECT year,
       COUNT(*)              AS fatal_crashes,
       SUM(CAST(fatalities AS INTEGER)) AS fatalities
FROM crash_db.fars_raw
WHERE CAST(latitude  AS DOUBLE) BETWEEN 35.932 AND 36.045
  AND CAST(longitude AS DOUBLE) BETWEEN -86.870 AND -86.686
GROUP BY year
ORDER BY year;


-- ===================== 8. COST EVIDENCE, RERUN FOR THE REPORT =================
-- Same business question, raw CSV versus partitioned Parquet.
-- Record the "Data scanned" figure for each.

SELECT county, COUNT(*) AS crashes
FROM crash_db.raw
WHERE state = 'TN'
GROUP BY county ORDER BY crashes DESC LIMIT 15;

SELECT county, COUNT(*) AS crashes
FROM crash_db.crashes_curated
WHERE state = 'TN'
GROUP BY county ORDER BY crashes DESC LIMIT 15;
