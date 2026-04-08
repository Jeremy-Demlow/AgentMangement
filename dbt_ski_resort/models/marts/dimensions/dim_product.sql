{{
    config(
        materialized='table',
        schema='marts'
    )
}}

-- Product dimension - Type 2 SCD for price changes
-- Products for rentals and F&B

WITH product_scd AS (
    SELECT
        product_id,
        product_name,
        product_category,
        product_type,
        price,
        '2020-11-01'::TIMESTAMP AS valid_from,
        '9999-12-31'::TIMESTAMP AS valid_to,
        TRUE AS is_current
    FROM {{ source('raw', 'products') }}
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['product_id', 'valid_from']) }} AS product_key,
    product_id,
    product_name,
    product_category,
    product_type,
    price,
    valid_from,
    valid_to,
    is_current,
    CURRENT_TIMESTAMP() AS created_at,
    CURRENT_TIMESTAMP() AS updated_at
FROM product_scd
ORDER BY product_id, valid_from
