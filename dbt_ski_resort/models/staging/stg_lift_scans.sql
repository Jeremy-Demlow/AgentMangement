{{
    config(
        materialized='view',
        schema='staging'
    )
}}

-- Staging model for lift scan events
-- Type-safe, cleaned data from raw lift scans

SELECT
    scan_id,
    customer_id,
    lift_id,
    scan_timestamp,
    wait_time_minutes,
    temperature_f,
    weather_condition,
    TO_DATE(scan_timestamp) AS scan_date,
    DATE_PART('HOUR', scan_timestamp) AS scan_hour,
    DATE_PART('DAYOFWEEK', scan_timestamp) AS day_of_week,
    created_at
FROM {{ source('raw', 'lift_scans') }}
WHERE scan_id IS NOT NULL
  AND customer_id IS NOT NULL
  AND lift_id IS NOT NULL
  AND scan_timestamp IS NOT NULL
