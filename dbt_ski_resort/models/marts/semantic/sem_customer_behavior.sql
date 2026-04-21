{{ config(materialized='semantic_view') }}

-- Customer behavior semantic view
-- Focuses on visit frequency, persona mix, and loyalty health

TABLES (
    DIM_CUSTOMER AS {{ ref('dim_customer') }}
      PRIMARY KEY (CUSTOMER_KEY)
      WITH SYNONYMS ('customers', 'guest_profiles')
      COMMENT = 'Customer persona, geography, and pass attributes',

    DIM_DATE AS {{ ref('dim_date') }}
      PRIMARY KEY (DATE_KEY)
      WITH SYNONYMS ('calendar', 'ski_calendar')
      COMMENT = 'Calendar dimension with ski-season classifications',

    FACT_PASS_USAGE AS {{ ref('fact_pass_usage') }}
      PRIMARY KEY (USAGE_KEY)
      WITH SYNONYMS ('pass_usage', 'skier_days')
      COMMENT = 'Daily pass usage fact capturing lift activity and time on mountain'
)

RELATIONSHIPS (
    PASS_USAGE_TO_DATE AS
      FACT_PASS_USAGE (DATE_KEY) REFERENCES DIM_DATE,
    PASS_USAGE_TO_CUSTOMER AS
      FACT_PASS_USAGE (CUSTOMER_KEY) REFERENCES DIM_CUSTOMER
)

FACTS (
    FACT_PASS_USAGE.TOTAL_LIFT_RIDES AS TOTAL_LIFT_RIDES
      COMMENT = 'Lift rides taken during the visit day',
    FACT_PASS_USAGE.HOURS_ON_MOUNTAIN AS HOURS_ON_MOUNTAIN
      COMMENT = 'Hours spent on mountain for the visit',
    FACT_PASS_USAGE.IS_WEEKEND AS IS_WEEKEND
      COMMENT = 'Indicates if the visit fell on a weekend'
)

DIMENSIONS (
    DIM_DATE.FULL_DATE AS FULL_DATE
      WITH SYNONYMS ('date')
      COMMENT = 'Date of the visit',
    DIM_DATE.SKI_SEASON AS SKI_SEASON
      WITH SYNONYMS ('season')
      COMMENT = 'Ski season identifier (YYYY-YYYY)',
    DIM_DATE.WEEK_OF_SEASON AS WEEK_OF_SEASON
      COMMENT = 'Week number within the ski season',
    DIM_DATE.IS_WEEKEND AS IS_WEEKEND
      COMMENT = 'Weekend flag from the calendar dimension',
    DIM_DATE.IS_HOLIDAY AS IS_HOLIDAY
      COMMENT = 'Holiday indicator',
    DIM_DATE.SNOW_CONDITION AS SNOW_CONDITION
      COMMENT = 'Snow surface quality classification',
    DIM_CUSTOMER.CUSTOMER_SEGMENT AS CUSTOMER_SEGMENT
      WITH SYNONYMS ('persona')
      COMMENT = 'Customer persona classification',
    DIM_CUSTOMER.AGE_GROUP AS AGE_GROUP
      COMMENT = 'Age group band',
    DIM_CUSTOMER.IS_PASS_HOLDER AS IS_PASS_HOLDER
      COMMENT = 'Indicates pass ownership',
    DIM_CUSTOMER.PASS_TYPE AS PASS_TYPE
      WITH SYNONYMS ('product_code')
      COMMENT = 'Pass or ticket product held',
    DIM_CUSTOMER.STATE AS STATE
      WITH SYNONYMS ('home_state')
      COMMENT = 'Home state for the guest',
    DIM_DATE.DATE_KEY AS DATE_KEY
      COMMENT = 'Date surrogate key',
    DIM_CUSTOMER.CUSTOMER_KEY AS CUSTOMER_KEY
      COMMENT = 'Customer surrogate key',
    FACT_PASS_USAGE.DATE_KEY AS DATE_KEY
      COMMENT = 'Pass usage FK to date',
    FACT_PASS_USAGE.CUSTOMER_KEY AS CUSTOMER_KEY
      COMMENT = 'Pass usage FK to customer'
)

METRICS (
    FACT_PASS_USAGE.TOTAL_VISITS AS COUNT(FACT_PASS_USAGE.USAGE_KEY)
      COMMENT = 'Total visit days recorded',
    FACT_PASS_USAGE.UNIQUE_CUSTOMERS AS COUNT(DISTINCT FACT_PASS_USAGE.CUSTOMER_KEY)
      COMMENT = 'Unique customers with activity',
    FACT_PASS_USAGE.PASS_HOLDER_VISITS AS COUNT(CASE WHEN DIM_CUSTOMER.IS_PASS_HOLDER THEN 1 END)
      COMMENT = 'Visits attributable to pass holders',
    FACT_PASS_USAGE.WEEKEND_VISITS AS COUNT(CASE WHEN DIM_DATE.IS_WEEKEND THEN 1 END)
      COMMENT = 'Visits occurring on weekends',
    FACT_PASS_USAGE.PASS_HOURS_TOTAL AS SUM(FACT_PASS_USAGE.HOURS_ON_MOUNTAIN)
      COMMENT = 'Total hours on mountain for all visits',
    FACT_PASS_USAGE.TOTAL_LIFT_RIDES_SUM AS SUM(FACT_PASS_USAGE.TOTAL_LIFT_RIDES)
      COMMENT = 'Total lift rides taken across visits',
    FACT_PASS_USAGE.VISITS_PER_CUSTOMER AS DIV0(
        COUNT(FACT_PASS_USAGE.USAGE_KEY),
        NULLIF(COUNT(DISTINCT FACT_PASS_USAGE.CUSTOMER_KEY), 0)
    )
      COMMENT = 'Average visits per active customer',
    FACT_PASS_USAGE.PASS_RETENTION_PCT AS DIV0(
        COUNT(DISTINCT CASE WHEN DIM_CUSTOMER.IS_PASS_HOLDER THEN FACT_PASS_USAGE.CUSTOMER_KEY END),
        NULLIF(COUNT(DISTINCT FACT_PASS_USAGE.CUSTOMER_KEY), 0)
    ) * 100
      COMMENT = 'Share of active customers who are pass holders (%)',
    FACT_PASS_USAGE.WEEKEND_SHARE_PCT AS DIV0(
        COUNT(CASE WHEN DIM_DATE.IS_WEEKEND THEN 1 END),
        NULLIF(COUNT(FACT_PASS_USAGE.USAGE_KEY), 0)
    ) * 100
      COMMENT = 'Percent of visits occurring on weekends',
    FACT_PASS_USAGE.AVERAGE_HOURS_PER_VISIT AS DIV0(
        SUM(FACT_PASS_USAGE.HOURS_ON_MOUNTAIN),
        NULLIF(COUNT(FACT_PASS_USAGE.USAGE_KEY), 0)
    )
      COMMENT = 'Average hours on mountain per visit',
    FACT_PASS_USAGE.AVERAGE_LIFT_RIDES_PER_VISIT AS DIV0(
        SUM(FACT_PASS_USAGE.TOTAL_LIFT_RIDES),
        NULLIF(COUNT(FACT_PASS_USAGE.USAGE_KEY), 0)
    )
      COMMENT = 'Average lift rides per visit'
)

COMMENT = 'Customer behavior semantic view for visit cadence, persona mix, and loyalty analysis'

WITH EXTENSION (CA = $$
{
  "module_custom_instructions": {
    "question_categorization": "Route lift wait or terrain utilization questions to SKI_RESORT_DB.SEMANTIC.SEM_OPERATIONS. Route revenue, pricing, or transaction questions to SKI_RESORT_DB.SEMANTIC.SEM_REVENUE. Route pass value, ROI, or renewal questions to SKI_RESORT_DB.SEMANTIC.SEM_PASSHOLDER_ANALYTICS. If a request references a specific guest without a CUSTOMER_ID or clear customer name, ask the user to supply that identifier before proceeding. Clarify whether the user wants day visitors, pass holders, or all guests when the persona scope is unclear. When no time frame is provided, default to the current SKI_SEASON and confirm with the user.",
    "sql_generation": "Filter seasonal analyses with DIM_DATE.SKI_SEASON; use DIM_DATE.FULL_DATE with DATE_TRUNC or DATEADD for calendar windows. Use DIM_DATE.IS_WEEKEND or FACT_PASS_USAGE.IS_WEEKEND to split weekend versus weekday behavior instead of recalculating flags. Aggregate visit metrics from FACT_PASS_USAGE and guard any division with DIV0(...). Break down personas with DIM_CUSTOMER.CUSTOMER_SEGMENT, STATE, and PASS_TYPE rather than ad-hoc string filters. When profiling specific cohorts, join only the declared tables and apply explicit filters (for example DIM_CUSTOMER.IS_PASS_HOLDER = TRUE) before aggregating."
  },
  "verified_queries": [
    {
      "name": "visits_by_segment",
      "question": "What are the total visits and unique customers by customer segment?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n    AM_SKI_RESORT.SEMANTIC.SEM_CUSTOMER_BEHAVIOR\n    DIMENSIONS dim_customer.customer_segment\n    METRICS total_visits, unique_customers\n)",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": true
    },
    {
      "name": "weekend_hours_by_season_pass",
      "question": "What is the weekend share percentage and average hours per visit by ski season and pass type?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n    AM_SKI_RESORT.SEMANTIC.SEM_CUSTOMER_BEHAVIOR\n    DIMENSIONS dim_date.ski_season, dim_customer.pass_type\n    METRICS weekend_share_pct, average_hours_per_visit\n) ORDER BY ski_season DESC NULLS LAST, pass_type NULLS LAST",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": true
    },
    {
      "name": "retention_by_season",
      "question": "What are the total visits, pass holder visits, and pass retention percentage by ski season?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n    AM_SKI_RESORT.SEMANTIC.SEM_CUSTOMER_BEHAVIOR\n    DIMENSIONS ski_season\n    METRICS total_visits, pass_holder_visits, pass_retention_pct\n) ORDER BY ski_season DESC NULLS LAST",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": false
    },
    {
      "name": "engagement_by_age_passholder",
      "question": "What are the visits per customer and average lift rides per visit by age group and pass holder status?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n    AM_SKI_RESORT.SEMANTIC.SEM_CUSTOMER_BEHAVIOR\n    METRICS visits_per_customer, average_lift_rides_per_visit\n    DIMENSIONS dim_customer.age_group, dim_customer.is_pass_holder\n)",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": false
    },
    {
      "name": "passholder_visits_by_state",
      "question": "What is the total visits and weekend visits by state for pass holders only?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n    AM_SKI_RESORT.SEMANTIC.SEM_CUSTOMER_BEHAVIOR\n    METRICS total_visits, weekend_visits\n    DIMENSIONS dim_customer.state\n    WHERE dim_customer.is_pass_holder = TRUE\n)",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": false
    }
  ]
}
$$)
