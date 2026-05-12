{{ config(materialized='semantic_view') }}

-- Executive daily summary semantic view
-- One-stop view for resort KPIs: visitors, revenue by segment
-- Based on FACT_PASS_USAGE as the primary grain (one row per visitor per day)

TABLES (
    DIM_DATE AS {{ ref('dim_date') }}
      PRIMARY KEY (DATE_KEY)
      WITH SYNONYMS ('calendar', 'dates')
      COMMENT = 'Calendar dimension with ski season classifications',

    DIM_CUSTOMER AS {{ ref('dim_customer') }}
      PRIMARY KEY (CUSTOMER_KEY)
      WITH SYNONYMS ('guests', 'visitors')
      COMMENT = 'Customer dimension with persona and pass information',

    FACT_PASS_USAGE AS {{ ref('fact_pass_usage') }}
      PRIMARY KEY (USAGE_KEY)
      WITH SYNONYMS ('visits', 'daily_attendance', 'skier_days')
      COMMENT = 'Daily visitor activity - one row per guest per ski day'
)

RELATIONSHIPS (
    VISITS_TO_DATE AS
      FACT_PASS_USAGE (DATE_KEY) REFERENCES DIM_DATE,
    VISITS_TO_CUSTOMER AS
      FACT_PASS_USAGE (CUSTOMER_KEY) REFERENCES DIM_CUSTOMER
)

FACTS (
    FACT_PASS_USAGE.TOTAL_LIFT_RIDES AS TOTAL_LIFT_RIDES
      COMMENT = 'Lift rides taken during the visit',
    FACT_PASS_USAGE.HOURS_ON_MOUNTAIN AS HOURS_ON_MOUNTAIN
      COMMENT = 'Time spent on mountain (hours)'
)

DIMENSIONS (
    DIM_DATE.DATE_KEY AS DATE_KEY
      COMMENT = 'Date surrogate key',
    DIM_CUSTOMER.CUSTOMER_KEY AS CUSTOMER_KEY
      COMMENT = 'Customer surrogate key',
    FACT_PASS_USAGE.USAGE_KEY AS USAGE_KEY
      COMMENT = 'Pass usage surrogate key',
    FACT_PASS_USAGE.DATE_KEY AS DATE_KEY
      COMMENT = 'Pass usage FK to date',
    FACT_PASS_USAGE.CUSTOMER_KEY AS CUSTOMER_KEY
      COMMENT = 'Pass usage FK to customer',
    -- Date dimensions
    DIM_DATE.FULL_DATE AS FULL_DATE
      WITH SYNONYMS ('date', 'day', 'visit_date')
      COMMENT = 'Calendar date of visit',
    DIM_DATE.DAY_NAME AS DAY_NAME
      COMMENT = 'Day of week name (Monday, Tuesday, etc)',
    DIM_DATE.MONTH_NAME AS MONTH_NAME
      COMMENT = 'Month name',
    DIM_DATE.CALENDAR_YEAR AS CALENDAR_YEAR
      COMMENT = 'Calendar year',
    DIM_DATE.SKI_SEASON AS SKI_SEASON
      WITH SYNONYMS ('season')
      COMMENT = 'Ski season identifier (YYYY-YYYY format)',
    DIM_DATE.WEEK_OF_SEASON AS WEEK_OF_SEASON
      COMMENT = 'Week number within the ski season (1-26)',
    DIM_DATE.SEASON_MONTH AS SEASON_MONTH
      COMMENT = 'Month of season (1=Nov, 6=Apr)',
    DIM_DATE.IS_WEEKEND AS IS_WEEKEND
      COMMENT = 'Weekend indicator (Saturday or Sunday)',
    DIM_DATE.IS_HOLIDAY AS IS_HOLIDAY
      COMMENT = 'Holiday indicator',
    DIM_DATE.HOLIDAY_NAME AS HOLIDAY_NAME
      COMMENT = 'Name of holiday if applicable',
    DIM_DATE.SNOW_CONDITION AS SNOW_CONDITION
      COMMENT = 'Snow quality (Excellent/Good/Fair)',

    -- Customer dimensions
    DIM_CUSTOMER.CUSTOMER_SEGMENT AS CUSTOMER_SEGMENT
      WITH SYNONYMS ('persona', 'segment')
      COMMENT = 'Customer persona classification',
    DIM_CUSTOMER.IS_PASS_HOLDER AS IS_PASS_HOLDER
      COMMENT = 'Pass holder indicator',
    DIM_CUSTOMER.PASS_TYPE AS PASS_TYPE
      COMMENT = 'Type of pass held',
    DIM_CUSTOMER.AGE_GROUP AS AGE_GROUP
      COMMENT = 'Customer age bracket',
    DIM_CUSTOMER.STATE AS STATE
      WITH SYNONYMS ('home_state')
      COMMENT = 'Customer home state'
)

METRICS (
    -- Core visitation metrics
    FACT_PASS_USAGE.TOTAL_VISITS AS COUNT(FACT_PASS_USAGE.USAGE_KEY)
      COMMENT = 'Total visitor count (skier visits)',
    FACT_PASS_USAGE.UNIQUE_VISITORS AS COUNT(DISTINCT FACT_PASS_USAGE.CUSTOMER_KEY)
      COMMENT = 'Unique guests',

    -- Activity metrics
    FACT_PASS_USAGE.TOTAL_LIFT_RIDES_SUM AS SUM(FACT_PASS_USAGE.TOTAL_LIFT_RIDES)
      COMMENT = 'Total lift rides across all visits',
    FACT_PASS_USAGE.TOTAL_MOUNTAIN_HOURS AS SUM(FACT_PASS_USAGE.HOURS_ON_MOUNTAIN)
      COMMENT = 'Total guest hours on mountain',

    -- Per-visit averages
    FACT_PASS_USAGE.AVG_RIDES_PER_VISIT AS DIV0(
        SUM(FACT_PASS_USAGE.TOTAL_LIFT_RIDES),
        NULLIF(COUNT(FACT_PASS_USAGE.USAGE_KEY), 0)
    )
      COMMENT = 'Average lift rides per visit',
    FACT_PASS_USAGE.AVG_HOURS_PER_VISIT AS DIV0(
        SUM(FACT_PASS_USAGE.HOURS_ON_MOUNTAIN),
        NULLIF(COUNT(FACT_PASS_USAGE.USAGE_KEY), 0)
    )
      COMMENT = 'Average hours on mountain per visit',

    -- Segment breakdowns
    FACT_PASS_USAGE.PASS_HOLDER_VISITS AS COUNT(CASE WHEN DIM_CUSTOMER.IS_PASS_HOLDER THEN 1 END)
      COMMENT = 'Visits from pass holders',
    FACT_PASS_USAGE.DAY_TICKET_VISITS AS COUNT(CASE WHEN NOT DIM_CUSTOMER.IS_PASS_HOLDER THEN 1 END)
      COMMENT = 'Visits from day ticket holders',
    FACT_PASS_USAGE.PASS_HOLDER_PCT AS DIV0(
        COUNT(CASE WHEN DIM_CUSTOMER.IS_PASS_HOLDER THEN 1 END),
        NULLIF(COUNT(FACT_PASS_USAGE.USAGE_KEY), 0)
    ) * 100
      COMMENT = 'Percent of visits from pass holders',

    -- Weekend patterns
    FACT_PASS_USAGE.WEEKEND_VISITS AS COUNT(CASE WHEN DIM_DATE.IS_WEEKEND THEN 1 END)
      COMMENT = 'Visits on weekends',
    FACT_PASS_USAGE.WEEKDAY_VISITS AS COUNT(CASE WHEN NOT DIM_DATE.IS_WEEKEND THEN 1 END)
      COMMENT = 'Visits on weekdays',
    FACT_PASS_USAGE.WEEKEND_SHARE_PCT AS DIV0(
        COUNT(CASE WHEN DIM_DATE.IS_WEEKEND THEN 1 END),
        NULLIF(COUNT(FACT_PASS_USAGE.USAGE_KEY), 0)
    ) * 100
      COMMENT = 'Percent of visits on weekends',

    -- Snow condition impact
    FACT_PASS_USAGE.EXCELLENT_SNOW_VISITS AS COUNT(CASE WHEN DIM_DATE.SNOW_CONDITION = 'Excellent' THEN 1 END)
      COMMENT = 'Visits on excellent snow days',
    FACT_PASS_USAGE.HOLIDAY_VISITS AS COUNT(CASE WHEN DIM_DATE.IS_HOLIDAY THEN 1 END)
      COMMENT = 'Visits on holidays',

    -- Visits per unique visitor (loyalty indicator)
    FACT_PASS_USAGE.VISITS_PER_GUEST AS DIV0(
        COUNT(FACT_PASS_USAGE.USAGE_KEY),
        NULLIF(COUNT(DISTINCT FACT_PASS_USAGE.CUSTOMER_KEY), 0)
    )
      COMMENT = 'Average visits per unique guest (frequency)'
)

COMMENT = 'Executive daily summary view - core resort KPIs for visitation and guest activity analysis'

WITH EXTENSION (CA = $$
{
  "module_custom_instructions": {
    "question_categorization": "This is the primary view for overall resort performance, visitor trends, and attendance patterns. Use it for questions about daily visitors, seasonal comparisons, weekend vs weekday patterns, and guest segment mix. Route detailed lift wait times to SEM_OPERATIONS. Route revenue and spend questions to SEM_REVENUE. Route pass holder ROI questions to SEM_PASSHOLDER_ANALYTICS. Route customer journey questions to SEM_CUSTOMER_BEHAVIOR. When no date is specified, default to the current SKI_SEASON.",
    "sql_generation": "Use DIM_DATE.FULL_DATE for daily analysis, DIM_DATE.SKI_SEASON for seasonal comparisons, and DATE_TRUNC for weekly/monthly trends. Segment by DIM_CUSTOMER.CUSTOMER_SEGMENT for persona insights and DIM_CUSTOMER.IS_PASS_HOLDER for pass vs day ticket analysis. Use DIM_DATE.IS_WEEKEND and DIM_DATE.IS_HOLIDAY for pattern analysis. All division should use DIV0() to handle zeros. For year-over-year, compare by WEEK_OF_SEASON across different SKI_SEASON values."
  },
  "verified_queries": [
    {
      "name": "visits_by_day_of_week",
      "question": "What is the total visits and unique visitors by day of week?",
      "sql": "WITH __fact_pass_usage AS (\n  SELECT customer_key, date_key, usage_key\n  FROM {{ target.database }}.MARTS.FACT_PASS_USAGE\n), __dim_date AS (\n  SELECT date_key, day_name\n  FROM {{ target.database }}.MARTS.DIM_DATE\n) SELECT d.day_name, COUNT(pu.usage_key) AS total_visits, COUNT(DISTINCT pu.customer_key) AS unique_visitors FROM __fact_pass_usage AS pu LEFT OUTER JOIN __dim_date AS d ON pu.date_key = d.date_key GROUP BY d.day_name ORDER BY total_visits DESC NULLS LAST",
      "verified_by": "Cortex Analyst",
      "verified_at": 1745200000,
      "use_as_onboarding_question": true
    },
    {
      "name": "season_visits_per_guest",
      "question": "What is the total visits and unique visitors per ski season, and what is the visits per guest ratio for each season?",
      "sql": "WITH __fact_pass_usage AS (\n  SELECT customer_key, date_key, usage_key\n  FROM {{ target.database }}.MARTS.FACT_PASS_USAGE\n), __dim_date AS (\n  SELECT date_key, ski_season\n  FROM {{ target.database }}.MARTS.DIM_DATE\n) SELECT d.ski_season, COUNT(pu.usage_key) AS total_visits, COUNT(DISTINCT pu.customer_key) AS unique_visitors, IFF(COUNT(DISTINCT pu.customer_key) = 0 AND NOT COUNT(pu.usage_key) IS NULL, 0,\n  COUNT(pu.usage_key) / NULLIF(COUNT(DISTINCT pu.customer_key), 0)) AS visits_per_guest\nFROM __fact_pass_usage AS pu LEFT OUTER JOIN __dim_date AS d ON pu.date_key = d.date_key GROUP BY d.ski_season ORDER BY d.ski_season DESC NULLS LAST",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": true
    },
    {
      "name": "visits_by_snow_condition",
      "question": "What is the total visits and average hours per visit by snow condition?",
      "sql": "WITH __fact_pass_usage AS (\n  SELECT customer_key, date_key, usage_key, hours_on_mountain\n  FROM {{ target.database }}.MARTS.FACT_PASS_USAGE\n), __dim_date AS (\n  SELECT date_key, snow_condition\n  FROM {{ target.database }}.MARTS.DIM_DATE\n) SELECT d.snow_condition, COUNT(pu.usage_key) AS total_visits, IFF(COUNT(pu.usage_key) = 0 AND NOT SUM(pu.hours_on_mountain) IS NULL, 0,\n  SUM(pu.hours_on_mountain) / NULLIF(COUNT(pu.usage_key), 0)) AS avg_hours_per_visit\nFROM __fact_pass_usage AS pu LEFT OUTER JOIN __dim_date AS d ON pu.date_key = d.date_key GROUP BY d.snow_condition ORDER BY total_visits DESC NULLS LAST",
      "verified_by": "Cortex Analyst",
      "verified_at": 1745200000,
      "use_as_onboarding_question": false
    },
    {
      "name": "weekend_weekday_by_season",
      "question": "What are the total weekend visits and total weekday visits by ski season?",
      "sql": "WITH __fact_pass_usage AS (\n  SELECT customer_key, date_key, usage_key\n  FROM {{ target.database }}.MARTS.FACT_PASS_USAGE\n), __dim_date AS (\n  SELECT date_key, is_weekend, ski_season\n  FROM {{ target.database }}.MARTS.DIM_DATE\n) SELECT d.ski_season, COUNT(CASE WHEN d.is_weekend THEN 1 END) AS weekend_visits, COUNT(CASE WHEN NOT d.is_weekend THEN 1 END) AS weekday_visits FROM __fact_pass_usage AS pu LEFT OUTER JOIN __dim_date AS d ON pu.date_key = d.date_key GROUP BY d.ski_season ORDER BY d.ski_season DESC NULLS LAST",
      "verified_by": "Cortex Analyst",
      "verified_at": 1745200000,
      "use_as_onboarding_question": false
    },
    {
      "name": "avg_rides_by_season",
      "question": "What is the average lift rides per visit and average hours per visit by ski season?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n  {{ target.database }}.SEMANTIC.SEM_DAILY_SUMMARY\n  METRICS avg_rides_per_visit, avg_hours_per_visit\n  DIMENSIONS ski_season\n) ORDER BY ski_season DESC NULLS LAST",
      "verified_by": "Cortex Analyst",
      "verified_at": 1745200000,
      "use_as_onboarding_question": false
    }
  ]
}
$$)
