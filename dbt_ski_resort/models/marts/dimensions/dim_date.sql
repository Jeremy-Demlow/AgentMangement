{{
    config(
        materialized='table',
        schema='marts'
    )
}}

-- Date dimension for ski resort analytics
-- Dynamically covers from 2020-2021 through 2 years into the future
-- No manual updates needed

WITH date_spine AS (
    SELECT
        DATEADD(
            DAY,
            ROW_NUMBER() OVER (ORDER BY SEQ4()) - 1,
            '2020-11-01'::DATE
        ) AS date_day
    FROM TABLE(GENERATOR(ROWCOUNT => 3650))  -- ~10 years of coverage
),

date_attributes AS (
    SELECT
        date_day,
        -- Primary key
        TO_NUMBER(TO_CHAR(date_day, 'YYYYMMDD')) AS date_key,

        -- Date components
        DAYNAME(date_day) AS day_name,
        DAYOFWEEK(date_day) AS day_of_week,  -- 0=Sunday, 6=Saturday
        DAY(date_day) AS day_of_month,
        DAYOFYEAR(date_day) AS day_of_year,

        -- Week attributes
        WEEKOFYEAR(date_day) AS week_of_year,

        -- Month attributes
        MONTH(date_day) AS month_num,
        MONTHNAME(date_day) AS month_name,
        DATE_TRUNC('MONTH', date_day) AS month_start_date,

        -- Quarter attributes
        QUARTER(date_day) AS quarter_num,
        DATE_TRUNC('QUARTER', date_day) AS quarter_start_date,

        -- Year attributes
        YEAR(date_day) AS calendar_year,

        -- Ski season logic (Nov 1 - Apr 30)
        CASE
            WHEN MONTH(date_day) >= 11 THEN YEAR(date_day) || '-' || (YEAR(date_day) + 1)
            WHEN MONTH(date_day) <= 4 THEN (YEAR(date_day) - 1) || '-' || YEAR(date_day)
            ELSE NULL
        END AS ski_season,

        -- Season month (1-6 for Nov-Apr)
        CASE
            WHEN MONTH(date_day) = 11 THEN 1
            WHEN MONTH(date_day) = 12 THEN 2
            WHEN MONTH(date_day) = 1 THEN 3
            WHEN MONTH(date_day) = 2 THEN 4
            WHEN MONTH(date_day) = 3 THEN 5
            WHEN MONTH(date_day) = 4 THEN 6
            ELSE NULL
        END AS season_month,

        -- Week of season (1-26)
        CASE
            WHEN MONTH(date_day) >= 11 THEN
                FLOOR(DATEDIFF('DAY',
                    DATE_FROM_PARTS(YEAR(date_day), 11, 1),
                    date_day
                ) / 7) + 1
            WHEN MONTH(date_day) <= 4 THEN
                FLOOR(DATEDIFF('DAY',
                    DATE_FROM_PARTS(YEAR(date_day) - 1, 11, 1),
                    date_day
                ) / 7) + 1
            ELSE NULL
        END AS week_of_season,

        -- Boolean flags
        CASE WHEN DAYOFWEEK(date_day) IN (0, 6) THEN TRUE ELSE FALSE END AS is_weekend,
        CASE WHEN DAYOFWEEK(date_day) = 0 THEN TRUE ELSE FALSE END AS is_sunday,
        CASE WHEN DAYOFWEEK(date_day) = 6 THEN TRUE ELSE FALSE END AS is_saturday,

        -- Holiday flags (US holidays that affect ski traffic)
        CASE
            WHEN (MONTH(date_day) = 12 AND DAY(date_day) BETWEEN 20 AND 31) THEN TRUE  -- Christmas/New Year
            WHEN (MONTH(date_day) = 1 AND DAY(date_day) BETWEEN 1 AND 5) THEN TRUE    -- New Year week
            WHEN (MONTH(date_day) = 1 AND DAYOFWEEK(date_day) = 1 AND DAY(date_day) BETWEEN 15 AND 21) THEN TRUE  -- MLK Day
            WHEN (MONTH(date_day) = 2 AND DAYOFWEEK(date_day) = 1 AND DAY(date_day) BETWEEN 15 AND 21) THEN TRUE  -- Presidents Day
            WHEN (MONTH(date_day) = 3 AND DAY(date_day) BETWEEN 10 AND 24) THEN TRUE  -- Spring Break
            ELSE FALSE
        END AS is_holiday,

        -- Specific holiday names
        CASE
            WHEN (MONTH(date_day) = 12 AND DAY(date_day) = 25) THEN 'Christmas'
            WHEN (MONTH(date_day) = 1 AND DAY(date_day) = 1) THEN 'New Years Day'
            WHEN (MONTH(date_day) = 7 AND DAY(date_day) = 4) THEN 'Independence Day'
            WHEN (MONTH(date_day) = 11 AND DAYOFWEEK(date_day) = 4 AND DAY(date_day) BETWEEN 22 AND 28) THEN 'Thanksgiving'
            ELSE NULL
        END AS holiday_name,

        -- Snow condition categories (simplified - in reality would come from weather data)
        CASE
            WHEN MONTH(date_day) IN (1, 2) THEN 'Excellent'  -- Peak season
            WHEN MONTH(date_day) IN (12, 3) THEN 'Good'
            WHEN MONTH(date_day) IN (11, 4) THEN 'Fair'
            ELSE 'Closed'
        END AS snow_condition,

        -- Operating status
        CASE
            WHEN MONTH(date_day) BETWEEN 5 AND 10 THEN FALSE  -- Closed in summer
            ELSE TRUE
        END AS is_operating

    FROM date_spine
    WHERE date_day <= DATEADD(YEAR, 2, CURRENT_DATE())  -- Always 2 years ahead, no manual updates
)

SELECT
    date_key,
    date_day AS full_date,
    day_name,
    day_of_week,
    day_of_month,
    day_of_year,
    week_of_year,
    month_num,
    month_name,
    month_start_date,
    quarter_num,
    quarter_start_date,
    calendar_year,
    ski_season,
    season_month,
    week_of_season,
    is_weekend,
    is_sunday,
    is_saturday,
    is_holiday,
    holiday_name,
    snow_condition,
    is_operating,
    CURRENT_TIMESTAMP() AS created_at
FROM date_attributes
WHERE ski_season IS NOT NULL  -- Only include ski season dates
ORDER BY date_key
