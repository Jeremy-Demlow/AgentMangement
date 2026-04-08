{{
    config(
        materialized='incremental',
        unique_key='sale_key',
        schema='marts',
        on_schema_change='append_new_columns',
        cluster_by=['purchase_date_key']
    )
}}

-- Fact table for ticket and pass sales
-- Grain: one row per sale_id

WITH sales AS (
    SELECT *
    FROM {{ ref('stg_ticket_sales') }}
    {% if is_incremental() %}
    WHERE purchase_timestamp > (SELECT MAX(purchase_timestamp) FROM {{ this }})
    {% endif %}
),
enriched_sales AS (
    SELECT
        {{ dbt_utils.generate_surrogate_key(['s.sale_id']) }}                           AS sale_key,
        TO_NUMBER(TO_CHAR(s.purchase_date, 'YYYYMMDD'))                                AS purchase_date_key,
        {{ dbt_utils.generate_surrogate_key(['s.customer_id', 'c.valid_from']) }}      AS customer_key,
        {{ dbt_utils.generate_surrogate_key(['s.location_id']) }}                      AS location_key,
        {{ dbt_utils.generate_surrogate_key(['s.ticket_type_id', 'tt.valid_from']) }}  AS ticket_type_key,
        s.sale_id,
        s.customer_id,
        s.ticket_type_id,
        s.location_id,
        s.purchase_timestamp,
        s.purchase_date,
        s.purchase_hour,
        s.valid_from_date,
        s.valid_to_date,
        s.days_until_valid,
        s.purchase_amount,
        s.payment_method,
        s.purchase_channel,
        s.is_advance_purchase,
        s.created_at,
        tt.ticket_category,
        tt.access_level,
        tt.price                             AS list_price,
        (tt.price - s.purchase_amount)       AS discount_amount
    FROM sales s
    LEFT JOIN {{ ref('dim_customer') }} c
        ON s.customer_id = c.customer_id
       AND c.is_current = TRUE
    LEFT JOIN {{ ref('dim_ticket_type') }} tt
        ON s.ticket_type_id = tt.ticket_type_id
       AND tt.is_current = TRUE
)

SELECT *
FROM enriched_sales
