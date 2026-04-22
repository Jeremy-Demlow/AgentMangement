{{
    config(
        materialized='semantic_view',
        schema='semantic'
    )
}}

-- Marketing Analytics semantic view
-- Analyzes campaign performance, conversion, and attribution

TABLES (
    MARKETING AS {{ ref('fact_marketing') }}
      PRIMARY KEY (MARKETING_KEY)
      WITH SYNONYMS ('campaigns', 'promotions')
      COMMENT = 'Marketing campaign performance and attribution',

    DATES AS {{ ref('dim_date') }}
      PRIMARY KEY (DATE_KEY)
      WITH SYNONYMS ('calendar', 'day_attributes')
      COMMENT = 'Calendar dimension'
)

RELATIONSHIPS (
    MARKETING_TO_DATE AS
      MARKETING (SEND_DATE_KEY) REFERENCES DATES (DATE_KEY)
)

FACTS (
    MARKETING.TARGET_COUNT AS TARGET_COUNT
      COMMENT = 'Number of recipients targeted',
    MARKETING.CONVERSION_COUNT AS CONVERSION_COUNT
      COMMENT = 'Number of conversions',
    MARKETING.REVENUE_ATTRIBUTED AS REVENUE_ATTRIBUTED
      COMMENT = 'Revenue attributed to campaign',
    MARKETING.OPEN_RATE AS OPEN_RATE
      COMMENT = 'Email open rate',
    MARKETING.CLICK_RATE AS CLICK_RATE
      COMMENT = 'Click-through rate',
    MARKETING.CONVERSION_RATE AS CONVERSION_RATE
      COMMENT = 'Conversion rate'
)

DIMENSIONS (
    MARKETING.SENT_DATE AS SENT_DATE
      WITH SYNONYMS ('date', 'campaign_date', 'send_date')
      COMMENT = 'Date campaign was sent',
    DATES.MONTH_NAME AS MONTH_NAME
      COMMENT = 'Month name',
    DATES.SKI_SEASON AS SKI_SEASON
      WITH SYNONYMS ('season')
      COMMENT = 'Ski season identifier',
    MARKETING.CAMPAIGN_NAME AS CAMPAIGN_NAME
      WITH SYNONYMS ('campaign', 'promo')
      COMMENT = 'Campaign name',
    MARKETING.CAMPAIGN_CHANNEL AS CAMPAIGN_CHANNEL
      WITH SYNONYMS ('channel', 'medium')
      COMMENT = 'Marketing channel (Email, Social, etc)',
    MARKETING.CAMPAIGN_TYPE AS CAMPAIGN_TYPE
      WITH SYNONYMS ('type', 'category')
      COMMENT = 'Campaign type (Acquisition, Retention, etc)',
    MARKETING.AUDIENCE_SEGMENT AS AUDIENCE_SEGMENT
      WITH SYNONYMS ('segment', 'audience')
      COMMENT = 'Target audience segment',
    DATES.DATE_KEY AS DATE_KEY
      COMMENT = 'Date surrogate key',
    MARKETING.SEND_DATE_KEY AS SEND_DATE_KEY
      COMMENT = 'Marketing FK to date'
)

METRICS (
    MARKETING.TOTAL_TARGETED AS SUM(MARKETING.TARGET_COUNT)
      WITH SYNONYMS ('recipients', 'audience_size')
      COMMENT = 'Total recipients targeted',
    MARKETING.TOTAL_CONVERSIONS AS SUM(MARKETING.CONVERSION_COUNT)
      WITH SYNONYMS ('conversions', 'sales')
      COMMENT = 'Total conversion count',
    MARKETING.TOTAL_REVENUE AS SUM(MARKETING.REVENUE_ATTRIBUTED)
      WITH SYNONYMS ('revenue', 'attributed_revenue')
      COMMENT = 'Total revenue attributed to campaigns',
    MARKETING.AVG_OPEN_RATE AS AVG(MARKETING.OPEN_RATE)
      WITH SYNONYMS ('open_rate')
      COMMENT = 'Average email open rate',
    MARKETING.AVG_CLICK_RATE AS AVG(MARKETING.CLICK_RATE)
      WITH SYNONYMS ('ctr', 'click_rate')
      COMMENT = 'Average click-through rate',
    MARKETING.AVG_CONVERSION_RATE AS AVG(MARKETING.CONVERSION_RATE)
      COMMENT = 'Average conversion rate',
    MARKETING.REVENUE_PER_CONVERSION AS DIV0(
        SUM(MARKETING.REVENUE_ATTRIBUTED),
        NULLIF(SUM(MARKETING.CONVERSION_COUNT), 0)
    )
      WITH SYNONYMS ('aov', 'avg_order_value')
      COMMENT = 'Average revenue per conversion',
    MARKETING.CAMPAIGN_COUNT AS COUNT(MARKETING.MARKETING_KEY)
      COMMENT = 'Number of campaign touches'
)

COMMENT = 'Marketing analytics semantic view for campaign performance and ROI analysis'

WITH EXTENSION (CA = $$
{
  "module_custom_instructions": {
    "question_categorization": "Use this view for marketing questions: campaign performance, conversion rates, revenue attribution, and channel effectiveness. For customer-level campaign impact, join with customer dimension.",
    "sql_generation": "Group by CAMPAIGN_CHANNEL for channel analysis. Use CAMPAIGN_TYPE to compare acquisition vs retention. Calculate ROI as (TOTAL_REVENUE - campaign_cost) / campaign_cost when cost data available. Use DIV0 for safe division."
  },
  "verified_queries": [
    {
      "name": "revenue_conversions_by_channel",
      "question": "What is the total revenue and total conversions by campaign channel?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n    AM_SKI_RESORT.SEMANTIC.SEM_MARKETING_ANALYTICS\n    METRICS total_revenue, total_conversions\n    DIMENSIONS marketing.campaign_channel\n)",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": true
    },
    {
      "name": "revenue_conversion_rate_by_type_segment",
      "question": "What is the total revenue and average conversion rate by campaign type and audience segment?",
      "sql": "WITH __marketing AS (\n  SELECT\n    audience_segment,\n    campaign_type,\n    conversion_rate,\n    revenue_attributed\n  FROM AM_SKI_RESORT.MARTS.FACT_MARKETING\n) SELECT\n  m.campaign_type,\n  m.audience_segment,\n  SUM(m.revenue_attributed) AS total_revenue,\n  AVG(m.conversion_rate) AS avg_conversion_rate\nFROM __marketing AS m GROUP BY\n  m.campaign_type,\n  m.audience_segment\nORDER BY\n  total_revenue DESC NULLS LAST",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": true
    },
    {
      "name": "monthly_revenue_campaign_count",
      "question": "What is the monthly total revenue and campaign count by month name?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n    AM_SKI_RESORT.SEMANTIC.SEM_MARKETING_ANALYTICS\n    METRICS total_revenue, campaign_count\n    DIMENSIONS dates.month_name\n)",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": false
    },
    {
      "name": "open_click_rate_by_channel_type",
      "question": "What is the average open rate and average click rate by campaign channel and campaign type?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n    AM_SKI_RESORT.SEMANTIC.SEM_MARKETING_ANALYTICS\n    METRICS avg_open_rate, avg_click_rate\n    DIMENSIONS marketing.campaign_channel, marketing.campaign_type\n)",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": false
    },
    {
      "name": "revenue_per_conversion_by_segment",
      "question": "What is the revenue per conversion and total conversions by audience segment?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n    AM_SKI_RESORT.SEMANTIC.SEM_MARKETING_ANALYTICS\n    METRICS revenue_per_conversion, total_conversions\n    DIMENSIONS marketing.audience_segment\n) ORDER BY total_conversions DESC NULLS LAST",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": false
    }
  ]
}
$$)
