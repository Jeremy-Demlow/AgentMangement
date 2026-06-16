{{
    config(
        materialized='table',
        schema='marts'
    )
}}

-- Ticket Type dimension - Type 2 SCD for price changes
-- All ticket and pass types (winter from RAW source + summer from seed)

WITH raw_types AS (
    SELECT
        ticket_type_id,
        ticket_name,
        ticket_category,
        duration_days,
        access_level,
        price,
        blackout_dates
    FROM {{ source('raw', 'ticket_types') }}
),
seed_types AS (
    SELECT
        ticket_type_id,
        ticket_name,
        ticket_category,
        duration_days,
        access_level,
        price,
        blackout_dates
    FROM {{ ref('ticket_type_metadata') }}
    WHERE ticket_type_id NOT IN (SELECT ticket_type_id FROM raw_types)
),
all_types AS (
    SELECT * FROM raw_types
    UNION ALL
    SELECT * FROM seed_types
),
ticket_scd AS (
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
    FROM all_types
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
