{{ config(materialized='semantic_view') }}

TABLES (
    DIM_DATE AS {{ ref('dim_date') }}
      PRIMARY KEY (DATE_KEY)
      WITH SYNONYMS ('calendar', 'ski_calendar', 'resort_calendar')
      COMMENT = 'Calendar dimension with season attributes (winter skiing and summer recreation)',

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
      WITH SYNONYMS ('lift_scans', 'lift_usage_events', 'activity_scans')
      COMMENT = 'Granular lift/gondola scan fact with wait times and weather context (winter ski + summer bike uplift/scenic rides)',

    FACT_LIFT_MAINTENANCE AS {{ ref('fact_lift_maintenance') }}
      PRIMARY KEY (MAINTENANCE_KEY)
      WITH SYNONYMS ('maintenance', 'lift_maintenance', 'repairs', 'inspections')
      COMMENT = 'Lift maintenance activities including inspections, repairs, and adjustments',

    FACT_GROOMING AS {{ ref('fact_grooming') }}
      PRIMARY KEY (GROOMING_KEY)
      WITH SYNONYMS ('grooming', 'trail_grooming', 'grooming_logs', 'trail_maintenance')
      COMMENT = 'Trail grooming/maintenance operations with conditions before and after (snow grooming in winter, trail repair in summer)'
)

RELATIONSHIPS (
    SCANS_TO_DATE AS
      FACT_LIFT_SCANS (DATE_KEY) REFERENCES DIM_DATE,
    SCANS_TO_LIFT AS
      FACT_LIFT_SCANS (LIFT_KEY) REFERENCES DIM_LIFT,
    SCANS_TO_CUSTOMER AS
      FACT_LIFT_SCANS (CUSTOMER_KEY) REFERENCES DIM_CUSTOMER,
    MAINTENANCE_TO_DATE AS
      FACT_LIFT_MAINTENANCE (DATE_KEY) REFERENCES DIM_DATE,
    MAINTENANCE_TO_LIFT AS
      FACT_LIFT_MAINTENANCE (LIFT_KEY) REFERENCES DIM_LIFT,
    GROOMING_TO_DATE AS
      FACT_GROOMING (DATE_KEY) REFERENCES DIM_DATE
)

FACTS (
    FACT_LIFT_SCANS.WAIT_TIME_MINUTES AS WAIT_TIME_MINUTES
      COMMENT = 'Observed wait time at the lift in minutes',
    FACT_LIFT_SCANS.TEMPERATURE_F AS TEMPERATURE_F
      COMMENT = 'Temperature at scan time (Fahrenheit)',
    FACT_LIFT_SCANS.SCAN_HOUR AS SCAN_HOUR
      COMMENT = 'Hour of day for the scan event',
    FACT_LIFT_SCANS.WEATHER_CONDITION AS WEATHER_CONDITION
      COMMENT = 'Weather condition reported at scan time',

    FACT_LIFT_MAINTENANCE.DOWNTIME_MINUTES AS DOWNTIME_MINUTES
      COMMENT = 'Minutes of lift downtime due to maintenance',
    FACT_LIFT_MAINTENANCE.TOTAL_COST AS TOTAL_COST
      COMMENT = 'Total maintenance cost (parts + labor)',
    FACT_LIFT_MAINTENANCE.PARTS_COST AS PARTS_COST
      COMMENT = 'Parts cost for maintenance',
    FACT_LIFT_MAINTENANCE.LABOR_COST AS LABOR_COST
      COMMENT = 'Labor cost for maintenance',
    FACT_LIFT_MAINTENANCE.LABOR_HOURS AS LABOR_HOURS
      COMMENT = 'Labor hours for maintenance',

    FACT_GROOMING.DURATION_MINUTES AS DURATION_MINUTES
      COMMENT = 'Grooming duration in minutes',
    FACT_GROOMING.SNOW_DEPTH_INCHES AS SNOW_DEPTH_INCHES
      COMMENT = 'Snow depth at time of grooming (inches)',
    FACT_GROOMING.FUEL_USED_GALLONS AS FUEL_USED_GALLONS
      COMMENT = 'Fuel consumed during grooming (gallons)'
)

DIMENSIONS (
    DIM_DATE.DATE_KEY AS DATE_KEY
      COMMENT = 'Date surrogate key',
    DIM_DATE.FULL_DATE AS FULL_DATE
      WITH SYNONYMS ('date')
      COMMENT = 'Date of the operation event',
    DIM_DATE.DAY_NAME AS DAY_NAME
      COMMENT = 'Day of week name',
    DIM_DATE.IS_WEEKEND AS IS_WEEKEND
      COMMENT = 'Weekend indicator',
    DIM_DATE.IS_HOLIDAY AS IS_HOLIDAY
      COMMENT = 'Holiday indicator',
    DIM_DATE.SKI_SEASON AS SKI_SEASON
      COMMENT = 'Ski season identifier (YYYY-YYYY)',
    DIM_DATE.SEASON_TYPE AS SEASON_TYPE
      WITH SYNONYMS ('operating_season')
      COMMENT = 'Season type: winter (Nov-Apr) or summer (May-Oct)',
    DIM_DATE.SNOW_CONDITION AS SNOW_CONDITION
      COMMENT = 'Snow surface quality classification (N/A in summer)',
    DIM_LIFT.LIFT_KEY AS LIFT_KEY
      COMMENT = 'Lift surrogate key',
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
    DIM_CUSTOMER.CUSTOMER_KEY AS CUSTOMER_KEY
      COMMENT = 'Customer surrogate key',
    DIM_CUSTOMER.CUSTOMER_SEGMENT AS CUSTOMER_SEGMENT
      WITH SYNONYMS ('persona')
      COMMENT = 'Customer persona classification',
    DIM_CUSTOMER.IS_PASS_HOLDER AS IS_PASS_HOLDER
      COMMENT = 'Indicates if the rider is a pass holder',

    FACT_LIFT_SCANS.SCAN_KEY AS SCAN_KEY
      COMMENT = 'Lift scan surrogate key',
    FACT_LIFT_SCANS.DATE_KEY AS DATE_KEY
      COMMENT = 'Lift scans FK to date',
    FACT_LIFT_SCANS.LIFT_KEY AS LIFT_KEY
      COMMENT = 'Lift scans FK to lift',
    FACT_LIFT_SCANS.CUSTOMER_KEY AS CUSTOMER_KEY
      COMMENT = 'Lift scans FK to customer',
    FACT_LIFT_MAINTENANCE.MAINTENANCE_KEY AS MAINTENANCE_KEY
      COMMENT = 'Maintenance event surrogate key',
    FACT_LIFT_MAINTENANCE.DATE_KEY AS DATE_KEY
      COMMENT = 'Maintenance FK to date',
    FACT_LIFT_MAINTENANCE.LIFT_KEY AS LIFT_KEY
      COMMENT = 'Maintenance FK to lift',
    FACT_LIFT_MAINTENANCE.MAINTENANCE_TYPE AS MAINTENANCE_TYPE
      WITH SYNONYMS ('maint_type')
      COMMENT = 'Type of maintenance (inspection, repair, adjustment)',
    FACT_LIFT_MAINTENANCE.CATEGORY AS CATEGORY
      COMMENT = 'Maintenance category (mechanical, electrical, routine, safety)',
    FACT_LIFT_MAINTENANCE.DURING_OPERATING_HOURS AS DURING_OPERATING_HOURS
      COMMENT = 'Whether maintenance occurred during operating hours',
    FACT_LIFT_MAINTENANCE.PASSED_INSPECTION AS PASSED_INSPECTION
      COMMENT = 'Whether lift passed inspection after maintenance',
    FACT_LIFT_MAINTENANCE.FOLLOWUP_REQUIRED AS FOLLOWUP_REQUIRED
      COMMENT = 'Whether follow-up maintenance is needed',
    FACT_LIFT_MAINTENANCE.PARTS_REPLACED AS PARTS_REPLACED
      COMMENT = 'Whether parts were replaced during maintenance',

    FACT_GROOMING.GROOMING_KEY AS GROOMING_KEY
      COMMENT = 'Grooming event surrogate key',
    FACT_GROOMING.DATE_KEY AS DATE_KEY
      COMMENT = 'Grooming FK to date',
    FACT_GROOMING.TRAIL_NAME AS TRAIL_NAME
      WITH SYNONYMS ('groomed_trail')
      COMMENT = 'Trail that was groomed',
    FACT_GROOMING.GROOMING_TYPE AS GROOMING_TYPE
      COMMENT = 'Type of grooming performed',
    FACT_GROOMING.SHIFT AS SHIFT
      COMMENT = 'Grooming shift (Day, Night, Early Morning)',
    FACT_GROOMING.CONDITIONS_BEFORE AS CONDITIONS_BEFORE
      COMMENT = 'Trail condition before grooming',
    FACT_GROOMING.CONDITIONS_AFTER AS CONDITIONS_AFTER
      COMMENT = 'Trail condition after grooming',
    FACT_GROOMING.CONDITION_IMPROVED AS CONDITION_IMPROVED
      COMMENT = 'Whether grooming improved trail condition'
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
      COMMENT = 'Utilization versus theoretical lift capacity (%)',

    FACT_LIFT_MAINTENANCE.TOTAL_MAINTENANCE_EVENTS AS COUNT(FACT_LIFT_MAINTENANCE.MAINTENANCE_KEY)
      COMMENT = 'Total maintenance events recorded',
    FACT_LIFT_MAINTENANCE.TOTAL_MAINTENANCE_COST AS SUM(FACT_LIFT_MAINTENANCE.TOTAL_COST)
      COMMENT = 'Total maintenance spend (parts + labor)',
    FACT_LIFT_MAINTENANCE.AVG_MAINTENANCE_COST AS AVG(FACT_LIFT_MAINTENANCE.TOTAL_COST)
      COMMENT = 'Average cost per maintenance event',
    FACT_LIFT_MAINTENANCE.TOTAL_DOWNTIME_MINUTES AS SUM(FACT_LIFT_MAINTENANCE.DOWNTIME_MINUTES)
      COMMENT = 'Total lift downtime from maintenance (minutes)',
    FACT_LIFT_MAINTENANCE.AVG_DOWNTIME_MINUTES AS AVG(FACT_LIFT_MAINTENANCE.DOWNTIME_MINUTES)
      COMMENT = 'Average downtime per maintenance event (minutes)',
    FACT_LIFT_MAINTENANCE.INSPECTION_PASS_RATE AS DIV0(
        COUNT(CASE WHEN FACT_LIFT_MAINTENANCE.PASSED_INSPECTION THEN 1 END),
        NULLIF(COUNT(FACT_LIFT_MAINTENANCE.MAINTENANCE_KEY), 0)
    ) * 100
      COMMENT = 'Percentage of maintenance events that passed inspection',
    FACT_LIFT_MAINTENANCE.FOLLOWUP_RATE AS DIV0(
        COUNT(CASE WHEN FACT_LIFT_MAINTENANCE.FOLLOWUP_REQUIRED THEN 1 END),
        NULLIF(COUNT(FACT_LIFT_MAINTENANCE.MAINTENANCE_KEY), 0)
    ) * 100
      COMMENT = 'Percentage of maintenance events requiring follow-up',
    FACT_LIFT_MAINTENANCE.TOTAL_LABOR_HOURS AS SUM(FACT_LIFT_MAINTENANCE.LABOR_HOURS)
      COMMENT = 'Total labor hours spent on maintenance',

    FACT_GROOMING.TOTAL_GROOMING_RUNS AS COUNT(FACT_GROOMING.GROOMING_KEY)
      COMMENT = 'Total grooming runs completed',
    FACT_GROOMING.TOTAL_GROOMING_MINUTES AS SUM(FACT_GROOMING.DURATION_MINUTES)
      COMMENT = 'Total grooming time (minutes)',
    FACT_GROOMING.AVG_GROOMING_DURATION AS AVG(FACT_GROOMING.DURATION_MINUTES)
      COMMENT = 'Average grooming run duration (minutes)',
    FACT_GROOMING.TOTAL_FUEL_USED AS SUM(FACT_GROOMING.FUEL_USED_GALLONS)
      COMMENT = 'Total fuel consumed by grooming operations (gallons)',
    FACT_GROOMING.CONDITION_IMPROVEMENT_RATE AS DIV0(
        COUNT(CASE WHEN FACT_GROOMING.CONDITION_IMPROVED THEN 1 END),
        NULLIF(COUNT(FACT_GROOMING.GROOMING_KEY), 0)
    ) * 100
      COMMENT = 'Percentage of grooming runs that improved trail conditions',
    FACT_GROOMING.AVG_SNOW_DEPTH AS AVG(FACT_GROOMING.SNOW_DEPTH_INCHES)
      COMMENT = 'Average snow depth at time of grooming (inches)'
)

COMMENT = 'Operations semantic view covering lift usage, maintenance, and trail grooming for comprehensive resort operations analysis'

WITH EXTENSION (CA = $$
{
  "module_custom_instructions": {
    "question_categorization": "This view covers three operational domains: (1) Lift scans and wait times, (2) Lift maintenance and inspections, (3) Trail grooming operations. Route customer persona or churn questions to SEM_CUSTOMER_BEHAVIOR. Route revenue, ticketing, or spend topics to SEM_REVENUE. Route pass ROI or renewal effectiveness to SEM_PASSHOLDER_ANALYTICS. For maintenance questions, use FACT_LIFT_MAINTENANCE metrics (downtime, cost, inspection pass rate). For grooming questions, use FACT_GROOMING metrics (duration, fuel, condition improvement). For lift performance, use FACT_LIFT_SCANS metrics (wait times, utilization).",
    "sql_generation": "Slice temporal windows with DIM_DATE.FULL_DATE or DIM_DATE.SKI_SEASON and rely on DATE_TRUNC/DATEADD for trend groupings. Use DIM_DATE.SEASON_TYPE to filter winter vs summer operations (winter = ski lift scans + snow grooming; summer = bike uplift/scenic gondola scans + trail maintenance). Use FACT_LIFT_SCANS.WAIT_TIME_MINUTES for wait calculations and DIM_LIFT.CAPACITY_PER_HOUR when computing utilization; wrap ratios with DIV0(...). For maintenance analysis, join through MAINTENANCE_TO_LIFT to get lift names. For grooming analysis, use FACT_GROOMING.TRAIL_NAME directly. Reuse DIM_DATE.IS_WEEKEND and DIM_DATE.SNOW_CONDITION flags instead of recomputing conditions. When ranking lifts by maintenance cost or downtime, include ORDER BY clauses with NULLS LAST. When asking about recent or current operations without a season filter, include ALL data."
  },
  "verified_queries": [
    {
      "name": "maintenance_cost_by_lift",
      "question": "What is the total maintenance cost and maintenance event count by lift name?",
      "sql": "WITH __fact_lift_maintenance AS (\n  SELECT lift_key, maintenance_key, total_cost\n  FROM {{ target.database }}.MARTS.FACT_LIFT_MAINTENANCE\n), __dim_lift AS (\n  SELECT lift_key, lift_name\n  FROM {{ target.database }}.MARTS.DIM_LIFT\n) SELECT l.lift_name, COUNT(m.maintenance_key) AS total_maintenance_events, SUM(m.total_cost) AS total_maintenance_cost FROM __fact_lift_maintenance AS m LEFT OUTER JOIN __dim_lift AS l ON m.lift_key = l.lift_key GROUP BY l.lift_name ORDER BY total_maintenance_cost DESC NULLS LAST",
      "verified_by": "Cortex Analyst",
      "verified_at": 1745200000,
      "use_as_onboarding_question": true
    },
    {
      "name": "scans_wait_by_terrain",
      "question": "What is the average wait time minutes and total scans by terrain type?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n  {{ target.database }}.SEMANTIC.SEM_OPERATIONS\n  METRICS avg_wait_minutes, total_scans\n  DIMENSIONS terrain_type\n)",
      "verified_by": "Cortex Analyst",
      "verified_at": 1745200000,
      "use_as_onboarding_question": true
    },
    {
      "name": "scans_wait_by_lift",
      "question": "What is the total lift scans and average wait time minutes by lift name?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n  {{ target.database }}.SEMANTIC.SEM_OPERATIONS\n  METRICS total_scans, avg_wait_minutes\n  DIMENSIONS lift_name\n)",
      "verified_by": "Cortex Analyst",
      "verified_at": 1745200000,
      "use_as_onboarding_question": false
    },
    {
      "name": "grooming_effectiveness_by_type",
      "question": "Which trails have the best grooming condition improvement rate, and what grooming types are most effective?",
      "sql": "WITH __fact_grooming AS (\n  SELECT condition_improved, grooming_key, grooming_type, trail_name\n  FROM {{ target.database }}.MARTS.FACT_GROOMING\n) SELECT g.trail_name, g.grooming_type, COUNT(g.grooming_key) AS total_runs, COUNT(CASE WHEN g.condition_improved THEN 1 END) AS improved_runs, COUNT(CASE WHEN g.condition_improved THEN 1 END) * 100.0 / NULLIF(NULLIF(COUNT(g.grooming_key), 0), 0) AS improvement_rate_pct FROM __fact_grooming AS g GROUP BY g.trail_name, g.grooming_type ORDER BY improvement_rate_pct DESC NULLS LAST, total_runs DESC NULLS LAST",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": false
    }
  ]
}
$$)
