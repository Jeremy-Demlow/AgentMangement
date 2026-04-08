{{
    config(
        materialized='view',
        schema='staging'
    )
}}

-- Staging model for grooming logs
-- Trail grooming operations

with source as (
    select * from {{ source('raw', 'grooming_logs') }}
),

staged as (
    select
        -- Keys
        log_id,
        groomer_id,
        machine_id,

        -- Date/Time
        grooming_date::date as grooming_date,
        start_time::timestamp_ntz as start_time,
        end_time::timestamp_ntz as end_time,

        -- Operations
        shift,
        trail_name,
        grooming_type,
        duration_minutes::int as duration_minutes,

        -- Snow conditions
        snow_depth_inches::float as snow_depth_inches,
        conditions_before,
        conditions_after,

        -- Condition improvement flag
        case
            when conditions_after in ('excellent', 'good')
                 and conditions_before in ('poor', 'fair', 'icy')
            then true
            else false
        end as condition_improved,

        -- Resources
        fuel_used_gallons::float as fuel_used_gallons,

        -- Notes
        notes,

        -- Audit
        created_at

    from source
    where log_id is not null
    qualify row_number() over (partition by log_id order by created_at desc) = 1
)

select * from staged
