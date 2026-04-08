-- Staging model for employees
with source as (
    select * from {{ source('raw', 'employees') }}
),

staged as (
    select
        employee_id,
        employee_name,
        department,
        job_title,
        hire_date,
        termination_date,
        employment_type,
        hourly_rate,
        certifications,
        emergency_contact,
        is_supervisor,
        reports_to,
        created_at
    from source
)

select * from staged
