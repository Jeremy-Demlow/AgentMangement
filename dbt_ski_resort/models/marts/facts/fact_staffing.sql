{{
    config(
        materialized='incremental',
        unique_key='staffing_key',
        schema='marts',
        on_schema_change='append_new_columns'
    )
}}

-- Fact table for daily staffing schedules
-- Grain: One row per schedule entry (date + department + role + location)

WITH staffing AS (
    SELECT * FROM {{ ref('stg_staffing_schedule') }}
),

dim_date AS (
    SELECT date_key, full_date FROM {{ ref('dim_date') }}
),

dim_location AS (
    SELECT location_key, location_id FROM {{ ref('dim_location') }}
),

final AS (
    SELECT
        -- Surrogate key
        {{ dbt_utils.generate_surrogate_key(['s.schedule_id']) }} AS staffing_key,

        -- Foreign keys
        d.date_key,
        l.location_key,

        -- Natural keys
        s.schedule_id,
        s.schedule_date,

        -- Department attributes
        s.department,
        s.job_role,

        -- Time attributes
        s.shift_start,
        s.shift_end,
        s.shift_hours,

        -- Staffing metrics
        s.scheduled_employees,
        s.actual_employees,
        s.coverage_ratio,
        s.is_understaffed,

        -- Derived metrics
        s.scheduled_employees - s.actual_employees AS staff_variance,
        s.scheduled_employees * s.shift_hours AS scheduled_labor_hours,
        s.actual_employees * s.shift_hours AS actual_labor_hours,

        -- Metadata
        s.created_at

    FROM staffing s
    LEFT JOIN dim_date d ON s.schedule_date = d.full_date
    LEFT JOIN dim_location l ON s.location_id = l.location_id
)

SELECT * FROM final

{% if is_incremental() %}
WHERE created_at > (SELECT MAX(created_at) FROM {{ this }})
{% endif %}
