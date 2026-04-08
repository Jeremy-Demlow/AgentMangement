{{
    config(
        materialized='table',
        schema='marts'
    )
}}

-- Ticket Type dimension - Type 2 SCD for price changes
-- All ticket and pass types

WITH ticket_scd AS (
    SELECT
        ticket_type_id,
        ticket_name,
        ticket_category,
        duration_days,
        access_level,
        price,
        blackout_dates,
        '2020-11-01'::TIMESTAMP AS valid_from,
        '9999-12-31'::TIMESTAMP AS valid_to,
        TRUE AS is_current
    FROM {{ source('raw', 'ticket_types') }}
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['ticket_type_id', 'valid_from']) }} AS ticket_type_key,
    ticket_type_id,
    ticket_name,
    ticket_category,
    duration_days,
    access_level,
    price,
    blackout_dates,
    valid_from,
    valid_to,
    is_current,
    CURRENT_TIMESTAMP() AS created_at,
    CURRENT_TIMESTAMP() AS updated_at
FROM ticket_scd
ORDER BY ticket_type_id, valid_from
