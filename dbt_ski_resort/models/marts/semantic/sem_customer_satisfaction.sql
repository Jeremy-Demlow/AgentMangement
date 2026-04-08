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
