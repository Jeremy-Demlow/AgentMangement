{{ config(
    materialized='view',
    schema='staging'
) }}

-- Staging model for ticket and pass sales
-- Normalizes purchase timestamps, flags advance purchases, and exposes spend attributes

SELECT
    sale_id,
    customer_id,
    ticket_type_id,
    location_id,
    purchase_timestamp,
    DATE(purchase_timestamp)               AS purchase_date,
    DATE_PART('HOUR', purchase_timestamp)  AS purchase_hour,
    valid_from_date,
    valid_to_date,
    DATEDIFF('DAY', purchase_timestamp::DATE, valid_from_date) AS days_until_valid,
    purchase_amount,
    payment_method,
    purchase_channel,
    CASE
        WHEN purchase_channel = 'online' AND valid_from_date > DATE(purchase_timestamp)
            THEN TRUE
        WHEN purchase_channel <> 'online' AND purchase_timestamp::DATE < valid_from_date
            THEN TRUE
        ELSE FALSE
    END AS is_advance_purchase,
    created_at
FROM {{ source('raw', 'ticket_sales') }}
WHERE sale_id IS NOT NULL
QUALIFY ROW_NUMBER() OVER (PARTITION BY sale_id ORDER BY created_at DESC) = 1
