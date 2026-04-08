{{
    config(
        materialized='incremental',
        unique_key='incident_id',
        on_schema_change='sync_all_columns'
    )
}}

with incidents as (
    select * from {{ ref('stg_incidents') }}
),

customers as (
    select customer_id, customer_segment from {{ ref('stg_customers') }}
),

final as (
    select
        i.incident_id,
        i.incident_date,
        i.incident_time,
        i.incident_type,
        i.severity,
        i.location_id,
        i.lift_id,
        i.trail_name,
        i.customer_id,
        c.customer_segment,
        i.customer_age,
        i.customer_skill_level,
        i.description,
        i.cause,
        i.weather_factor,
        i.equipment_factor,
        i.first_aid_rendered,
        i.transport_required,
        i.patrol_response_minutes,
        i.resolution,
        i.followup_required,
        -- Severity score for analysis
        case i.severity
            when 'Minor' then 1
            when 'Moderate' then 2
            when 'Serious' then 3
            when 'Critical' then 4
            else 0
        end as severity_score,
        i.created_at
    from incidents i
    left join customers c on i.customer_id = c.customer_id
)

select * from final
{% if is_incremental() %}
where created_at > (select max(created_at) from {{ this }})
{% endif %}
