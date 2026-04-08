{{
    config(
        materialized='incremental',
        unique_key='lesson_id',
        on_schema_change='sync_all_columns'
    )
}}

with lessons as (
    select * from {{ ref('stg_ski_lessons') }}
),

customers as (
    select customer_id, customer_segment from {{ ref('stg_customers') }}
),

instructors as (
    select instructor_id, instructor_name, certification_level, avg_rating as instructor_rating
    from {{ ref('stg_instructors') }}
),

final as (
    select
        l.lesson_id,
        l.customer_id,
        c.customer_segment,
        l.lesson_date,
        l.lesson_start_time,
        l.lesson_type,
        l.sport_type,
        l.skill_level,
        l.duration_hours,
        l.instructor_id,
        i.instructor_name,
        i.certification_level as instructor_certification,
        i.instructor_rating,
        l.group_size,
        l.lesson_amount,
        l.rental_included,
        l.rental_amount,
        l.tip_amount,
        l.lesson_amount + coalesce(l.rental_amount, 0) + coalesce(l.tip_amount, 0) as total_lesson_revenue,
        l.booking_channel,
        l.booking_lead_days,
        l.completed,
        l.cancellation_reason,
        l.student_rating,
        l.created_at
    from lessons l
    left join customers c on l.customer_id = c.customer_id
    left join instructors i on l.instructor_id = i.instructor_id
)

select * from final
{% if is_incremental() %}
where created_at > (select max(created_at) from {{ this }})
{% endif %}
