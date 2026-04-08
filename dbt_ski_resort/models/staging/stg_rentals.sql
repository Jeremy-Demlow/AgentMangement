{{ config(
    materialized='view',
    schema='staging'
) }}

-- Staging model for equipment rentals
-- Adds rental/return dates, same-day return indicator, and duration hygiene

SELECT
    rental_id,
    customer_id,
    location_id,
    product_id,
    rental_timestamp,
    DATE(rental_timestamp)                    AS rental_date,
    DATE_PART('HOUR', rental_timestamp)       AS rental_hour,
    return_timestamp,
    DATE(return_timestamp)                    AS return_date,
    DATE_PART('HOUR', return_timestamp)       AS return_hour,
    CASE
        WHEN DATE(return_timestamp) = DATE(rental_timestamp) THEN TRUE
        ELSE FALSE
    END AS returned_same_day,
    rental_duration_hours,
    rental_amount,
    created_at
FROM {{ source('raw', 'rentals') }}
WHERE rental_id IS NOT NULL
QUALIFY ROW_NUMBER() OVER (PARTITION BY rental_id ORDER BY created_at DESC) = 1
