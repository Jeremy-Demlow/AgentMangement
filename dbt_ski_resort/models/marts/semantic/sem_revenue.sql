{{ config(materialized='semantic_view') }}

-- Unified revenue semantic view
-- Combines tickets, rentals, and food & beverage performance

TABLES (
    DIM_DATE AS {{ ref('dim_date') }}
      PRIMARY KEY (DATE_KEY)
      WITH SYNONYMS ('calendar')
      COMMENT = 'Calendar dimension with ski season awareness',

    DIM_CUSTOMER AS {{ ref('dim_customer') }}
      PRIMARY KEY (CUSTOMER_KEY)
      WITH SYNONYMS ('customers')
      COMMENT = 'Customer dimension with persona and geography',

    DIM_LOCATION AS {{ ref('dim_location') }}
      PRIMARY KEY (LOCATION_KEY)
      WITH SYNONYMS ('venues', 'points_of_sale')
      COMMENT = 'On-mountain venues for sales and services',

    DIM_TICKET_TYPE AS {{ ref('dim_ticket_type') }}
      PRIMARY KEY (TICKET_TYPE_KEY)
      WITH SYNONYMS ('ticket_products')
      COMMENT = 'Ticket and pass catalog with pricing',

    DIM_PRODUCT AS {{ ref('dim_product') }}
      PRIMARY KEY (PRODUCT_KEY)
      WITH SYNONYMS ('sku')
      COMMENT = 'Rental and food & beverage products',

    FACT_TICKET_SALES AS {{ ref('fact_ticket_sales') }}
      PRIMARY KEY (SALE_KEY)
      WITH SYNONYMS ('ticket_sales', 'pass_sales')
      COMMENT = 'Ticket and pass sales transactions including price and channel',

    FACT_RENTALS AS {{ ref('fact_rentals') }}
      PRIMARY KEY (RENTAL_KEY)
      WITH SYNONYMS ('rental_transactions')
      COMMENT = 'Rental transactions with duration and revenue',

    FACT_FOOD_BEVERAGE AS {{ ref('fact_food_beverage') }}
      PRIMARY KEY (TRANSACTION_KEY)
      WITH SYNONYMS ('fnb_sales')
      COMMENT = 'Food and beverage transactions with quantity and spend'
)

RELATIONSHIPS (
    TICKET_SALES_TO_DATE AS
      FACT_TICKET_SALES (PURCHASE_DATE_KEY) REFERENCES DIM_DATE,
    TICKET_SALES_TO_CUSTOMER AS
      FACT_TICKET_SALES (CUSTOMER_KEY) REFERENCES DIM_CUSTOMER,
    TICKET_SALES_TO_LOCATION AS
      FACT_TICKET_SALES (LOCATION_KEY) REFERENCES DIM_LOCATION,
    TICKET_SALES_TO_TICKET_TYPE AS
      FACT_TICKET_SALES (TICKET_TYPE_KEY) REFERENCES DIM_TICKET_TYPE,

    RENTALS_TO_DATE AS
      FACT_RENTALS (RENTAL_DATE_KEY) REFERENCES DIM_DATE,
    RENTALS_TO_CUSTOMER AS
      FACT_RENTALS (CUSTOMER_KEY) REFERENCES DIM_CUSTOMER,
    RENTALS_TO_LOCATION AS
      FACT_RENTALS (LOCATION_KEY) REFERENCES DIM_LOCATION,
    RENTALS_TO_PRODUCT AS
      FACT_RENTALS (PRODUCT_KEY) REFERENCES DIM_PRODUCT,

    FNB_TO_DATE AS
      FACT_FOOD_BEVERAGE (TRANSACTION_DATE_KEY) REFERENCES DIM_DATE,
    FNB_TO_CUSTOMER AS
      FACT_FOOD_BEVERAGE (CUSTOMER_KEY) REFERENCES DIM_CUSTOMER,
    FNB_TO_LOCATION AS
      FACT_FOOD_BEVERAGE (LOCATION_KEY) REFERENCES DIM_LOCATION,
    FNB_TO_PRODUCT AS
      FACT_FOOD_BEVERAGE (PRODUCT_KEY) REFERENCES DIM_PRODUCT
)

FACTS (
    FACT_TICKET_SALES.PURCHASE_AMOUNT AS PURCHASE_AMOUNT
      COMMENT = 'Net ticket or pass revenue collected',
    FACT_TICKET_SALES.IS_ADVANCE_PURCHASE AS IS_ADVANCE_PURCHASE
      COMMENT = 'Indicates ticket was purchased before the ski day',
    FACT_TICKET_SALES.PURCHASE_CHANNEL AS PURCHASE_CHANNEL
      COMMENT = 'Ticket sales channel (online, window, kiosk)',
    FACT_RENTALS.RENTAL_AMOUNT AS RENTAL_AMOUNT
      COMMENT = 'Rental revenue collected',
    FACT_RENTALS.RENTAL_MARKUP AS RENTAL_MARKUP
      COMMENT = 'Rental price minus catalog list price',
    FACT_FOOD_BEVERAGE.TOTAL_AMOUNT AS TOTAL_AMOUNT
      COMMENT = 'Total food & beverage revenue',
    FACT_FOOD_BEVERAGE.UPSELL_AMOUNT AS UPSELL_AMOUNT
      COMMENT = 'Upsell dollars above list price'
)

DIMENSIONS (
    DIM_DATE.DATE_KEY AS DATE_KEY
      COMMENT = 'Date surrogate key',
    DIM_DATE.FULL_DATE AS FULL_DATE
      WITH SYNONYMS ('transaction_date')
      COMMENT = 'Transaction date',
    DIM_DATE.SKI_SEASON AS SKI_SEASON
      COMMENT = 'Ski season identifier',
    DIM_DATE.MONTH_NAME AS MONTH_NAME
      COMMENT = 'Calendar month name',
    DIM_CUSTOMER.CUSTOMER_KEY AS CUSTOMER_KEY
      COMMENT = 'Customer surrogate key',
    DIM_CUSTOMER.CUSTOMER_SEGMENT AS CUSTOMER_SEGMENT
      COMMENT = 'Customer persona classification',
    DIM_CUSTOMER.IS_PASS_HOLDER AS IS_PASS_HOLDER
      COMMENT = 'Pass holder indicator',
    DIM_LOCATION.LOCATION_KEY AS LOCATION_KEY
      COMMENT = 'Location surrogate key',
    DIM_LOCATION.LOCATION_NAME AS LOCATION_NAME
      COMMENT = 'Point-of-sale location name',
    DIM_LOCATION.LOCATION_TYPE AS LOCATION_TYPE
      COMMENT = 'Location category (ticket window, rental shop, dining)',
    DIM_TICKET_TYPE.TICKET_TYPE_KEY AS TICKET_TYPE_KEY
      COMMENT = 'Ticket type surrogate key',
    DIM_TICKET_TYPE.TICKET_CATEGORY AS TICKET_CATEGORY
      COMMENT = 'Ticket product category (Season Pass, Day Ticket, etc.)',
    DIM_PRODUCT.PRODUCT_KEY AS PRODUCT_KEY
      COMMENT = 'Product surrogate key',
    DIM_PRODUCT.PRODUCT_CATEGORY AS PRODUCT_CATEGORY
      COMMENT = 'Rental or F&B product category',
    DIM_PRODUCT.PRODUCT_TYPE AS PRODUCT_TYPE
      COMMENT = 'Specific product type (Demo Skis, Summit Restaurant, etc.)',
    FACT_TICKET_SALES.SALE_KEY AS SALE_KEY
      COMMENT = 'Ticket sale surrogate key',
    FACT_TICKET_SALES.CUSTOMER_KEY AS CUSTOMER_KEY
      COMMENT = 'Ticket sales FK to customer',
    FACT_TICKET_SALES.PURCHASE_DATE_KEY AS PURCHASE_DATE_KEY
      COMMENT = 'Ticket sales FK to date',
    FACT_TICKET_SALES.LOCATION_KEY AS LOCATION_KEY
      COMMENT = 'Ticket sales FK to location',
    FACT_TICKET_SALES.TICKET_TYPE_KEY AS TICKET_TYPE_KEY
      COMMENT = 'Ticket sales FK to ticket type',
    FACT_RENTALS.RENTAL_KEY AS RENTAL_KEY
      COMMENT = 'Rental transaction surrogate key',
    FACT_RENTALS.CUSTOMER_KEY AS CUSTOMER_KEY
      COMMENT = 'Rentals FK to customer',
    FACT_RENTALS.RENTAL_DATE_KEY AS RENTAL_DATE_KEY
      COMMENT = 'Rentals FK to date',
    FACT_RENTALS.LOCATION_KEY AS LOCATION_KEY
      COMMENT = 'Rentals FK to location',
    FACT_RENTALS.PRODUCT_KEY AS PRODUCT_KEY
      COMMENT = 'Rentals FK to product',
    FACT_FOOD_BEVERAGE.TRANSACTION_KEY AS TRANSACTION_KEY
      COMMENT = 'F&B transaction surrogate key',
    FACT_FOOD_BEVERAGE.CUSTOMER_KEY AS CUSTOMER_KEY
      COMMENT = 'F&B FK to customer',
    FACT_FOOD_BEVERAGE.TRANSACTION_DATE_KEY AS TRANSACTION_DATE_KEY
      COMMENT = 'F&B FK to date',
    FACT_FOOD_BEVERAGE.LOCATION_KEY AS LOCATION_KEY
      COMMENT = 'F&B FK to location',
    FACT_FOOD_BEVERAGE.PRODUCT_KEY AS PRODUCT_KEY
      COMMENT = 'F&B FK to product'
)

METRICS (
    FACT_TICKET_SALES.TICKET_REVENUE AS SUM(FACT_TICKET_SALES.PURCHASE_AMOUNT)
      COMMENT = 'Total ticket and pass revenue',
    FACT_TICKET_SALES.TICKETS_SOLD AS COUNT(FACT_TICKET_SALES.SALE_KEY)
      COMMENT = 'Number of ticket and pass transactions',
    FACT_TICKET_SALES.ADVANCE_SALES_SHARE_PCT AS DIV0(
        COUNT(CASE WHEN FACT_TICKET_SALES.IS_ADVANCE_PURCHASE THEN 1 END),
        NULLIF(COUNT(FACT_TICKET_SALES.SALE_KEY), 0)
    ) * 100
      COMMENT = 'Percent of ticket transactions purchased in advance',
    FACT_TICKET_SALES.ONLINE_CHANNEL_REVENUE AS SUM(CASE WHEN FACT_TICKET_SALES.PURCHASE_CHANNEL = 'online' THEN FACT_TICKET_SALES.PURCHASE_AMOUNT END)
      COMMENT = 'Ticket revenue booked through the online channel',
    FACT_TICKET_SALES.ONLINE_CHANNEL_SHARE_PCT AS DIV0(
        SUM(CASE WHEN FACT_TICKET_SALES.PURCHASE_CHANNEL = 'online' THEN FACT_TICKET_SALES.PURCHASE_AMOUNT END),
        NULLIF(SUM(FACT_TICKET_SALES.PURCHASE_AMOUNT), 0)
    ) * 100
      COMMENT = 'Online channel share of ticket revenue (%)',
    FACT_TICKET_SALES.AVERAGE_TICKET_PRICE AS DIV0(
        SUM(FACT_TICKET_SALES.PURCHASE_AMOUNT),
        NULLIF(COUNT(FACT_TICKET_SALES.SALE_KEY), 0)
    )
      COMMENT = 'Average ticket revenue per transaction',
    FACT_RENTALS.RENTAL_REVENUE AS SUM(FACT_RENTALS.RENTAL_AMOUNT)
      COMMENT = 'Total rental revenue',
    FACT_RENTALS.RENTAL_TRANSACTIONS AS COUNT(FACT_RENTALS.RENTAL_KEY)
      COMMENT = 'Number of rental transactions',
    FACT_RENTALS.RENTAL_MARKUP_DOLLARS AS SUM(FACT_RENTALS.RENTAL_MARKUP)
      COMMENT = 'Rental markup versus catalog price',
    FACT_FOOD_BEVERAGE.FNB_REVENUE AS SUM(FACT_FOOD_BEVERAGE.TOTAL_AMOUNT)
      COMMENT = 'Total food & beverage revenue',
    FACT_FOOD_BEVERAGE.FNB_TRANSACTIONS AS COUNT(FACT_FOOD_BEVERAGE.TRANSACTION_KEY)
      COMMENT = 'Number of food & beverage transactions',
    FACT_FOOD_BEVERAGE.FNB_UPSELL_REVENUE AS SUM(FACT_FOOD_BEVERAGE.UPSELL_AMOUNT)
      COMMENT = 'Upsell revenue above list price for F&B'
)

COMMENT = 'Revenue semantic view for analyzing ticket, rental, and F&B performance across channels'

WITH EXTENSION (CA = $$
{
  "module_custom_instructions": {
    "question_categorization": "Route lift operations, wait time, or capacity conversations to SKI_RESORT_DB.SEMANTIC.SEM_OPERATIONS. Route pass utilization, renewal, or loyalty questions to SKI_RESORT_DB.SEMANTIC.SEM_PASSHOLDER_ANALYTICS. Route persona-only behavioral questions to SKI_RESORT_DB.SEMANTIC.SEM_CUSTOMER_BEHAVIOR. When a request mentions ticket, ticket sales, or ticket category, use FACT_TICKET_SALES. When it mentions rental or equipment, use FACT_RENTALS. When it mentions food, beverage, F&B, or dining, use FACT_FOOD_BEVERAGE. Never ask for clarification about which revenue stream — infer from context or answer for all streams if ambiguous.",
    "sql_generation": "Aggregate ticket revenue from FACT_TICKET_SALES, rentals from FACT_RENTALS, and F&B from FACT_FOOD_BEVERAGE. When the question specifies a product family (tickets, rentals, or F&B), use only that fact table. When ambiguous, answer using all relevant fact tables without asking for clarification. Use DIM_DATE.FULL_DATE for calendar filters and DIM_DATE.SKI_SEASON for seasonal framing; leverage DATE_TRUNC for month or season aggregation. Join DIM_LOCATION, DIM_TICKET_TYPE, or DIM_PRODUCT to segment results. Guard division with DIV0(...) and include NULLS LAST when ordering by computed metrics."
  },
  "verified_queries": [
    {
      "name": "ticket_revenue_by_category",
      "question": "What is the total ticket sales revenue by ticket category?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n  {{ target.database }}.SEMANTIC.SEM_REVENUE\n  METRICS ticket_revenue\n  DIMENSIONS ticket_category\n) ORDER BY ticket_revenue DESC NULLS LAST",
      "verified_by": "Cortex Analyst",
      "verified_at": 1745200000,
      "use_as_onboarding_question": true
    },
    {
      "name": "rental_revenue_by_product",
      "question": "What is the total equipment rental revenue by product category?",
      "sql": "WITH __fact_rentals AS (\n  SELECT product_key, rental_amount\n  FROM {{ target.database }}.MARTS.FACT_RENTALS\n), __dim_product AS (\n  SELECT product_category, product_key\n  FROM {{ target.database }}.MARTS.DIM_PRODUCT\n) SELECT dp.product_category, SUM(fr.rental_amount) AS total_rental_revenue FROM __fact_rentals AS fr LEFT OUTER JOIN __dim_product AS dp ON fr.product_key = dp.product_key GROUP BY dp.product_category ORDER BY total_rental_revenue DESC NULLS LAST",
      "verified_by": "Cortex Analyst",
      "verified_at": 1745200000,
      "use_as_onboarding_question": true
    },
    {
      "name": "fnb_revenue_by_location",
      "question": "What is the total food and beverage revenue by location name?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n  {{ target.database }}.SEMANTIC.SEM_REVENUE\n  METRICS fnb_revenue\n  DIMENSIONS location_name\n) ORDER BY fnb_revenue DESC NULLS LAST",
      "verified_by": "Cortex Analyst",
      "verified_at": 1745200000,
      "use_as_onboarding_question": false
    },
    {
      "name": "rental_revenue_by_season",
      "question": "What is the rental revenue and rental markup dollars by ski season?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n  {{ target.database }}.SEMANTIC.SEM_REVENUE\n  METRICS rental_revenue, rental_markup_dollars\n  DIMENSIONS ski_season\n) ORDER BY ski_season DESC NULLS LAST",
      "verified_by": "Cortex Analyst",
      "verified_at": 1745200000,
      "use_as_onboarding_question": false
    },
    {
      "name": "advance_purchase_by_passholder",
      "question": "How does the advance purchase rate and average ticket price differ between pass holders and non-pass holders by ticket category?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n  {{ target.database }}.SEMANTIC.SEM_REVENUE\n  METRICS advance_sales_share_pct, average_ticket_price\n  DIMENSIONS is_pass_holder, ticket_category\n) ORDER BY ticket_category NULLS LAST, is_pass_holder NULLS LAST",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": false
    }
  ]
}
$$)
