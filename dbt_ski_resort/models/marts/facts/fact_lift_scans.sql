{{
    config(
        materialized='incremental',
        unique_key='scan_key',
        schema='marts',
        on_schema_change='append_new_columns',
        cluster_by=['date_key']
    )
}}

-- Fact table for lift scan events
-- Transaction grain: one row per lift scan

WITH scans AS (
    SELECT * FROM {{ ref('stg_lift_scans') }}
    {% if is_incremental() %}
    WHERE scan_timestamp > (SELECT MAX(scan_timestamp) FROM {{ this }})
    {% endif %}
),

enriched_scans AS (
    SELECT
        {{ dbt_utils.generate_surrogate_key(['s.scan_id']) }} AS scan_key,
        TO_NUMBER(TO_CHAR(s.scan_date, 'YYYYMMDD')) AS date_key,
        {{ dbt_utils.generate_surrogate_key(['s.customer_id', 'c.valid_from']) }} AS customer_key,
        {{ dbt_utils.generate_surrogate_key(['s.lift_id']) }} AS lift_key,
        s.scan_id,
        s.customer_id,
        s.lift_id,
        s.scan_timestamp,
        s.wait_time_minutes,
        s.temperature_f,
        s.weather_condition,
        s.scan_hour,
        s.day_of_week,
        CURRENT_TIMESTAMP() AS created_at
    FROM scans s
    LEFT JOIN {{ ref('dim_customer') }} c
        ON s.customer_id = c.customer_id
        AND c.is_current = TRUE
)

SELECT * FROM enriched_scans
