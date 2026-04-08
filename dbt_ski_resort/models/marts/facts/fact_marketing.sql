{{
    config(
        materialized='incremental',
        unique_key='marketing_key',
        schema='marts',
        on_schema_change='append_new_columns'
    )
}}

-- Fact table for marketing campaign performance
-- Grain: One row per marketing touch (campaign execution)

WITH marketing AS (
    SELECT * FROM {{ ref('stg_marketing_touches') }}
),

dim_date AS (
    SELECT date_key, full_date FROM {{ ref('dim_date') }}
),

final AS (
    SELECT
        -- Surrogate key
        {{ dbt_utils.generate_surrogate_key(['m.touch_id']) }} AS marketing_key,

        -- Foreign keys
        d.date_key AS send_date_key,

        -- Natural keys
        m.touch_id,
        m.campaign_id,
        m.sent_date,

        -- Campaign attributes
        m.campaign_name,
        m.campaign_channel,
        m.campaign_type,
        m.audience_segment,

        -- Volume metrics
        m.target_count,
        m.conversion_count,

        -- Rate metrics
        m.open_rate,
        m.click_rate,
        m.conversion_rate,

        -- Revenue metrics
        m.revenue_attributed,
        m.revenue_per_conversion,

        -- Derived metrics
        CASE
            WHEN m.target_count > 0 THEN m.revenue_attributed / m.target_count
            ELSE 0
        END AS revenue_per_target,
        m.target_count * m.open_rate AS estimated_opens,
        m.target_count * m.click_rate AS estimated_clicks,

        -- Metadata
        m.created_at

    FROM marketing m
    LEFT JOIN dim_date d ON m.sent_date = d.full_date
)

SELECT * FROM final

{% if is_incremental() %}
WHERE created_at > (SELECT MAX(created_at) FROM {{ this }})
{% endif %}
