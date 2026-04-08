{{
    config(
        materialized='view',
        schema='staging'
    )
}}

-- Staging model for daily pass usage
-- Tracks customer visits with entry/exit times

SELECT
    usage_id,
    customer_id,
    visit_date,
    first_scan_time,
    last_scan_time,
    total_lift_rides,
    hours_on_mountain,
    DATE_PART('DAYOFWEEK', visit_date) AS day_of_week,
    CASE WHEN DATE_PART('DAYOFWEEK', visit_date) IN (0, 6) THEN TRUE ELSE FALSE END AS is_weekend,
    created_at
FROM {{ source('raw', 'pass_usage') }}
WHERE usage_id IS NOT NULL
  AND customer_id IS NOT NULL
  AND visit_date IS NOT NULL
