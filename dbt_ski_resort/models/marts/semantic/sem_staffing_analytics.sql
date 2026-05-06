{{
    config(
        materialized='semantic_view',
        schema='semantic'
    )
}}

-- Staffing Analytics semantic view
-- Analyzes staffing coverage, labor efficiency, and operational staffing

TABLES (
    STAFFING AS {{ ref('fact_staffing') }}
      PRIMARY KEY (STAFFING_KEY)
      WITH SYNONYMS ('staff', 'labor', 'schedule')
      COMMENT = 'Daily staffing schedules and coverage metrics',

    DATES AS {{ ref('dim_date') }}
      PRIMARY KEY (DATE_KEY)
      WITH SYNONYMS ('calendar', 'day_attributes')
      COMMENT = 'Calendar dimension with ski-season attributes',

    LOCATIONS AS {{ ref('dim_location') }}
      PRIMARY KEY (LOCATION_KEY)
      WITH SYNONYMS ('venue', 'facility')
      COMMENT = 'Physical locations for staffing'
)

RELATIONSHIPS (
    STAFFING_TO_DATE AS
      STAFFING (DATE_KEY) REFERENCES DATES (DATE_KEY),
    STAFFING_TO_LOCATION AS
      STAFFING (LOCATION_KEY) REFERENCES LOCATIONS (LOCATION_KEY)
)

FACTS (
    STAFFING.SCHEDULED_EMPLOYEES AS SCHEDULED_EMPLOYEES
      COMMENT = 'Number of employees scheduled',
    STAFFING.ACTUAL_EMPLOYEES AS ACTUAL_EMPLOYEES
      COMMENT = 'Actual employees who worked',
    STAFFING.COVERAGE_RATIO AS COVERAGE_RATIO
      COMMENT = 'Actual/Scheduled ratio',
    STAFFING.SHIFT_HOURS AS SHIFT_HOURS
      COMMENT = 'Duration of shift in hours',
    STAFFING.SCHEDULED_LABOR_HOURS AS SCHEDULED_LABOR_HOURS
      COMMENT = 'Total scheduled labor hours',
    STAFFING.ACTUAL_LABOR_HOURS AS ACTUAL_LABOR_HOURS
      COMMENT = 'Total actual labor hours'
)

DIMENSIONS (
    DATES.DATE_KEY AS DATE_KEY
      COMMENT = 'Date surrogate key',
    STAFFING.STAFFING_KEY AS STAFFING_KEY
      COMMENT = 'Staffing surrogate key',
    STAFFING.DATE_KEY AS DATE_KEY
      COMMENT = 'Staffing FK to date',
    STAFFING.LOCATION_KEY AS LOCATION_KEY
      COMMENT = 'Staffing FK to location',
    LOCATIONS.LOCATION_KEY AS LOCATION_KEY
      COMMENT = 'Location surrogate key',
    DATES.FULL_DATE AS FULL_DATE
      WITH SYNONYMS ('date', 'schedule_date')
      COMMENT = 'Date of staffing schedule',
    DATES.DAY_NAME AS DAY_NAME
      COMMENT = 'Day of week name',
    DATES.SKI_SEASON AS SKI_SEASON
      WITH SYNONYMS ('season')
      COMMENT = 'Ski season identifier',
    DATES.IS_WEEKEND AS IS_WEEKEND
      COMMENT = 'Weekend indicator',
    DATES.IS_HOLIDAY AS IS_HOLIDAY
      COMMENT = 'Holiday indicator',
    STAFFING.DEPARTMENT AS DEPARTMENT
      WITH SYNONYMS ('dept', 'team')
      COMMENT = 'Department (Lift Operations, F&B, etc)',
    STAFFING.JOB_ROLE AS JOB_ROLE
      WITH SYNONYMS ('role', 'position')
      COMMENT = 'Specific job role',
    LOCATIONS.LOCATION_NAME AS LOCATION_NAME
      WITH SYNONYMS ('venue', 'facility')
      COMMENT = 'Physical location name'
)

METRICS (
    STAFFING.TOTAL_SCHEDULED AS SUM(STAFFING.SCHEDULED_EMPLOYEES)
      WITH SYNONYMS ('planned_staff', 'expected_headcount')
      COMMENT = 'Total employees scheduled',
    STAFFING.TOTAL_ACTUAL AS SUM(STAFFING.ACTUAL_EMPLOYEES)
      WITH SYNONYMS ('actual_staff', 'actual_headcount')
      COMMENT = 'Total employees who actually worked',
    STAFFING.AVG_COVERAGE AS AVG(STAFFING.COVERAGE_RATIO)
      WITH SYNONYMS ('coverage', 'fill_rate')
      COMMENT = 'Average coverage ratio (actual/scheduled)',
    STAFFING.UNDERSTAFFED_COUNT AS COUNT(CASE WHEN STAFFING.IS_UNDERSTAFFED THEN 1 END)
      COMMENT = 'Count of understaffed shifts (< 90% coverage)',
    STAFFING.TOTAL_SCHEDULED_HOURS AS SUM(STAFFING.SCHEDULED_LABOR_HOURS)
      WITH SYNONYMS ('planned_hours')
      COMMENT = 'Total scheduled labor hours',
    STAFFING.TOTAL_ACTUAL_HOURS AS SUM(STAFFING.ACTUAL_LABOR_HOURS)
      WITH SYNONYMS ('worked_hours')
      COMMENT = 'Total actual labor hours worked',
    STAFFING.SHIFT_COUNT AS COUNT(STAFFING.STAFFING_KEY)
      COMMENT = 'Number of scheduled shifts'
)

COMMENT = 'Staffing analytics semantic view for labor management and coverage analysis'

WITH EXTENSION (CA = $$
{
  "module_custom_instructions": {
    "question_categorization": "Use this view for staffing questions: coverage ratios, labor hours, understaffing analysis, and department-level staffing. For visitor-to-staff ratios, join with pass_usage data.",
    "sql_generation": "Group by DEPARTMENT for department-level analysis. Use IS_UNDERSTAFFED filter for coverage issues. Calculate efficiency as ACTUAL_LABOR_HOURS / visitor_count when joined with visit data. Weekend and holiday staffing often differs significantly."
  },
  "verified_queries": [
    {
      "name": "hours_by_department",
      "question": "What is the total actual hours and total scheduled hours by department?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n    {{ target.database }}.SEMANTIC.SEM_STAFFING_ANALYTICS\n    METRICS total_actual_hours, total_scheduled_hours\n    DIMENSIONS department\n)",
      "verified_by": "Cortex Analyst",
      "verified_at": 1745200000,
      "use_as_onboarding_question": true
    },
    {
      "name": "worst_coverage_dept_day",
      "question": "Which department and day of week combinations have the worst average staffing coverage, and how do they rank?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n  {{ target.database }}.SEMANTIC.SEM_STAFFING_ANALYTICS\n  METRICS avg_coverage\n  DIMENSIONS department, day_name\n) ORDER BY avg_coverage ASC NULLS LAST",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": true
    },
    {
      "name": "holiday_staffing_gap",
      "question": "How does average staffing coverage on holidays compare to non-holidays for each department, and what is the coverage gap?",
      "sql": "WITH holiday_coverage AS (\n  SELECT *\n  FROM SEMANTIC_VIEW(\n    {{ target.database }}.SEMANTIC.SEM_STAFFING_ANALYTICS\n    METRICS avg_coverage\n    DIMENSIONS department, is_holiday\n  )\n), holiday AS (\n  SELECT department, avg_coverage AS holiday_avg_coverage\n  FROM holiday_coverage\n  WHERE is_holiday = TRUE\n), non_holiday AS (\n  SELECT department, avg_coverage AS non_holiday_avg_coverage\n  FROM holiday_coverage\n  WHERE is_holiday = FALSE\n) SELECT COALESCE(h.department, nh.department) AS department, h.holiday_avg_coverage, nh.non_holiday_avg_coverage, h.holiday_avg_coverage - nh.non_holiday_avg_coverage AS coverage_gap FROM holiday AS h FULL OUTER JOIN non_holiday AS nh ON h.department = nh.department ORDER BY coverage_gap NULLS LAST",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": false
    },
    {
      "name": "understaffing_by_job_role",
      "question": "What is the understaffed shift count and overstaffed shift count by job role?",
      "sql": "WITH __staffing AS (\n  SELECT job_role, staffing_key, coverage_ratio, is_understaffed\n  FROM {{ target.database }}.MARTS.FACT_STAFFING\n) SELECT s.job_role, COUNT(CASE WHEN s.is_understaffed THEN 1 END) AS understaffed_shift_count, COUNT(CASE WHEN NOT s.is_understaffed AND s.coverage_ratio > 1 THEN 1 END) AS overstaffed_shift_count FROM __staffing AS s GROUP BY s.job_role ORDER BY understaffed_shift_count DESC NULLS LAST",
      "verified_by": "Cortex Analyst",
      "verified_at": 1745200000,
      "use_as_onboarding_question": false
    },
    {
      "name": "understaffing_trend_by_location",
      "question": "What is the month-over-month trend of understaffed shift count by location?",
      "sql": "WITH __staffing AS (\n  SELECT date_key, location_key, is_understaffed\n  FROM {{ target.database }}.MARTS.FACT_STAFFING\n), __dates AS (\n  SELECT date_key, full_date\n  FROM {{ target.database }}.MARTS.DIM_DATE\n), __locations AS (\n  SELECT location_key, location_name\n  FROM {{ target.database }}.MARTS.DIM_LOCATION\n), monthly_understaffed AS (\n  SELECT l.location_name,\n  DATE_TRUNC('MONTH', d.full_date) AS month,\n  COUNT(CASE WHEN s.is_understaffed THEN 1 END) AS understaffed_count\n  FROM __staffing AS s\n  LEFT OUTER JOIN __dates AS d ON s.date_key = d.date_key\n  LEFT OUTER JOIN __locations AS l ON s.location_key = l.location_key\n  GROUP BY l.location_name, DATE_TRUNC('MONTH', d.full_date)\n), mom AS (\n  SELECT curr.location_name, curr.month AS curr_month, prev.month AS prev_month,\n  curr.understaffed_count AS curr_understaffed_count,\n  prev.understaffed_count AS prev_understaffed_count,\n  curr.understaffed_count - prev.understaffed_count AS mom_chg,\n  (curr.understaffed_count - prev.understaffed_count) / NULLIF(NULLIF(prev.understaffed_count, 0), 0) AS mom_pct_chg\n  FROM monthly_understaffed AS curr\n  LEFT JOIN monthly_understaffed AS prev\n    ON curr.location_name = prev.location_name\n    AND curr.month = prev.month + INTERVAL '1 MONTH'\n) SELECT * FROM mom ORDER BY curr_month DESC NULLS LAST, location_name",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": false
    }
  ]
}
$$)
