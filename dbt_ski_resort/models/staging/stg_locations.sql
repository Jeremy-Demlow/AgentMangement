{{
    config(
        materialized='view',
        schema='staging'
    )
}}

-- Staging model for physical locations
-- Rental shops, F&B venues, ticket windows

SELECT
    location_id,
    location_name,
    location_type,
    venue_size,
    seating_capacity,
    elevation_zone
FROM {{ source('raw', 'locations') }}
WHERE location_id IS NOT NULL
