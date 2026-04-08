{{
    config(
        materialized='table',
        schema='marts'
    )
}}

-- Location dimension - Type 1 SCD
-- Physical locations for rentals, F&B, and ticket sales

SELECT
    {{ dbt_utils.generate_surrogate_key(['location_id']) }} AS location_key,
    location_id,
    location_name,
    location_type,
    venue_size,
    seating_capacity,
    elevation_zone,
    CURRENT_TIMESTAMP() AS created_at,
    CURRENT_TIMESTAMP() AS updated_at
FROM {{ source('raw', 'locations') }}
ORDER BY location_id
