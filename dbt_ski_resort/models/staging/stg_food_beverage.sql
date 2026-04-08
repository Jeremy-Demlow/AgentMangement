{{ config(
    materialized='view',
    schema='staging'
) }}

-- Staging model for food & beverage transactions
-- Standardizes timestamps and exposes spend metrics

SELECT
    transaction_id,
    customer_id,
    location_id,
    product_id,
    transaction_timestamp,
    DATE(transaction_timestamp)                AS transaction_date,
    DATE_PART('HOUR', transaction_timestamp)   AS transaction_hour,
    quantity,
    unit_price,
    total_amount,
    payment_method,
    created_at
FROM {{ source('raw', 'food_beverage') }}
WHERE transaction_id IS NOT NULL
QUALIFY ROW_NUMBER() OVER (PARTITION BY transaction_id ORDER BY created_at DESC) = 1
