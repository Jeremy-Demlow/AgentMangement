{{ config(materialized='semantic_view') }}

-- Pass holder analytics semantic view
-- Covers acquisition, utilization, and ROI metrics for pass programs

TABLES (
    DIM_CUSTOMER AS {{ ref('dim_customer') }}
      PRIMARY KEY (CUSTOMER_KEY)
      WITH SYNONYMS ('passholders', 'customers')
      COMMENT = 'Customer dimension with pass attributes and personas',

    DIM_DATE AS {{ ref('dim_date') }}
      PRIMARY KEY (DATE_KEY)
      WITH SYNONYMS ('calendar')
      COMMENT = 'Calendar dimension used for pass activity',

    DIM_TICKET_TYPE AS {{ ref('dim_ticket_type') }}
      PRIMARY KEY (TICKET_TYPE_KEY)
      WITH SYNONYMS ('pass_catalog')
      COMMENT = 'Ticket type catalog including season pass products',

    FACT_PASS_USAGE AS {{ ref('fact_pass_usage') }}
      PRIMARY KEY (USAGE_KEY)
      WITH SYNONYMS ('pass_usage')
      COMMENT = 'Daily pass usage fact table with lift rides and time on mountain',

    FACT_TICKET_SALES AS {{ ref('fact_ticket_sales') }}
      PRIMARY KEY (SALE_KEY)
      WITH SYNONYMS ('pass_sales', 'ticket_sales')
      COMMENT = 'Ticket sales fact including pass purchases and revenue'
)

RELATIONSHIPS (
    PASS_USAGE_TO_DATE AS
      FACT_PASS_USAGE (DATE_KEY) REFERENCES DIM_DATE,
    PASS_USAGE_TO_CUSTOMER AS
      FACT_PASS_USAGE (CUSTOMER_KEY) REFERENCES DIM_CUSTOMER,
    PASS_SALES_TO_DATE AS
      FACT_TICKET_SALES (PURCHASE_DATE_KEY) REFERENCES DIM_DATE,
    PASS_SALES_TO_CUSTOMER AS
      FACT_TICKET_SALES (CUSTOMER_KEY) REFERENCES DIM_CUSTOMER,
    PASS_SALES_TO_TICKET_TYPE AS
      FACT_TICKET_SALES (TICKET_TYPE_KEY) REFERENCES DIM_TICKET_TYPE
)

FACTS (
    FACT_PASS_USAGE.TOTAL_LIFT_RIDES AS TOTAL_LIFT_RIDES
      COMMENT = 'Lift rides taken during the pass holder visit',
    FACT_PASS_USAGE.HOURS_ON_MOUNTAIN AS HOURS_ON_MOUNTAIN
      COMMENT = 'Time on mountain for the pass visit (hours)',
    FACT_TICKET_SALES.PURCHASE_AMOUNT AS PURCHASE_AMOUNT
      COMMENT = 'Revenue collected from pass product sales',
    FACT_TICKET_SALES.IS_ADVANCE_PURCHASE AS IS_ADVANCE_PURCHASE
      COMMENT = 'Indicates pass purchase was made prior to validity start',
    FACT_TICKET_SALES.PURCHASE_CHANNEL AS PURCHASE_CHANNEL
      COMMENT = 'Channel used to acquire or renew the pass'
)

DIMENSIONS (
    DIM_DATE.FULL_DATE AS FULL_DATE
      WITH SYNONYMS ('activity_date')
      COMMENT = 'Date of pass usage or sale',
    DIM_DATE.SKI_SEASON AS SKI_SEASON
      COMMENT = 'Ski season identifier',
    DIM_CUSTOMER.PASS_TYPE AS PASS_TYPE
      COMMENT = 'Pass product currently held',
    DIM_CUSTOMER.CUSTOMER_SEGMENT AS CUSTOMER_SEGMENT
      COMMENT = 'Customer persona classification',
    DIM_CUSTOMER.STATE AS STATE
      COMMENT = 'Customer home state',
    DIM_CUSTOMER.IS_PASS_HOLDER AS IS_PASS_HOLDER
      COMMENT = 'Indicates pass ownership',
    DIM_TICKET_TYPE.TICKET_CATEGORY AS TICKET_CATEGORY
      COMMENT = 'Pass product category (e.g., Season Pass, Flex Pass)',
    DIM_DATE.DATE_KEY AS DATE_KEY
      COMMENT = 'Date surrogate key',
    DIM_CUSTOMER.CUSTOMER_KEY AS CUSTOMER_KEY
      COMMENT = 'Customer surrogate key',
    DIM_TICKET_TYPE.TICKET_TYPE_KEY AS TICKET_TYPE_KEY
      COMMENT = 'Ticket type surrogate key',
    FACT_PASS_USAGE.DATE_KEY AS DATE_KEY
      COMMENT = 'Pass usage FK to date',
    FACT_PASS_USAGE.CUSTOMER_KEY AS CUSTOMER_KEY
      COMMENT = 'Pass usage FK to customer',
    FACT_TICKET_SALES.PURCHASE_DATE_KEY AS PURCHASE_DATE_KEY
      COMMENT = 'Ticket sales FK to date',
    FACT_TICKET_SALES.CUSTOMER_KEY AS CUSTOMER_KEY
      COMMENT = 'Ticket sales FK to customer',
    FACT_TICKET_SALES.TICKET_TYPE_KEY AS TICKET_TYPE_KEY
      COMMENT = 'Ticket sales FK to ticket type',
    FACT_PASS_USAGE.USAGE_KEY AS USAGE_KEY
      COMMENT = 'Pass usage surrogate key',
    FACT_TICKET_SALES.SALE_KEY AS SALE_KEY
      COMMENT = 'Ticket sale surrogate key'
)

METRICS (
    FACT_PASS_USAGE.PASS_HOLDER_VISITS AS COUNT(CASE WHEN DIM_CUSTOMER.IS_PASS_HOLDER THEN FACT_PASS_USAGE.USAGE_KEY END)
      COMMENT = 'Number of pass holder visit days',
    FACT_PASS_USAGE.ACTIVE_PASS_HOLDERS AS COUNT(DISTINCT CASE WHEN DIM_CUSTOMER.IS_PASS_HOLDER THEN FACT_PASS_USAGE.CUSTOMER_KEY END)
      COMMENT = 'Distinct pass holders with recent activity',
    FACT_PASS_USAGE.PASS_USAGE_PER_HOLDER AS DIV0(
        COUNT(CASE WHEN DIM_CUSTOMER.IS_PASS_HOLDER THEN FACT_PASS_USAGE.USAGE_KEY END),
        NULLIF(COUNT(DISTINCT CASE WHEN DIM_CUSTOMER.IS_PASS_HOLDER THEN FACT_PASS_USAGE.CUSTOMER_KEY END), 0)
    )
      COMMENT = 'Average visits per active pass holder',
    FACT_PASS_USAGE.PASS_HOURS_TOTAL AS SUM(CASE WHEN DIM_CUSTOMER.IS_PASS_HOLDER THEN FACT_PASS_USAGE.HOURS_ON_MOUNTAIN END)
      COMMENT = 'Total hours on mountain for pass holders',
    FACT_PASS_USAGE.AVERAGE_PASS_SESSION_HOURS AS DIV0(
        SUM(CASE WHEN DIM_CUSTOMER.IS_PASS_HOLDER THEN FACT_PASS_USAGE.HOURS_ON_MOUNTAIN END),
        NULLIF(COUNT(CASE WHEN DIM_CUSTOMER.IS_PASS_HOLDER THEN FACT_PASS_USAGE.USAGE_KEY END), 0)
    )
      COMMENT = 'Average hours on mountain per pass visit',
    FACT_PASS_USAGE.PASS_LIFT_RIDES_TOTAL AS SUM(CASE WHEN DIM_CUSTOMER.IS_PASS_HOLDER THEN FACT_PASS_USAGE.TOTAL_LIFT_RIDES END)
      COMMENT = 'Total lift rides taken by pass holders',
    FACT_TICKET_SALES.PASS_REVENUE_TOTAL AS SUM(CASE WHEN DIM_TICKET_TYPE.TICKET_CATEGORY ILIKE '%Pass%' THEN FACT_TICKET_SALES.PURCHASE_AMOUNT END)
      COMMENT = 'Revenue from pass product sales',
    FACT_TICKET_SALES.AVERAGE_PASS_PRICE AS DIV0(
        SUM(CASE WHEN DIM_TICKET_TYPE.TICKET_CATEGORY ILIKE '%Pass%' THEN FACT_TICKET_SALES.PURCHASE_AMOUNT END),
        NULLIF(COUNT(CASE WHEN DIM_TICKET_TYPE.TICKET_CATEGORY ILIKE '%Pass%' THEN FACT_TICKET_SALES.SALE_KEY END), 0)
    )
      COMMENT = 'Average selling price for pass products',
    FACT_TICKET_SALES.ADVANCE_PASS_SHARE_PCT AS DIV0(
        COUNT(CASE WHEN DIM_TICKET_TYPE.TICKET_CATEGORY ILIKE '%Pass%' AND FACT_TICKET_SALES.IS_ADVANCE_PURCHASE THEN 1 END),
        NULLIF(COUNT(CASE WHEN DIM_TICKET_TYPE.TICKET_CATEGORY ILIKE '%Pass%' THEN FACT_TICKET_SALES.SALE_KEY END), 0)
    ) * 100
      COMMENT = 'Percent of pass sales booked in advance'
)

COMMENT = 'Pass holder analytics semantic view for utilization, retention, and revenue insights'

WITH EXTENSION (CA = $$
{
  "module_custom_instructions": {
    "question_categorization": "Route lift wait time or terrain utilization topics to SKI_RESORT_DB.SEMANTIC.SEM_OPERATIONS. Route broad revenue mix, pricing, or channel analyses that include non-pass sales to SKI_RESORT_DB.SEMANTIC.SEM_REVENUE. Route general customer segmentation or visitation cadence questions to SKI_RESORT_DB.SEMANTIC.SEM_CUSTOMER_BEHAVIOR. If a user references a pass without identifying PASS_TYPE or TICKET_CATEGORY, ask for clarification before proceeding. Confirm whether the user needs active pass holders, historical pass owners, or all customers when the population is ambiguous.",
    "sql_generation": "Anchor time filters with DIM_DATE.SKI_SEASON or DIM_DATE.FULL_DATE; use DATE_TRUNC for season-to-date comparisons. Aggregate utilization metrics exclusively from FACT_PASS_USAGE and revenue metrics from FACT_TICKET_SALES; wrap ratios with DIV0(...). Filter pass-specific cohorts with DIM_CUSTOMER.IS_PASS_HOLDER = TRUE and refine by PASS_TYPE when requested. When analyzing sales channels, rely on FACT_TICKET_SALES.PURCHASE_CHANNEL and group by DIM_TICKET_TYPE.TICKET_CATEGORY as needed. Exclude day-ticket categories when the question targets pass-only behavior to prevent double counting."
  },
  "verified_queries": [
    {
      "name": "visits_holders_by_pass_type",
      "question": "What are the pass holder visits and active pass holders by pass type?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n  {{ target.database }}.SEMANTIC.SEM_PASSHOLDER_ANALYTICS\n  METRICS pass_holder_visits, active_pass_holders\n  DIMENSIONS dim_customer.pass_type\n)",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": true
    },
    {
      "name": "revenue_price_by_season",
      "question": "What is the pass revenue total and average pass price by ski season?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n    {{ target.database }}.SEMANTIC.SEM_PASSHOLDER_ANALYTICS\n    DIMENSIONS dim_date.ski_season\n    METRICS pass_revenue_total, average_pass_price\n) ORDER BY ski_season DESC NULLS LAST",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": true
    },
    {
      "name": "usage_session_by_segment",
      "question": "What is the pass usage per holder and average pass session hours by customer segment?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n    {{ target.database }}.SEMANTIC.SEM_PASSHOLDER_ANALYTICS\n    METRICS pass_usage_per_holder, average_pass_session_hours\n    DIMENSIONS dim_customer.customer_segment\n    WHERE dim_customer.is_pass_holder = TRUE\n)",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": false
    },
    {
      "name": "advance_share_revenue_by_category",
      "question": "What is the advance pass share percentage and pass revenue total by ticket category?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n  {{ target.database }}.SEMANTIC.SEM_PASSHOLDER_ANALYTICS\n  DIMENSIONS ticket_category\n  METRICS advance_pass_share_pct, pass_revenue_total\n)",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": false
    },
    {
      "name": "active_holders_rides_by_state",
      "question": "What are the active pass holders and pass lift rides total by state?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n  {{ target.database }}.SEMANTIC.SEM_PASSHOLDER_ANALYTICS\n  METRICS active_pass_holders, pass_lift_rides_total\n  DIMENSIONS dim_customer.state\n)",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": false
    }
  ]
}
$$)
