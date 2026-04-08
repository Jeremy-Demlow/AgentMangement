# REQ-002: Semantic View CI/CD Pipeline

## Summary
Semantic views defined as YAML in Git and deployed via `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML`, with dry-run validation and drift detection against the live Snowflake state.

## Business Context
Semantic views are the bridge between raw tables and Cortex Agents. When they are only managed through the Snowsight UI, there is no version history, no PR review, no way to detect unauthorized edits, and no mechanism to promote changes across environments. Defining them as YAML in Git and deploying via CI/CD solves all of these problems.

## Acceptance Criteria
- [ ] 4 semantic view YAML files in `semantic-views/definitions/` (sem_daily_summary, sem_revenue, sem_operations, sem_staffing_analytics)
- [ ] `deploy_semantic_views.py` creates/replaces SVs via `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML`
- [ ] `--dry-run` flag validates YAML without deploying (uses 3rd arg `TRUE`)
- [ ] `--view <name>` deploys a single semantic view
- [ ] Drift detection compares Git YAML vs deployed state via `SYSTEM$READ_YAML_FROM_SEMANTIC_VIEW`
- [ ] Deploy script respects environment config for database/schema resolution
- [ ] All semantic view YAML files use Jinja2 placeholders for env-specific FQNs

## User Stories
| Story ID | As a... | I want to... | So that... |
|----------|---------|-------------|------------|
| US-003   | data engineer | semantic views defined in Git | changes go through PR review before reaching any environment |
| US-004   | data engineer | dry-run validation before deploying | I catch YAML errors and missing columns before they break production |
| US-005   | operator | drift detection comparing Git vs deployed state | I know if someone edited a semantic view in the UI without updating Git |

## Dependencies
- REQ-001: Environment Configuration System (for database/schema resolution)

## Out of Scope
- Creating the underlying base tables (handled by dbt, see REQ-007)
- Semantic view performance tuning or query optimization
- Semantic model files on stages (this repo uses semantic views, not stage-based YAML models)

## Notes
- `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML(schema_fqn, yaml, validate_only)` is the deploy mechanism
- `SYSTEM$READ_YAML_FROM_SEMANTIC_VIEW(view_fqn)` exports current deployed state for drift comparison
- Round-trip YAML is lossy on first pass but idempotent thereafter (ordering/formatting changes)
- 4 of 11 total ski resort semantic views included; pattern scales to all 11
