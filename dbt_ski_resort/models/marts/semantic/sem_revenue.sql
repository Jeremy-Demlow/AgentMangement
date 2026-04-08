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
    DIM_DATE.FULL_DATE AS FULL_DATE
      WITH SYNONYMS ('transaction_date')
      COMMENT = 'Transaction date',
    DIM_DATE.SKI_SEASON AS SKI_SEASON
      COMMENT = 'Ski season identifier',
    DIM_DATE.MONTH_NAME AS MONTH_NAME
      COMMENT = 'Calendar month name',
    DIM_CUSTOMER.CUSTOMER_SEGMENT AS CUSTOMER_SEGMENT
      COMMENT = 'Customer persona classification',
    DIM_CUSTOMER.IS_PASS_HOLDER AS IS_PASS_HOLDER
      COMMENT = 'Pass holder indicator',
    DIM_LOCATION.LOCATION_NAME AS LOCATION_NAME
      COMMENT = 'Point-of-sale location name',
    DIM_LOCATION.LOCATION_TYPE AS LOCATION_TYPE
      COMMENT = 'Location category (ticket window, rental shop, dining)',
    DIM_TICKET_TYPE.TICKET_CATEGORY AS TICKET_CATEGORY
      COMMENT = 'Ticket product category (Season Pass, Day Ticket, etc.)',
    DIM_PRODUCT.PRODUCT_CATEGORY AS PRODUCT_CATEGORY
      COMMENT = 'Rental or F&B product category',
    DIM_PRODUCT.PRODUCT_TYPE AS PRODUCT_TYPE
      COMMENT = 'Specific product type (Demo Skis, Summit Restaurant, etc.)'
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
    "question_categorization": "Route lift operations, wait time, or capacity conversations to SKI_RESORT_DB.SEMANTIC.SEM_OPERATIONS. Route pass utilization, renewal, or loyalty questions to SKI_RESORT_DB.SEMANTIC.SEM_PASSHOLDER_ANALYTICS. Route persona-only behavioral questions to SKI_RESORT_DB.SEMANTIC.SEM_CUSTOMER_BEHAVIOR. When a request omits the product family or channel, ask whether the user wants ticket sales, rentals, food & beverage, or a combined view before responding. Clarify whether forecasted revenue should be included when the date range extends into future periods.",
    "sql_generation": "Aggregate ticket revenue from FACT_TICKET_SALES, rentals from FACT_RENTALS, and F&B from FACT_FOOD_BEVERAGE; combine only when explicitly requested. Use DIM_DATE.FULL_DATE for calendar filters and DIM_DATE.SKI_SEASON for seasonal framing; leverage DATE_TRUNC for month or season aggregation. Join DIM_LOCATION, DIM_TICKET_TYPE, or DIM_PRODUCT to segment results, applying ILIKE filters for flexible text matching. Guard division with DIV0(...) and include NULLS LAST when ordering by computed metrics. Filter channel insights with FACT_TICKET_SALES.PURCHASE_CHANNEL and document whether online or in-resort sales are included."
  }
}
$$)
