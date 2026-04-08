{{
    config(
        materialized='incremental',
        unique_key='usage_key',
        schema='marts',
        on_schema_change='append_new_columns',
        cluster_by=['date_key']
    )
}}

-- Fact table for daily pass usage
-- Transaction grain: one row per customer per day

WITH usage AS (
    SELECT * FROM {{ ref('stg_pass_usage') }}
    {% if is_incremental() %}
    WHERE visit_date > (SELECT MAX(visit_date) FROM {{ this }})
    {% endif %}
),

enriched_usage AS (
    SELECT
        {{ dbt_utils.generate_surrogate_key(['u.usage_id']) }} AS usage_key,
        TO_NUMBER(TO_CHAR(u.visit_date, 'YYYYMMDD')) AS date_key,
        {{ dbt_utils.generate_surrogate_key(['u.customer_id', 'c.valid_from']) }} AS customer_key,
        u.usage_id,
        u.customer_id,
        u.visit_date,
        u.first_scan_time,
        u.last_scan_time,
        u.total_lift_rides,
        u.hours_on_mountain,
        u.is_weekend,
        CURRENT_TIMESTAMP() AS created_at
    FROM usage u
    LEFT JOIN {{ ref('dim_customer') }} c
        ON u.customer_id = c.customer_id
        AND c.is_current = TRUE
)

SELECT * FROM enriched_usage
