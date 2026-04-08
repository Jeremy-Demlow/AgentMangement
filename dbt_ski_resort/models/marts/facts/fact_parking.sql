{{
    config(
        materialized='incremental',
        unique_key='record_id',
        on_schema_change='sync_all_columns'
    )
}}

with parking_occupancy as (
    select * from {{ ref('stg_parking_occupancy') }}
),

parking_lots as (
    select lot_id, lot_name, lot_type, total_spaces as lot_capacity,
           daily_max as daily_rate, has_shuttle, distance_to_lifts_feet
    from {{ ref('stg_parking_lots') }}
),

final as (
    select
        po.record_id,
        po.record_date,
        po.record_hour,
        po.lot_id,
        pl.lot_name as lot_name_dim,
        pl.lot_type,
        pl.lot_capacity,
        pl.daily_rate,
        pl.has_shuttle,
        pl.distance_to_lifts_feet,
        po.lot_name,
        po.total_spaces,
        po.occupied_spaces,
        po.occupancy_percent,
        po.vehicles_entered,
        po.vehicles_exited,
        po.revenue_collected,
        po.overflow_active,
        -- Occupancy status
        case
            when po.occupancy_percent >= 95 then 'Full'
            when po.occupancy_percent >= 80 then 'Near Full'
            when po.occupancy_percent >= 50 then 'Moderate'
            else 'Light'
        end as occupancy_status,
        po.created_at
    from parking_occupancy po
    left join parking_lots pl on po.lot_id = pl.lot_id
)

select * from final
{% if is_incremental() %}
where created_at > (select max(created_at) from {{ this }})
{% endif %}
