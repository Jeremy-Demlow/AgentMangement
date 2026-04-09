{{
    config(
        materialized='incremental',
        unique_key='grooming_key',
        schema='marts',
        on_schema_change='append_new_columns'
    )
}}

WITH grooming AS (
    SELECT * FROM {{ ref('stg_grooming_logs') }}
),

dim_date AS (
    SELECT date_key, full_date FROM {{ ref('dim_date') }}
),

final AS (
    SELECT
        {{ dbt_utils.generate_surrogate_key(['g.log_id']) }} AS grooming_key,

        d.date_key,

        g.log_id,
        g.groomer_id,
        g.machine_id,
        g.grooming_date,
        g.start_time,
        g.end_time,

        g.shift,
        g.trail_name,
        g.grooming_type,
        g.duration_minutes,

        g.snow_depth_inches,
        g.conditions_before,
        g.conditions_after,
        g.condition_improved,

        g.fuel_used_gallons,
        g.notes,

        g.created_at

    FROM grooming g
    LEFT JOIN dim_date d ON g.grooming_date = d.full_date
)

SELECT * FROM final

{% if is_incremental() %}
WHERE created_at > (SELECT MAX(created_at) FROM {{ this }})
{% endif %}
