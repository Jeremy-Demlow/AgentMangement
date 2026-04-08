{{ config(materialized='semantic_view') }}

-- Lift operations semantic view
-- Focuses on wait times, capacity utilization, and customer mix

TABLES (
    DIM_DATE AS {{ ref('dim_date') }}
      PRIMARY KEY (DATE_KEY)
      WITH SYNONYMS ('calendar', 'ski_calendar')
      COMMENT = 'Calendar dimension with ski-season attributes',

    DIM_LIFT AS {{ ref('dim_lift') }}
      PRIMARY KEY (LIFT_KEY)
      WITH SYNONYMS ('lifts', 'lift_infrastructure')
      COMMENT = 'Lift infrastructure metadata including terrain and capacity',

    DIM_CUSTOMER AS {{ ref('dim_customer') }}
      PRIMARY KEY (CUSTOMER_KEY)
      WITH SYNONYMS ('visitors', 'guests')
      COMMENT = 'Customer personas and pass status',

    FACT_LIFT_SCANS AS {{ ref('fact_lift_scans') }}
      PRIMARY KEY (SCAN_KEY)
      WITH SYNONYMS ('lift_scans', 'lift_usage_events')
      COMMENT = 'Granular lift scan fact with wait times and weather context'
)

RELATIONSHIPS (
    SCANS_TO_DATE AS
      FACT_LIFT_SCANS (DATE_KEY) REFERENCES DIM_DATE,
    SCANS_TO_LIFT AS
      FACT_LIFT_SCANS (LIFT_KEY) REFERENCES DIM_LIFT,
    SCANS_TO_CUSTOMER AS
      FACT_LIFT_SCANS (CUSTOMER_KEY) REFERENCES DIM_CUSTOMER
)

FACTS (
    FACT_LIFT_SCANS.WAIT_TIME_MINUTES AS WAIT_TIME_MINUTES
      COMMENT = 'Observed wait time at the lift in minutes',
    FACT_LIFT_SCANS.TEMPERATURE_F AS TEMPERATURE_F
      COMMENT = 'Temperature at scan time (Fahrenheit)',
    FACT_LIFT_SCANS.SCAN_HOUR AS SCAN_HOUR
      COMMENT = 'Hour of day for the scan event',
    FACT_LIFT_SCANS.WEATHER_CONDITION AS WEATHER_CONDITION
      COMMENT = 'Weather condition reported at scan time'
)

DIMENSIONS (
    DIM_DATE.FULL_DATE AS FULL_DATE
      WITH SYNONYMS ('date')
      COMMENT = 'Date of the lift scan',
    DIM_DATE.DAY_NAME AS DAY_NAME
      COMMENT = 'Day of week name',
    DIM_DATE.IS_WEEKEND AS IS_WEEKEND
      COMMENT = 'Weekend indicator',
    DIM_DATE.IS_HOLIDAY AS IS_HOLIDAY
      COMMENT = 'Holiday indicator',
    DIM_DATE.SKI_SEASON AS SKI_SEASON
      COMMENT = 'Ski season identifier (YYYY-YYYY)',
    DIM_DATE.SNOW_CONDITION AS SNOW_CONDITION
      COMMENT = 'Snow surface quality classification',
    DIM_LIFT.LIFT_NAME AS LIFT_NAME
      WITH SYNONYMS ('lift')
      COMMENT = 'Operational lift name',
    DIM_LIFT.LIFT_TYPE AS LIFT_TYPE
      COMMENT = 'Lift infrastructure type',
    DIM_LIFT.TERRAIN_TYPE AS TERRAIN_TYPE
      COMMENT = 'Primary terrain serviced by the lift',
    DIM_LIFT.DIFFICULTY_ACCESS AS DIFFICULTY_ACCESS
      COMMENT = 'Ability level required to access the lift',
    DIM_LIFT.CAPACITY_PER_HOUR AS CAPACITY_PER_HOUR
      COMMENT = 'Theoretical throughput per hour',
    DIM_CUSTOMER.CUSTOMER_SEGMENT AS CUSTOMER_SEGMENT
      WITH SYNONYMS ('persona')
      COMMENT = 'Customer persona classification',
    DIM_CUSTOMER.IS_PASS_HOLDER AS IS_PASS_HOLDER
      COMMENT = 'Indicates if the rider is a pass holder'
)

METRICS (
    FACT_LIFT_SCANS.TOTAL_SCANS AS COUNT(FACT_LIFT_SCANS.SCAN_KEY)
      COMMENT = 'Total lift scans recorded',
    FACT_LIFT_SCANS.UNIQUE_RIDERS AS COUNT(DISTINCT FACT_LIFT_SCANS.CUSTOMER_KEY)
      COMMENT = 'Unique riders captured in the scans',
    FACT_LIFT_SCANS.AVG_WAIT_MINUTES AS AVG(FACT_LIFT_SCANS.WAIT_TIME_MINUTES)
      COMMENT = 'Average wait time in minutes',
    FACT_LIFT_SCANS.P95_WAIT_MINUTES AS APPROX_PERCENTILE(FACT_LIFT_SCANS.WAIT_TIME_MINUTES, 0.95)
      COMMENT = '95th percentile wait time (minutes)',
    FACT_LIFT_SCANS.MAX_WAIT_MINUTES AS MAX(FACT_LIFT_SCANS.WAIT_TIME_MINUTES)
      COMMENT = 'Maximum wait time observed',
    FACT_LIFT_SCANS.POWDER_DAY_SCANS AS COUNT(CASE WHEN DIM_DATE.SNOW_CONDITION = 'Excellent' THEN 1 END)
      COMMENT = 'Ride volume on excellent snow days',
    FACT_LIFT_SCANS.WEEKEND_WAIT_DELTA AS (
        AVG(CASE WHEN DIM_DATE.IS_WEEKEND THEN FACT_LIFT_SCANS.WAIT_TIME_MINUTES END)
        -
        AVG(CASE WHEN NOT DIM_DATE.IS_WEEKEND THEN FACT_LIFT_SCANS.WAIT_TIME_MINUTES END)
    )
      COMMENT = 'Weekend vs weekday wait time difference (minutes)',
    FACT_LIFT_SCANS.EARLY_MORNING_SCANS AS COUNT(CASE WHEN FACT_LIFT_SCANS.SCAN_HOUR < 10 THEN 1 END)
      COMMENT = 'Lift scans occurring before 10am',
    FACT_LIFT_SCANS.PASS_HOLDER_SHARE_PCT AS DIV0(
        COUNT(CASE WHEN DIM_CUSTOMER.IS_PASS_HOLDER THEN 1 END),
        NULLIF(COUNT(FACT_LIFT_SCANS.SCAN_KEY), 0)
    ) * 100
      COMMENT = 'Percent of scans attributable to pass holders',
    FACT_LIFT_SCANS.CAPACITY_UTILIZATION_PCT AS DIV0(
        COUNT(FACT_LIFT_SCANS.SCAN_KEY),
        NULLIF(SUM(DIM_LIFT.CAPACITY_PER_HOUR), 0)
    ) * 100
      COMMENT = 'Utilization versus theoretical lift capacity (%)'
)

COMMENT = 'Lift operations semantic view for wait times, capacity, and customer mix analysis'

WITH EXTENSION (CA = $$
{
  "module_custom_instructions": {
    "question_categorization": "Route customer persona or churn questions to SKI_RESORT_DB.SEMANTIC.SEM_CUSTOMER_BEHAVIOR. Route revenue, ticketing, or spend topics to SKI_RESORT_DB.SEMANTIC.SEM_REVENUE. Route pass ROI or renewal effectiveness to SKI_RESORT_DB.SEMANTIC.SEM_PASSHOLDER_ANALYTICS. If a question does not specify the targeted LIFT_NAME, TERRAIN_TYPE, or SKI_SEASON, ask the user to provide that context before answering. Keep snowmaking, rentals, or food & beverage utilization requests outside this view unless they directly relate to lift performance.",
    "sql_generation": "Slice temporal windows with DIM_DATE.FULL_DATE or DIM_DATE.SKI_SEASON and rely on DATE_TRUNC/DATEADD for trend groupings. Use FACT_LIFT_SCANS.WAIT_TIME_MINUTES for wait calculations and DIM_LIFT.CAPACITY_PER_HOUR when computing utilization; wrap ratios with DIV0(...). Reuse DIM_DATE.IS_WEEKEND and DIM_DATE.SNOW_CONDITION flags instead of recomputing conditions. Bring customer mix context in through DIM_CUSTOMER.CUSTOMER_SEGMENT or DIM_CUSTOMER.IS_PASS_HOLDER when needed. When ranking lifts, include ORDER BY clauses with NULLS LAST so populated metrics surface first."
  }
}
$$)
