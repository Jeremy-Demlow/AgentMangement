# Data Generation

Synthetic ski resort data generation and loading scripts for the Agent Management reference framework.

## Directory Layout

```
data-generation/
  generate_complete_ski_data.py    # Full historical data generation (4 years)
  generate_daily_increment.py      # Daily incremental data (used in CI/CD)
  generate_documents.py            # Document content for Cortex Search
  load_documents_to_snowflake.py   # Upload documents to Snowflake stage
  load_seed_data.py                # Load CSV seeds into Snowflake
  reload_from_local.py             # Reload all data from local files
  shared.py                        # Constants, RNG, helpers shared across generators
  config.py                        # Project config loader (reads project.yml)
  snowflake_connection.py          # Snowflake connector wrapper
  documents.json                   # Generated document content
  social_media_tweets.csv          # Sample social media data
```

## How It Works

Data flows **PROD-first**: the `daily_data_refresh.yml` workflow generates new data in PROD, then `sync_env_data.yml` copies RAW tables to DEV and QA. This ensures all environments test against the same dataset.

```
generate_daily_increment.py → AM_SKI_RESORT.RAW.*
  └── sync_env_data.yml → AM_SKI_RESORT_DEV.RAW.* / AM_SKI_RESORT_QA.RAW.*
      └── dbt run → rebuild STAGING + MARTS in each env
```

## Common Operations

### Generate daily increment (CI/CD or manual)

```bash
cd data-generation
python generate_daily_increment.py --env prod --date 2026-04-13
python generate_daily_increment.py --env dev --date 2026-04-13 --days 7
```

The script is **idempotent** — it checks for existing data before inserting and skips dates that already have records.

### Generate full historical dataset (initial setup only)

```bash
python generate_complete_ski_data.py
```

Generates ~4 years of synthetic ski resort data across 13 RAW tables. Only needed once during initial project setup.

### Load documents for Cortex Search

```bash
python generate_documents.py
python load_documents_to_snowflake.py --env dev
```

## Adding a New RAW Table

1. Add the generation logic to both `generate_complete_ski_data.py` and `generate_daily_increment.py`.
2. Add shared constants (IDs, categories, probabilities) to `shared.py`.
3. Add the table name to `raw_tables` in `project.yml` (so `sync_env_data.yml` knows to sync it).
4. Create the table DDL in all environments via DCM or manual `CREATE TABLE ... LIKE`.
5. Add a dbt staging model in `dbt_ski_resort/models/staging/`.

## Conventions

- **Idempotency**: All incremental scripts must check for existing data before inserting. Use `check_date_exists()` from the daily generator as a pattern.
- **RNG seeding**: `generate_complete_ski_data.py` uses a seeded RNG for reproducible historical data. `generate_daily_increment.py` uses an unseeded RNG for truly random daily variation.
- **Config from project.yml**: Database names, schemas, and environment mappings come from `config.py` which reads `project.yml`. Never hardcode Snowflake object names.
- **Environment flag**: Scripts accept `--env` to target different environments. Defaults to PROD for backward compatibility.

## Dependencies

These scripts use `pandas`, `numpy`, and `snowflake-connector-python`. They are not part of the `agent_management` package — they run standalone with their own imports.
