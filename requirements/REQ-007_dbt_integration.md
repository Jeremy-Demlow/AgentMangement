# REQ-007: dbt Integration Points

## Summary
Integrate the existing `dbt_ski_resort/` project into the CI/CD pipeline, with enforced deploy ordering: dbt build runs before semantic views and agents are deployed.

## Implementation Status

The dbt project already exists at `dbt_ski_resort/`:

| Component | Status | Location |
|-----------|--------|----------|
| dbt project (Kimball model) | EXISTS | `dbt_ski_resort/` |
| 23 staging models | EXISTS | `dbt_ski_resort/models/staging/` |
| 6 dimension tables | EXISTS | `dbt_ski_resort/models/marts/dimensions/` |
| 13 incremental fact tables | EXISTS | `dbt_ski_resort/models/marts/facts/` |
| 11 semantic views (dbt materialization) | EXISTS | `dbt_ski_resort/models/marts/semantic/` |
| Profiles.yml (SKI_RESORT_DB) | EXISTS | `dbt_ski_resort/profiles.yml` |
| dbt_semantic_view package | EXISTS | `dbt_ski_resort/packages.yml` |
| Daily dbt run (GHA cron) | EXISTS | `.github/workflows/daily_data_refresh.yml` |
| dbt steps in CI/CD promotion workflows | TO BUILD | `.github/workflows/promote-*.yml` |
| dbt target mapping to SNOWFLAKE_ENV | TO BUILD | Environment-aware profile configuration |
| dbt/README.md integration guide | TO BUILD | `dbt_ski_resort/` or `docs/` |

## Business Context
Semantic views reference base tables (facts and dimensions) that are materialized by dbt. If those tables do not exist or have stale schemas when semantic views deploy, the pipeline fails with confusing errors. The daily_data_refresh.yml already runs `dbt run --select "marts.facts"` and `dbt run --select "marts.semantic"` on a cron. The CI/CD promotion workflows need to optionally include dbt as a step for environments that don't have the daily pipeline.

## Acceptance Criteria
- [x] dbt project exists with full Kimball model (23 staging, 6 dims, 13 facts)
- [x] 11 semantic views materialized via `dbt_semantic_view` package
- [x] Daily dbt run automated in `daily_data_refresh.yml`
- [x] Integration guide documents: profile structure, env-aware target selection, deploy order
- [x] GitHub Actions CI/CD workflows include optional dbt steps (`if: hashFiles('dbt_ski_resort/dbt_project.yml') != ''`)
- [x] Deploy order documented and enforced: dbt build -> semantic views -> agents -> eval
- [x] dbt profile supports SNOWFLAKE_ENV for target selection (dev/qa/prod)

## User Stories
| Story ID | As a... | I want to... | So that... |
|----------|---------|-------------|------------|
| US-020   | data engineer | a clear integration guide for my dbt project | I can plug my existing dbt project into this pipeline without guessing |
| US-021   | DevOps engineer | conditional dbt steps in the pipeline | the pipeline works correctly with or without a dbt project present |

## Dependencies
- REQ-001: Environment Configuration System (dbt targets map to environments)
- REQ-006: GitHub Actions Workflows (dbt steps are part of the workflow chain)
- REQ-008: Data Generation Pipeline (dbt sources come from data_generation/)

## Out of Scope
- dbt Cloud integration (CLI-only approach)
- dbt package management beyond what the project defines
- Deploying dbt as a Snowflake native object (`snow dbt deploy`)
- Modifying the existing dbt models (user owns the dbt project)

## Notes
- dbt project: `dbt_ski_resort/` with profile `dbt_ski_resort`
- Target database: SKI_RESORT_DB, schema: MARTS, warehouse: COMPUTE_WH
- Uses `SNOWFLAKE_PASSWORD` env var for CI auth (profiles.yml)
- `dbt_semantic_view` package (Snowflake-Labs) materializes semantic views via SQL
- The daily_data_refresh.yml runs facts then semantic in sequence — same ordering needed in CI/CD
- Full refresh supported via `dbt run --select "marts.facts" --full-refresh`
