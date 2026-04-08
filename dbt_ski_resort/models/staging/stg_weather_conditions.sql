{{
    config(
        materialized='view',
        schema='staging'
    )
}}

-- Staging model for weather conditions
-- Daily weather observations by mountain zone

WITH source AS (
    SELECT * FROM {{ source('raw', 'weather_conditions') }}
),

renamed AS (
    SELECT
        -- Natural key
        weather_date::DATE AS weather_date,
        mountain_zone,

        -- Weather attributes
        snow_condition,
        snowfall_inches::FLOAT AS snowfall_inches,
        base_depth_inches::FLOAT AS base_depth_inches,
        temp_high_f::FLOAT AS temp_high_f,
        temp_low_f::FLOAT AS temp_low_f,
        wind_speed_mph::FLOAT AS wind_speed_mph,
        storm_warning::BOOLEAN AS storm_warning,

        -- Derived fields
        CASE
            WHEN snowfall_inches >= 6 THEN TRUE
            ELSE FALSE
        END AS is_powder_day,
        CASE
            WHEN wind_speed_mph >= 25 THEN TRUE
            ELSE FALSE
        END AS is_high_wind,

        -- Metadata
        created_at::TIMESTAMP_NTZ AS created_at

    FROM source
)

SELECT * FROM renamed
