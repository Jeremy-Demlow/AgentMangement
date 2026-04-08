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
  }
}
$$)
