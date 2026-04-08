-- Staging model for parking lots
with source as (
    select * from {{ source('raw', 'parking_lots') }}
),

staged as (
    select
        lot_id,
        lot_name,
        lot_type,
        total_spaces,
        hourly_rate,
        daily_max,
        distance_to_lifts_feet,
        has_shuttle,
        elevation_zone,
        created_at
    from source
)

select * from staged
