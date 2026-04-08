{{
    config(
        materialized='table',
        schema='marts'
    )
}}

-- Customer dimension - Type 2 SCD
-- Tracks customer profile changes over time
-- Will be populated from generated customer data

WITH raw_customers AS (
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
        created_at AS record_created_at
    FROM {{ source('raw', 'customers') }}
),

customer_scd AS (
    SELECT
        customer_id,
        customer_name,
        email,
        phone,
        birth_date,
        age,
        age_group,
        customer_segment,
        is_pass_holder,
        pass_type,
        first_visit_date,
        home_zip_code,
        state,
        record_created_at AS valid_from,
        '9999-12-31'::TIMESTAMP AS valid_to,
        TRUE AS is_current
    FROM raw_customers
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['customer_id', 'valid_from']) }} AS customer_key,
    customer_id,
    customer_name,
    email,
    phone,
    birth_date,
    age,
    age_group,
    customer_segment,
    is_pass_holder,
    pass_type,
    first_visit_date,
    home_zip_code,
    state,
    valid_from,
    valid_to,
    is_current,
    CURRENT_TIMESTAMP() AS created_at,
    CURRENT_TIMESTAMP() AS updated_at
FROM customer_scd
ORDER BY customer_id, valid_from
