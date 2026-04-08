{{
    config(
        materialized='view',
        schema='staging'
    )
}}

-- Staging model for parking occupancy
-- Hourly parking lot utilization

with source as (
    select * from {{ source('raw', 'parking_occupancy') }}
),

staged as (
    select
        -- Keys
        record_id,
        lot_id,

        -- Date/Time
        record_date::date as record_date,
        record_hour::int as record_hour,

        -- Lot info
        lot_name,
        total_spaces::int as total_spaces,

        -- Occupancy
        occupied_spaces::int as occupied_spaces,
        (total_spaces - occupied_spaces)::int as available_spaces,
        occupancy_percent::float as occupancy_percent,

        -- Occupancy tier for analysis
        case
            when occupancy_percent >= 95 then 'Full'
            when occupancy_percent >= 80 then 'High'
            when occupancy_percent >= 50 then 'Moderate'
            when occupancy_percent >= 20 then 'Low'
            else 'Empty'
        end as occupancy_tier,

        -- Traffic
        vehicles_entered::int as vehicles_entered,
        vehicles_exited::int as vehicles_exited,

        -- Revenue
        revenue_collected::float as revenue_collected,

        -- Flags
        overflow_active::boolean as overflow_active,

        -- Audit
        created_at

    from source
    where record_id is not null
    qualify row_number() over (partition by record_id order by created_at desc) = 1
)

select * from staged
