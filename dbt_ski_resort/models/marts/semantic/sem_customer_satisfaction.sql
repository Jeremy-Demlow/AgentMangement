{{ config(materialized='semantic_view') }}

-- Customer Satisfaction semantic view (simplified)

TABLES (
    FACT_FEEDBACK AS {{ ref('fact_feedback') }}
      PRIMARY KEY (FEEDBACK_ID)
      WITH SYNONYMS ('customer_feedback', 'satisfaction', 'nps')
      COMMENT = 'Customer feedback and satisfaction scores'
)

FACTS (
    FACT_FEEDBACK.RATING AS RATING
      COMMENT = 'Customer satisfaction rating',
    FACT_FEEDBACK.SENTIMENT_SCORE AS SENTIMENT_SCORE
      COMMENT = 'Sentiment score',
    FACT_FEEDBACK.NPS_SCORE AS NPS_SCORE
      COMMENT = 'Net Promoter Score (0-10)',
    FACT_FEEDBACK.LIKELIHOOD_TO_RETURN AS LIKELIHOOD_TO_RETURN
      COMMENT = 'Likelihood to return rating',
    FACT_FEEDBACK.LIKELIHOOD_TO_RECOMMEND AS LIKELIHOOD_TO_RECOMMEND
      COMMENT = 'Likelihood to recommend rating',
    FACT_FEEDBACK.RESPONSE_TIME_DAYS AS RESPONSE_TIME_DAYS
      COMMENT = 'Days to respond to feedback'
)

DIMENSIONS (
    FACT_FEEDBACK.FEEDBACK_DATE AS FEEDBACK_DATE
      COMMENT = 'Date feedback was submitted',
    FACT_FEEDBACK.CATEGORY AS CATEGORY
      WITH SYNONYMS ('feedback_category')
      COMMENT = 'Feedback category',
    FACT_FEEDBACK.SENTIMENT AS SENTIMENT
      COMMENT = 'Sentiment classification',
    FACT_FEEDBACK.FEEDBACK_TYPE AS FEEDBACK_TYPE
      COMMENT = 'Type of feedback',
    FACT_FEEDBACK.RESOLVED AS RESOLVED
      COMMENT = 'Whether resolved',
    FACT_FEEDBACK.CUSTOMER_SEGMENT AS CUSTOMER_SEGMENT
      COMMENT = 'Customer segment'
)

METRICS (
    FACT_FEEDBACK.TOTAL_FEEDBACK AS COUNT(FACT_FEEDBACK.FEEDBACK_ID)
      COMMENT = 'Total feedback submissions',
    FACT_FEEDBACK.AVERAGE_RATING AS AVG(FACT_FEEDBACK.RATING)
      COMMENT = 'Average satisfaction rating',
    FACT_FEEDBACK.AVERAGE_NPS AS AVG(FACT_FEEDBACK.NPS_SCORE)
      COMMENT = 'Average Net Promoter Score',
    FACT_FEEDBACK.POSITIVE_FEEDBACK_COUNT AS COUNT(CASE WHEN FACT_FEEDBACK.SENTIMENT = 'Positive' THEN 1 END)
      COMMENT = 'Count of positive feedback',
    FACT_FEEDBACK.NEGATIVE_FEEDBACK_COUNT AS COUNT(CASE WHEN FACT_FEEDBACK.SENTIMENT = 'Negative' THEN 1 END)
      COMMENT = 'Count of negative feedback'
)

COMMENT = 'Customer satisfaction and feedback analysis'

WITH EXTENSION (CA = $$
{
  "module_custom_instructions": {
    "sql_generation": "Use FACT_FEEDBACK for all feedback and satisfaction queries. Filter by SENTIMENT for positive/negative analysis. Use NPS_SCORE for net promoter calculations. Guard division with DIV0()."
  },
  "verified_queries": [
    {
      "name": "feedback_by_category",
      "question": "What is the total feedback count and average rating by feedback category?",
      "sql": "WITH __fact_feedback AS (\n  SELECT\n    category,\n    feedback_id,\n    rating\n  FROM AM_SKI_RESORT.MARTS.FACT_FEEDBACK\n) SELECT\n  category,\n  COUNT(feedback_id) AS total_feedback,\n  AVG(rating) AS average_rating\nFROM __fact_feedback GROUP BY\n  category\nORDER BY\n  total_feedback DESC NULLS LAST",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": true
    },
    {
      "name": "nps_by_segment",
      "question": "What is the average NPS score and positive feedback count by customer segment?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n  AM_SKI_RESORT.SEMANTIC.SEM_CUSTOMER_SATISFACTION\n  DIMENSIONS customer_segment\n  METRICS average_nps, positive_feedback_count\n)",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": true
    },
    {
      "name": "monthly_feedback_trend",
      "question": "What is the monthly total feedback count and average rating by month?",
      "sql": "WITH __fact_feedback AS (\n  SELECT\n    feedback_date,\n    feedback_id,\n    rating\n  FROM AM_SKI_RESORT.MARTS.FACT_FEEDBACK\n) SELECT\n  DATE_TRUNC('MONTH', feedback_date) AS month,\n  COUNT(feedback_id) AS total_feedback,\n  AVG(rating) AS average_rating\nFROM __fact_feedback GROUP BY\n  DATE_TRUNC('MONTH', feedback_date)\nORDER BY\n  month DESC NULLS LAST",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": false
    },
    {
      "name": "unresolved_negative_by_type",
      "question": "What is the negative feedback count and total feedback by feedback type for unresolved feedback only?",
      "sql": "WITH __fact_feedback AS (\n  SELECT\n    feedback_type,\n    resolved,\n    sentiment,\n    feedback_id\n  FROM AM_SKI_RESORT.MARTS.FACT_FEEDBACK\n) SELECT\n  feedback_type,\n  COUNT(CASE WHEN sentiment = 'Negative' THEN 1 END) AS negative_feedback_count,\n  COUNT(feedback_id) AS total_feedback\nFROM __fact_feedback WHERE\n  resolved = FALSE\nGROUP BY\n  feedback_type\nORDER BY\n  total_feedback DESC NULLS LAST",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": false
    },
    {
      "name": "rating_nps_by_sentiment_category",
      "question": "What is the average rating and average NPS by sentiment and category?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n    AM_SKI_RESORT.SEMANTIC.SEM_CUSTOMER_SATISFACTION\n    DIMENSIONS sentiment, category\n    METRICS average_rating, average_nps\n)",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": false
    }
  ]
}
$$)
