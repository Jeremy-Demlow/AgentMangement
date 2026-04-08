{{
    config(
        materialized='table',
        schema='marts'
    )
}}

-- Lift dimension - Type 1 SCD (slowly changing dimension)
-- Based on static lift infrastructure

SELECT
    {{ dbt_utils.generate_surrogate_key(['lift_id']) }} AS lift_key,
    lift_id,
    lift_name,
    lift_type,
    capacity_per_hour,
    vertical_feet,
    terrain_type,
    base_elevation,
    top_elevation,
    difficulty_access,
    CURRENT_TIMESTAMP() AS created_at,
    CURRENT_TIMESTAMP() AS updated_at
FROM {{ source('raw', 'lifts') }}
ORDER BY lift_id
