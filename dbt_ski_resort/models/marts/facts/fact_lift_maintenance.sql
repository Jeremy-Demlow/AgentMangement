{{
    config(
        materialized='incremental',
        unique_key='maintenance_key',
        schema='marts',
        on_schema_change='append_new_columns'
    )
}}

WITH maintenance AS (
    SELECT * FROM {{ ref('stg_lift_maintenance') }}
),

dim_date AS (
    SELECT date_key, full_date FROM {{ ref('dim_date') }}
),

dim_lift AS (
    SELECT lift_key, lift_id FROM {{ ref('dim_lift') }}
),

final AS (
    SELECT
        {{ dbt_utils.generate_surrogate_key(['m.maintenance_id']) }} AS maintenance_key,

        d.date_key,
        l.lift_key,

        m.maintenance_id,
        m.lift_id,
        m.technician_id,
        m.maintenance_date,
        m.start_time,
        m.end_time,

        m.maintenance_type,
        m.category,
        m.description,

        m.downtime_minutes,
        m.during_operating_hours,

        m.parts_replaced,
        m.parts_cost,
        m.labor_hours,
        m.labor_cost,
        m.total_cost,

        m.passed_inspection,
        m.followup_required,
        m.notes,

        m.created_at

    FROM maintenance m
    LEFT JOIN dim_date d ON m.maintenance_date = d.full_date
    LEFT JOIN dim_lift l ON m.lift_id = l.lift_id
)

SELECT * FROM final

{% if is_incremental() %}
WHERE created_at > (SELECT MAX(created_at) FROM {{ this }})
{% endif %}
