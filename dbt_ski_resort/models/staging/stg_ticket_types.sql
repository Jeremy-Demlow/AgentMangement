{{
    config(
        materialized='view',
        schema='staging'
    )
}}

-- Staging model for ticket types
-- All pass and ticket type definitions

SELECT
    ticket_type_id,
    ticket_name,
    ticket_category,
    duration_days,
    access_level,
    price,
    blackout_dates
FROM {{ source('raw', 'ticket_types') }}
WHERE ticket_type_id IS NOT NULL
