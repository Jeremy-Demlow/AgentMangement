# Ski Resort Analytics DBT Project

This DBT project implements a Kimball-style dimensional model for ski resort operations analytics, designed to work with Snowflake semantic views and Cortex Analyst.

## Project Structure

```
dbt_ski_resort/
├── models/
│   ├── staging/          # Type-safe views from raw data
│   ├── intermediate/     # Ephemeral business logic transformations
│   └── marts/
│       ├── dimensions/   # Dimension tables (6 total)
│       ├── facts/        # Fact tables (5 total, incremental)
│       └── semantic/     # Semantic views for agents
├── tests/                # Data quality tests
├── macros/               # Custom SQL macros
├── seeds/                # Static reference data
└── analyses/             # Ad-hoc analyses

```

## Dimensional Model

### Dimensions (6)
- `dim_date` - Date dimension with ski season attributes
- `dim_customer` - Customer profiles with Type 2 SCD
- `dim_lift` - Lift infrastructure and capacity
- `dim_location` - Rental shops, F&B venues, ticket windows
- `dim_product` - Rentals and F&B items with Type 2 SCD
- `dim_ticket_type` - Ticket and pass types with Type 2 SCD

### Facts (5 - Incremental)
- `fact_lift_scans` - Lift scan events with wait times
- `fact_pass_usage` - Daily customer visit summaries
- `fact_ticket_sales` - Ticket/pass purchases
- `fact_rentals` - Equipment rentals
- `fact_food_beverage` - F&B transactions

### Semantic Views (4)
- `sem_operations` - Lift utilization and wait times
- `sem_customer_behavior` - Customer segments and churn
- `sem_revenue` - Revenue analytics
- `sem_passholder_analytics` - Pass holder ROI

## Setup

```bash
# Install dependencies
cd dbt_ski_resort
dbt deps

# Test connection
dbt debug

# Run models
dbt run

# Run tests
dbt test

# Generate documentation
dbt docs generate
dbt docs serve
```

## Connection Configuration

This project uses the `agents_example` Snowflake CLI connection. The `profiles.yml` is configured for dual compatibility:
- Local development via Snowflake CLI
- dbt Projects on Snowflake (native execution)

## Data Refresh

The models support incremental loads:
```bash
# Full refresh
dbt run --full-refresh

# Incremental (daily)
dbt run
```

## Customer Personas

The data includes 7 realistic customer segments:
1. Local Season Pass Holders (15%)
2. Weekend Warriors (25%)
3. Vacation Families (30%)
4. Day Trippers (20%)
5. Expert/Backcountry Skiers (5%)
6. Groups & Corporate (3%)
7. Beginners/First-Timers (2%)

## Demo Queries

Once deployed, semantic views enable natural language queries via Cortex Analyst:
- "Which customer segments have the highest lifetime value?"
- "How does weather affect attendance 24-48 hours later?"
- "What's the ROI of season pass holders vs day visitors?"
- "Which lifts should we staff first on Saturday mornings?"
