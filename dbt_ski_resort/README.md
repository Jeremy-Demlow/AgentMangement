# Ski Resort Analytics DBT Project

This DBT project implements a Kimball-style dimensional model for ski resort operations analytics, designed to work with Snowflake semantic views and Cortex Analyst.

## Project Structure

```
dbt_ski_resort/
├── models/
│   ├── staging/          # Type-safe views from raw data (23)
│   └── marts/
│       ├── dimensions/   # Dimension tables (6)
│       ├── facts/        # Fact tables (13, incremental)
│       └── semantic/     # Semantic views for agents (11)
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

### Facts (13 - Incremental)
- `fact_lift_scans` - Lift scan events with wait times
- `fact_pass_usage` - Daily customer visit summaries
- `fact_ticket_sales` - Ticket/pass purchases
- `fact_rentals` - Equipment rentals
- `fact_food_beverage` - F&B transactions
- Plus 8 additional fact tables covering weather, staffing, incidents, lessons, parking, grooming, customer feedback, and marketing

### Semantic Views (11)
- `sem_operations` - Lift utilization and wait times
- `sem_customer_behavior` - Customer segments and churn
- `sem_revenue` - Revenue analytics
- `sem_passholder_analytics` - Pass holder ROI
- `sem_customer_satisfaction` - Customer feedback and NPS
- `sem_daily_summary` - Daily operational summary
- `sem_lessons_analytics` - Ski lessons performance
- `sem_marketing_analytics` - Marketing campaign effectiveness
- `sem_safety_incidents` - Safety and incident tracking
- `sem_staffing_analytics` - Staffing levels and efficiency
- `sem_weather_analytics` - Weather impact analysis

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

This project uses the `dbt_ski_resort` profile. The `profiles.yml` is configured for dual compatibility:
- Local development via Snowflake CLI
- dbt Projects on Snowflake (native execution)

Environment-specific targets:

| Target | Database | Warehouse | Role |
|--------|----------|-----------|------|
| `dev` | `AM_SKI_RESORT_DEV` | `AM_SKI_RESORT_WH_DEV` | `AM_DEPLOY_ROLE_DEV` |
| `qa` | `AM_SKI_RESORT_QA` | `AM_SKI_RESORT_WH_QA` | `AM_DEPLOY_ROLE_QA` |
| `prod` | `AM_SKI_RESORT` | `AM_SKI_RESORT_WH` | `AM_DEPLOY_ROLE` |

## CI/CD Integration

### `dbt run` vs `dbt build`

CI/CD deploy workflows use `dbt run` (not `dbt build`) because `dbt build` includes tests that store failures to a `DBT_TEST__AUDIT` schema. The deploy role cannot create this schema unless DCM has provisioned it first. After DCM deploys the schema with proper grants, `dbt build` becomes viable.

### Selector Patterns

The `+` prefix in dbt selectors means "build this AND all upstream dependencies":

```bash
dbt run --target dev --select "+marts.facts" --profiles-dir .
```

This builds all staging views first (upstream dependencies), then dimensions, then fact tables — in dependency order.

```bash
dbt run --target dev --select "marts.semantic" --profiles-dir .
```

Semantic views reference fact/dimension tables, so they run after facts.

### `--profiles-dir .`

In CI/CD, `--profiles-dir .` tells dbt to use the `profiles.yml` in the project directory (not `~/.dbt/profiles.yml`). This ensures the CI runner uses the checked-in profile with environment variable overrides.

### Environment Variable Override

The `profiles.yml` uses `{{ env_var('SNOWFLAKE_DATABASE', 'AM_SKI_RESORT_DEV') }}` for all connection properties. GitHub Actions sets these via environment secrets. Locally, the `test_workflow_locally.sh` script force-sets them per `TARGET_ENV`.

**Warning:** The Snowflake IDE (Cortex Code) sets `SNOWFLAKE_DATABASE` in the parent shell environment. This overrides the `${VAR:-default}` bash syntax and can cause dbt to target the wrong database. Always explicitly set environment variables when running dbt locally.

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
