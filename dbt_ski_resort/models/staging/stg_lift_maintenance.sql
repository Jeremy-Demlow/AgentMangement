{{
    config(
        materialized='view',
        schema='staging'
    )
}}

with source as (
    select * from {{ source('raw', 'lift_maintenance') }}
),

staged as (
    select
        maintenance_id,
        lift_id,
        technician_id,

        maintenance_date::date as maintenance_date,
        start_time::timestamp_ntz as start_time,
        end_time::timestamp_ntz as end_time,

        LOWER(maintenance_type) as maintenance_type,
        LOWER(category) as category,
        description,

        downtime_minutes::int as downtime_minutes,
        during_operating_hours::boolean as during_operating_hours,

        parts_replaced::boolean as parts_replaced,
        parts_cost::float as parts_cost,
        labor_hours::float as labor_hours,
        labor_cost::float as labor_cost,
        total_cost::float as total_cost,

        passed_inspection::boolean as passed_inspection,
        followup_required::boolean as followup_required,
        notes,

        created_at

    from source
    where maintenance_id is not null
    qualify row_number() over (partition by maintenance_id order by created_at desc) = 1
)

select * from staged
