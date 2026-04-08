{{
    config(
        materialized='incremental',
        unique_key='weather_key',
        schema='marts',
        on_schema_change='append_new_columns'
    )
}}

-- Fact table for daily weather conditions
-- Grain: One row per date per mountain zone

WITH weather AS (
    SELECT * FROM {{ ref('stg_weather_conditions') }}
),

dim_date AS (
    SELECT date_key, full_date FROM {{ ref('dim_date') }}
),

final AS (
    SELECT
        -- Surrogate key
        {{ dbt_utils.generate_surrogate_key(['w.weather_date', 'w.mountain_zone']) }} AS weather_key,

        -- Foreign keys
        d.date_key,

        -- Natural keys (for reference)
        w.weather_date,
        w.mountain_zone,

        -- Weather facts
        w.snow_condition,
        w.snowfall_inches,
        w.base_depth_inches,
        w.temp_high_f,
        w.temp_low_f,
        w.wind_speed_mph,
        w.storm_warning,
        w.is_powder_day,
        w.is_high_wind,

        -- Derived metrics
        (w.temp_high_f + w.temp_low_f) / 2 AS avg_temp_f,
        w.temp_high_f - w.temp_low_f AS temp_range_f,

        -- Metadata
        w.created_at

    FROM weather w
    LEFT JOIN dim_date d ON w.weather_date = d.full_date
)

SELECT * FROM final

{% if is_incremental() %}
WHERE created_at > (SELECT MAX(created_at) FROM {{ this }})
{% endif %}
