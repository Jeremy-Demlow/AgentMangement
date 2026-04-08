# REQ-008: Data Generation Pipeline

## Summary
Synthetic ski resort data generation covering 21 Snowflake tables across 5 ski seasons (Nov 2020 - present), with daily incremental generation automated via GitHub Actions cron and manual triggers with recovery options.

## Implementation Status

This component is fully built:

| Component | Status | Location |
|-----------|--------|----------|
| Complete historical data generator | EXISTS | `data_generation/generate_complete_ski_data.py` |
| Daily incremental generator | EXISTS | `data_generation/generate_daily_increment.py` |
| Shared constants (personas, lifts, zones) | EXISTS | `data_generation/shared.py` |
| Snowflake connection wrapper | EXISTS | `data_generation/snowflake_connection.py` |
| Document generator (14 docs for Cortex Search) | EXISTS | `data_generation/generate_documents.py` |
| Seed data loader | EXISTS | `data_generation/load_seed_data.py` |
| Fast reload from local CSV | EXISTS | `data_generation/reload_from_local.py` |
| GitHub Actions daily cron | EXISTS | `.github/workflows/daily_data_refresh.yml` |
| Pipeline setup guide | EXISTS | `.github/PIPELINE_SETUP.md` |

## Business Context
The evaluation framework requires fresh, realistic data to produce meaningful eval results. Stale data means golden questions with `validation_query` return different answers than expected, causing false eval failures. The daily data pipeline ensures RAW tables always have data through the current date, so dbt models, semantic views, and agents all operate on current data.

## Acceptance Criteria
- [x] 21 RAW tables generated covering core transactions, operations, customers, marketing, facilities
- [x] 8000 synthetic customers across 7 persona segments
- [x] 5 ski seasons of historical data (Nov 2020 - present)
- [x] Daily incremental generation with idempotency checks (skip if date already exists)
- [x] Smart backfill for gap detection and recovery
- [x] Reproducible via seeded RNG (seed=42)
- [x] GitHub Actions cron at 5am PST with manual override
- [x] Recovery options: rebuild_from_date, full_refresh, clear_raw_data
- [x] Setup guide with secrets configuration
- [x] Unstructured document generation for Cortex Search (14 documents)

## User Stories
| Story ID | As a... | I want to... | So that... |
|----------|---------|-------------|------------|
| US-022   | developer | synthetic data generated daily on a schedule | the demo environment always has current, realistic data for agent evaluations |
| US-023   | developer | recovery options for data corruption | I can rebuild from any date without losing the entire dataset |

## Dependencies
- REQ-007: dbt Integration (dbt consumes RAW tables as sources)
- REQ-004: Evaluation Framework (eval golden questions reference current data via validation_query)

## Out of Scope
- Real customer data or PII
- Data masking or anonymization (data is entirely synthetic)
- Streaming/real-time data ingestion
- Data volume scaling beyond demo size (8000 customers)

## Notes
- Target database: SKI_RESORT_DB.RAW
- Uses Snowpark Python for connection and data loading (PUT + COPY INTO)
- 7 customer personas with distinct behavior patterns: family, young_adult, retired, local, tourist, corporate, budget
- 18 lift definitions with capacity and popularity weighting
- Weather conditions vary by mountain zone (base, mid, summit) and season
- `generate_complete_ski_data.py` is for initial setup; `generate_daily_increment.py` is for ongoing
- GitHub Action uses `snowflakedb/snowflake-cli-action@v1.5` for Snowflake CLI
- Pipeline integrates: data_gen -> dbt facts -> dbt semantic -> verify (in that order)
