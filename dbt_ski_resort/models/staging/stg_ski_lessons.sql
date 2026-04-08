-- Staging model for ski lessons
with source as (
    select * from {{ source('raw', 'ski_lessons') }}
),

staged as (
    select
        lesson_id,
        customer_id,
        lesson_date,
        lesson_start_time,
        lesson_type,
        sport_type,
        skill_level,
        duration_hours,
        instructor_id,
        group_size,
        lesson_amount,
        rental_included,
        rental_amount,
        tip_amount,
        booking_channel,
        booking_lead_days,
        completed,
        cancellation_reason,
        student_rating,
        created_at
    from source
    qualify row_number() over (partition by lesson_id order by created_at desc) = 1
)

select * from staged
