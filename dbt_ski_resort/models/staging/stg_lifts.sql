{{
    config(
        materialized='view',
        schema='staging'
    )
}}

-- Staging model for lift infrastructure
-- Clean lift metadata

SELECT
    lift_id,
    lift_name,
    lift_type,
    capacity_per_hour,
    vertical_feet,
    terrain_type,
    base_elevation,
    top_elevation,
    difficulty_access
FROM {{ source('raw', 'lifts') }}
WHERE lift_id IS NOT NULL
