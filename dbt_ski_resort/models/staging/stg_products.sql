{{
    config(
        materialized='view',
        schema='staging'
    )
}}

-- Staging model for products
-- Rental equipment and F&B items

SELECT
    product_id,
    product_name,
    product_category,
    product_type,
    price
FROM {{ source('raw', 'products') }}
WHERE product_id IS NOT NULL
