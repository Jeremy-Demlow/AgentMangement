{{
    config(
        materialized='incremental',
        unique_key='transaction_key',
        schema='marts',
        on_schema_change='append_new_columns',
        cluster_by=['transaction_date_key']
    )
}}

-- Fact table for food & beverage transactions
-- Grain: one row per transaction_id + product

WITH transactions AS (
    SELECT *
    FROM {{ ref('stg_food_beverage') }}
    {% if is_incremental() %}
    WHERE transaction_timestamp > (SELECT MAX(transaction_timestamp) FROM {{ this }})
    {% endif %}
),
enriched_transactions AS (
    SELECT
        {{ dbt_utils.generate_surrogate_key(['t.transaction_id']) }}                   AS transaction_key,
        TO_NUMBER(TO_CHAR(t.transaction_date, 'YYYYMMDD'))                             AS transaction_date_key,
        {{ dbt_utils.generate_surrogate_key(['t.customer_id', 'c.valid_from']) }}      AS customer_key,
        {{ dbt_utils.generate_surrogate_key(['t.location_id']) }}                      AS location_key,
        {{ dbt_utils.generate_surrogate_key(['t.product_id', 'p.valid_from']) }}       AS product_key,
        t.transaction_id,
        t.customer_id,
        t.location_id,
        t.product_id,
        t.transaction_timestamp,
        t.transaction_date,
        t.transaction_hour,
        t.quantity,
        t.unit_price,
        t.total_amount,
        t.payment_method,
        t.created_at,
        p.product_category,
        p.product_type,
        p.price                                   AS list_price,
        (t.total_amount - (t.quantity * p.price)) AS upsell_amount
    FROM transactions t
    LEFT JOIN {{ ref('dim_customer') }} c
        ON t.customer_id = c.customer_id
       AND c.is_current = TRUE
    LEFT JOIN {{ ref('dim_product') }} p
        ON t.product_id = p.product_id
       AND p.is_current = TRUE
)

SELECT *
FROM enriched_transactions
