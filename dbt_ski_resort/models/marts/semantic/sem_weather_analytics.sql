{{
    config(
        materialized='semantic_view',
        schema='semantic'
    )
}}

-- Weather Analytics semantic view
-- Analyzes weather impact on resort operations and attendance

TABLES (
    WEATHER AS {{ ref('fact_weather') }}
      PRIMARY KEY (WEATHER_KEY)
      WITH SYNONYMS ('conditions', 'snow_report')
      COMMENT = 'Daily weather conditions by mountain zone',

    DATES AS {{ ref('dim_date') }}
      PRIMARY KEY (DATE_KEY)
      WITH SYNONYMS ('calendar', 'day_attributes')
      COMMENT = 'Calendar dimension with ski-season attributes'
)

RELATIONSHIPS (
    WEATHER_TO_DATE AS
      WEATHER (DATE_KEY) REFERENCES DATES (DATE_KEY)
)

FACTS (
    WEATHER.SNOWFALL_INCHES AS SNOWFALL_INCHES
      COMMENT = 'New snowfall in inches',
    WEATHER.BASE_DEPTH_INCHES AS BASE_DEPTH_INCHES
      COMMENT = 'Snow base depth in inches',
    WEATHER.TEMP_HIGH_F AS TEMP_HIGH_F
      COMMENT = 'High temperature (Fahrenheit)',
    WEATHER.TEMP_LOW_F AS TEMP_LOW_F
      COMMENT = 'Low temperature (Fahrenheit)',
    WEATHER.WIND_SPEED_MPH AS WIND_SPEED_MPH
      COMMENT = 'Wind speed in MPH'
)

DIMENSIONS (
    DATES.FULL_DATE AS FULL_DATE
      WITH SYNONYMS ('date', 'weather_date')
      COMMENT = 'Date of weather observation',
    DATES.DAY_NAME AS DAY_NAME
      COMMENT = 'Day of week name',
    DATES.SKI_SEASON AS SKI_SEASON
      WITH SYNONYMS ('season')
      COMMENT = 'Ski season identifier',
    DATES.MONTH_NAME AS MONTH_NAME
      COMMENT = 'Month name',
    DATES.IS_WEEKEND AS IS_WEEKEND
      COMMENT = 'Weekend indicator',
    DATES.IS_HOLIDAY AS IS_HOLIDAY
      COMMENT = 'Holiday indicator',
    WEATHER.MOUNTAIN_ZONE AS MOUNTAIN_ZONE
      WITH SYNONYMS ('zone', 'area')
      COMMENT = 'Mountain zone (Summit Peak, North Ridge, etc)',
    WEATHER.SNOW_CONDITION AS SNOW_CONDITION
      WITH SYNONYMS ('surface', 'conditions')
      COMMENT = 'Snow surface condition'
)

METRICS (
    WEATHER.TOTAL_SNOWFALL AS SUM(WEATHER.SNOWFALL_INCHES)
      WITH SYNONYMS ('new_snow', 'fresh_snow')
      COMMENT = 'Total new snowfall in inches',
    WEATHER.MAX_SNOWFALL AS MAX(WEATHER.SNOWFALL_INCHES)
      COMMENT = 'Maximum single-day snowfall',
    WEATHER.MAX_BASE_DEPTH AS MAX(WEATHER.BASE_DEPTH_INCHES)
      WITH SYNONYMS ('deepest_base')
      COMMENT = 'Maximum base depth observed',
    WEATHER.MIN_TEMP AS MIN(WEATHER.TEMP_LOW_F)
      COMMENT = 'Minimum temperature observed (F)',
    WEATHER.MAX_TEMP AS MAX(WEATHER.TEMP_HIGH_F)
      COMMENT = 'Maximum temperature observed (F)',
    WEATHER.MAX_WIND AS MAX(WEATHER.WIND_SPEED_MPH)
      COMMENT = 'Maximum wind speed observed (MPH)',
    WEATHER.AVG_SNOWFALL AS AVG(WEATHER.SNOWFALL_INCHES)
      COMMENT = 'Average snowfall per observation',
    WEATHER.POWDER_DAY_COUNT AS COUNT(CASE WHEN WEATHER.IS_POWDER_DAY THEN 1 END)
      WITH SYNONYMS ('powder_days')
      COMMENT = 'Count of powder days (6+ inches new snow)',
    WEATHER.HIGH_WIND_COUNT AS COUNT(CASE WHEN WEATHER.IS_HIGH_WIND THEN 1 END)
      COMMENT = 'Count of high wind days (25+ mph)',
    WEATHER.STORM_COUNT AS COUNT(CASE WHEN WEATHER.STORM_WARNING THEN 1 END)
      COMMENT = 'Count of storm warning days',
    WEATHER.OBSERVATION_COUNT AS COUNT(WEATHER.WEATHER_KEY)
      COMMENT = 'Number of weather observations'
)

COMMENT = 'Weather analytics semantic view for analyzing conditions and their impact'

WITH EXTENSION (CA = $$
{
  "module_custom_instructions": {
    "question_categorization": "Use this view for weather-related questions: snowfall, temperature, wind, powder days, and conditions analysis. For attendance impact correlation, join with pass_usage or lift_scans data.",
    "sql_generation": "Group by MOUNTAIN_ZONE for zone-specific analysis. Use DATES.SKI_SEASON for seasonal comparisons. Filter on IS_POWDER_DAY for powder day analysis. Use DATE_TRUNC for time-based aggregations."
  }
}
$$)
