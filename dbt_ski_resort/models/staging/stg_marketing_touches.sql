{{
    config(
        materialized='view',
        schema='staging'
    )
}}

-- Staging model for marketing campaign touches
-- Campaign performance and attribution data

WITH source AS (
    SELECT * FROM {{ source('raw', 'marketing_touches') }}
),

renamed AS (
    SELECT
        -- Keys
        touch_id,
        campaign_id,

        -- Campaign attributes
        campaign_name,
        campaign_channel,
        campaign_type,
        audience_segment,

        -- Timing
        send_date::DATE AS sent_date,

        -- Volume metrics
        target_count::INT AS target_count,
        conversion_count::INT AS conversion_count,

        -- Rate metrics
        open_rate::FLOAT AS open_rate,
        click_rate::FLOAT AS click_rate,

        -- Revenue
        revenue_attributed::FLOAT AS revenue_attributed,

        -- Derived fields
        CASE
            WHEN conversion_count > 0 THEN revenue_attributed / conversion_count
            ELSE 0
        END AS revenue_per_conversion,
        CASE
            WHEN target_count > 0 THEN conversion_count::FLOAT / target_count
            ELSE 0
        END AS conversion_rate,

        -- Metadata
        created_at::TIMESTAMP_NTZ AS created_at

    FROM source
)

SELECT * FROM renamed
