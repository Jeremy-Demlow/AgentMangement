{{
    config(
        materialized='view',
        schema='staging'
    )
}}

-- Staging model for customers
-- Type-safe customer master data

SELECT
    customer_id,
    customer_name,
    email,
    phone,
    birth_date,
    FLOOR(DATEDIFF('YEAR', birth_date, CURRENT_DATE())) AS age,
    CASE
        WHEN FLOOR(DATEDIFF('YEAR', birth_date, CURRENT_DATE())) < 18 THEN 'Child'
        WHEN FLOOR(DATEDIFF('YEAR', birth_date, CURRENT_DATE())) BETWEEN 18 AND 34 THEN 'Young Adult'
        WHEN FLOOR(DATEDIFF('YEAR', birth_date, CURRENT_DATE())) BETWEEN 35 AND 54 THEN 'Adult'
        WHEN FLOOR(DATEDIFF('YEAR', birth_date, CURRENT_DATE())) >= 55 THEN 'Senior'
        ELSE 'Unknown'
    END AS age_group,
    customer_segment,
    is_pass_holder,
    pass_type,
    first_visit_date,
    home_zip_code,
    state,
    created_at
FROM {{ source('raw', 'customers') }}
WHERE customer_id IS NOT NULL
