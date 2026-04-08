{{
    config(
        materialized='view',
        schema='staging'
    )
}}

-- Staging model for staffing schedules
-- Daily staff allocations by department and role

WITH source AS (
    SELECT * FROM {{ source('raw', 'staffing_schedule') }}
),

renamed AS (
    SELECT
        -- Keys
        schedule_id,
        location_id,

        -- Time attributes
        schedule_date::DATE AS schedule_date,
        shift_start::TIMESTAMP_NTZ AS shift_start,
        shift_end::TIMESTAMP_NTZ AS shift_end,

        -- Department attributes
        department,
        job_role,

        -- Staffing metrics
        scheduled_employees::INT AS scheduled_employees,
        actual_employees::INT AS actual_employees,
        coverage_ratio::FLOAT AS coverage_ratio,

        -- Derived fields
        CASE
            WHEN coverage_ratio < 0.9 THEN TRUE
            ELSE FALSE
        END AS is_understaffed,
        DATEDIFF('HOUR', shift_start, shift_end) AS shift_hours,

        -- Metadata
        created_at::TIMESTAMP_NTZ AS created_at

    FROM source
)

SELECT * FROM renamed
