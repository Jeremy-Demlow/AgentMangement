{{
    config(
        materialized='incremental',
        unique_key='rental_key',
        schema='marts',
        on_schema_change='append_new_columns',
        cluster_by=['rental_date_key']
    )
}}

-- Fact table for rental transactions
-- Grain: one row per rental_id + product

WITH rentals AS (
    SELECT *
    FROM {{ ref('stg_rentals') }}
    {% if is_incremental() %}
    WHERE rental_timestamp > (SELECT MAX(rental_timestamp) FROM {{ this }})
    {% endif %}
),
enriched_rentals AS (
    SELECT
        {{ dbt_utils.generate_surrogate_key(['r.rental_id']) }}                        AS rental_key,
        TO_NUMBER(TO_CHAR(r.rental_date, 'YYYYMMDD'))                                  AS rental_date_key,
        TO_NUMBER(TO_CHAR(r.return_date, 'YYYYMMDD'))                                  AS return_date_key,
        {{ dbt_utils.generate_surrogate_key(['r.customer_id', 'c.valid_from']) }}      AS customer_key,
        {{ dbt_utils.generate_surrogate_key(['r.location_id']) }}                      AS location_key,
        {{ dbt_utils.generate_surrogate_key(['r.product_id', 'p.valid_from']) }}       AS product_key,
        r.rental_id,
        r.customer_id,
        r.location_id,
        r.product_id,
        r.rental_timestamp,
        r.rental_date,
        r.rental_hour,
        r.return_timestamp,
        r.return_date,
        r.return_hour,
        r.returned_same_day,
        r.rental_duration_hours,
        r.rental_amount,
        r.created_at,
        p.product_category,
        p.product_type,
        p.price                                  AS list_price,
        (r.rental_amount - p.price)              AS rental_markup
    FROM rentals r
    LEFT JOIN {{ ref('dim_customer') }} c
        ON r.customer_id = c.customer_id
       AND c.is_current = TRUE
    LEFT JOIN {{ ref('dim_product') }} p
        ON r.product_id = p.product_id
       AND p.is_current = TRUE
)

SELECT *
FROM enriched_rentals
