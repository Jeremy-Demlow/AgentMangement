{{ config(materialized='semantic_view') }}

-- Lessons Analytics semantic view — year-round instruction programs

TABLES (
    FACT_LESSONS AS {{ ref('fact_lessons') }}
      PRIMARY KEY (LESSON_ID)
      WITH SYNONYMS ('lessons', 'ski_school', 'instruction')
      COMMENT = 'Lesson bookings: ski, snowboard, mountain bike, hiking, kids camp',

    DIM_DATE AS {{ ref('dim_date') }}
      PRIMARY KEY (DATE_KEY)
      WITH SYNONYMS ('calendar')
      COMMENT = 'Calendar dimension with season and summer awareness'
)

RELATIONSHIPS (
    LESSONS_TO_DATE AS
      FACT_LESSONS (LESSON_DATE_KEY) REFERENCES DIM_DATE
)

FACTS (
    FACT_LESSONS.LESSON_AMOUNT AS LESSON_AMOUNT
      COMMENT = 'Base lesson price',
    FACT_LESSONS.TOTAL_LESSON_REVENUE AS TOTAL_LESSON_REVENUE
      COMMENT = 'Total lesson revenue',
    FACT_LESSONS.DURATION_HOURS AS DURATION_HOURS
      COMMENT = 'Lesson duration',
    FACT_LESSONS.GROUP_SIZE AS GROUP_SIZE
      COMMENT = 'Group size',
    FACT_LESSONS.STUDENT_RATING AS STUDENT_RATING
      COMMENT = 'Student rating'
)

DIMENSIONS (
    FACT_LESSONS.LESSON_DATE AS LESSON_DATE
      COMMENT = 'Date of lesson',
    DIM_DATE.SEASON_TYPE AS SEASON_TYPE
      WITH SYNONYMS ('operating_season')
      COMMENT = 'Season type: winter (Nov-Apr) or summer (May-Oct)',
    DIM_DATE.SKI_SEASON AS SKI_SEASON
      COMMENT = 'Ski season identifier (e.g. 2024-2025)',
    DIM_DATE.FULL_DATE AS FULL_DATE
      WITH SYNONYMS ('date')
      COMMENT = 'Calendar date',
    DIM_DATE.IS_WEEKEND AS IS_WEEKEND
      COMMENT = 'Weekend flag',
    DIM_DATE.IS_HOLIDAY AS IS_HOLIDAY
      COMMENT = 'Holiday flag',
    FACT_LESSONS.LESSON_TYPE AS LESSON_TYPE
      WITH SYNONYMS ('type')
      COMMENT = 'Lesson type',
    FACT_LESSONS.SPORT_TYPE AS SPORT_TYPE
      COMMENT = 'Sport',
    FACT_LESSONS.SKILL_LEVEL AS SKILL_LEVEL
      COMMENT = 'Skill level',
    FACT_LESSONS.INSTRUCTOR_NAME AS INSTRUCTOR_NAME
      COMMENT = 'Instructor',
    FACT_LESSONS.BOOKING_CHANNEL AS BOOKING_CHANNEL
      COMMENT = 'Booking channel',
    FACT_LESSONS.COMPLETED AS COMPLETED
      COMMENT = 'Completed',
    FACT_LESSONS.CUSTOMER_SEGMENT AS CUSTOMER_SEGMENT
      COMMENT = 'Customer segment'
)

METRICS (
    FACT_LESSONS.TOTAL_LESSONS AS COUNT(FACT_LESSONS.LESSON_ID)
      COMMENT = 'Total lessons',
    FACT_LESSONS.TOTAL_REVENUE AS SUM(FACT_LESSONS.TOTAL_LESSON_REVENUE)
      COMMENT = 'Total revenue',
    FACT_LESSONS.AVG_STUDENT_RATING AS AVG(FACT_LESSONS.STUDENT_RATING)
      COMMENT = 'Avg student rating',
    FACT_LESSONS.PRIVATE_LESSONS AS COUNT(CASE WHEN FACT_LESSONS.LESSON_TYPE = 'Private' THEN 1 END)
      COMMENT = 'Private lessons',
    FACT_LESSONS.GROUP_LESSONS AS COUNT(CASE WHEN FACT_LESSONS.LESSON_TYPE = 'Group' THEN 1 END)
      COMMENT = 'Group lessons'
)

COMMENT = 'Ski school analytics'

WITH EXTENSION (CA = $$
{
  "module_custom_instructions": {
    "question_categorization": "This view covers all resort instruction programs year-round. Winter lessons include ski and snowboard instruction (beginner_group, intermediate_group, advanced_group, private, kids_camp). Summer lessons include mountain bike instruction (mountain_bike_beginner, mountain_bike_intermediate, mountain_bike_advanced), guided hikes (guided_hike), and kids adventure camps (kids_adventure_camp). Use SPORT_TYPE to distinguish winter (ski, snowboard) from summer (mountain_bike, hiking, adventure) activities. Route revenue questions to SEM_REVENUE if they are about ticket/pass sales rather than lesson bookings.",
    "sql_generation": "Use FACT_LESSONS for all lesson queries. Filter by LESSON_TYPE for private vs group. Use STUDENT_RATING for instructor performance. Guard division with DIV0(). Use DIM_DATE.SEASON_TYPE to filter winter vs summer lessons. The resort offers year-round lessons: winter includes ski/snowboard (beginner_group, intermediate_group, advanced_group, private, kids_camp); summer includes mountain biking and guided hikes (mountain_bike_beginner, mountain_bike_intermediate, mountain_bike_advanced, guided_hike, kids_adventure_camp). Use SPORT_TYPE to distinguish ski/snowboard/mountain_bike/hiking/adventure. When asking about recent lessons, include ALL data unless a season is specified."
  },
  "verified_queries": [
    {
      "name": "lessons_by_type_sport",
      "question": "What is the total lessons count and total revenue by lesson type and sport type?",
      "sql": "WITH __fact_lessons AS (\n  SELECT\n    lesson_type,\n    sport_type,\n    lesson_id,\n    total_lesson_revenue\n  FROM {{ target.database }}.MARTS.FACT_LESSONS\n) SELECT\n  lesson_type,\n  sport_type,\n  COUNT(lesson_id) AS total_lessons,\n  SUM(total_lesson_revenue) AS total_revenue\nFROM __fact_lessons GROUP BY\n  lesson_type,\n  sport_type\nORDER BY\n  lesson_type,\n  sport_type",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": true
    },
    {
      "name": "rating_by_instructor",
      "question": "What is the average student rating by instructor name, ordered by highest rating?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n    {{ target.database }}.SEMANTIC.SEM_LESSONS_ANALYTICS\n    METRICS avg_student_rating\n    DIMENSIONS instructor_name\n) ORDER BY avg_student_rating DESC NULLS LAST",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": true
    },
    {
      "name": "monthly_revenue_trend",
      "question": "What is the monthly total revenue for lessons by month?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n    {{ target.database }}.SEMANTIC.SEM_LESSONS_ANALYTICS\n    DIMENSIONS DATE_TRUNC('month', fact_lessons.lesson_date) AS lesson_month\n    METRICS total_revenue\n) ORDER BY lesson_month DESC NULLS LAST",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": false
    },
    {
      "name": "lessons_by_channel_segment",
      "question": "What is the total lessons and total revenue by booking channel and customer segment?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n    {{ target.database }}.SEMANTIC.SEM_LESSONS_ANALYTICS\n    DIMENSIONS booking_channel, customer_segment\n    METRICS total_lessons, total_revenue\n)",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": false
    },
    {
      "name": "private_group_by_skill",
      "question": "What are the private lessons count and group lessons count by skill level?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n    {{ target.database }}.SEMANTIC.SEM_LESSONS_ANALYTICS\n    DIMENSIONS skill_level\n    METRICS private_lessons, group_lessons\n)",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": false
    },
    {
      "name": "summer_lessons_by_sport",
      "question": "What is the total lesson count and revenue for summer activities by sport type?",
      "sql": "WITH __fact_lessons AS (\n  SELECT sport_type, lesson_id, total_lesson_revenue\n  FROM {{ target.database }}.MARTS.FACT_LESSONS\n  WHERE sport_type IN ('mountain_bike', 'hiking', 'adventure')\n) SELECT sport_type, COUNT(lesson_id) AS total_lessons, SUM(total_lesson_revenue) AS total_revenue\nFROM __fact_lessons\nGROUP BY sport_type\nORDER BY total_revenue DESC NULLS LAST",
      "verified_by": "Cortex Analyst",
      "verified_at": 1750032000,
      "use_as_onboarding_question": true
    }
  ]
}
$$)
