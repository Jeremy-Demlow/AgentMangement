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
      COMMENT = 'Target audience segment'
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
  }
}
$$)
