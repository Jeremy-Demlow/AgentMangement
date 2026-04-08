{{
    config(
        materialized='view',
        schema='staging'
    )
}}

-- Staging model for safety incidents
-- Type-safe with severity categorization

with source as (
    select * from {{ source('raw', 'incidents') }}
),

staged as (
    select
        -- Keys
        incident_id,
        customer_id,
        location_id,
        lift_id,

        -- Dates/Times
        incident_date::date as incident_date,
        incident_time::time as incident_time,
        incident_timestamp::timestamp_ntz as incident_timestamp,

        -- Location
        trail_name,

        -- Incident details
        LOWER(incident_type) AS incident_type,
        LOWER(severity) AS severity,
        description,
        cause,

        -- Severity scoring for analytics
        case severity
            when 'minor' then 1
            when 'moderate' then 2
            when 'serious' then 3
            else 0
        end as severity_score,

        -- Customer context
        customer_age::int as customer_age,
        customer_skill_level,

        -- Contributing factors
        weather_factor::boolean as weather_factor,
        equipment_factor::boolean as equipment_factor,

        -- Response
        first_aid_rendered::boolean as first_aid_rendered,
        transport_required::boolean as transport_required,
        transport_type,
        patrol_response_minutes::int as patrol_response_minutes,

        -- Resolution
        resolution,
        followup_required::boolean as followup_required,
        report_filed::boolean as report_filed,

        -- Audit
        created_at

    from source
    where incident_id is not null
    qualify row_number() over (partition by incident_id order by created_at desc) = 1
)

select * from staged
