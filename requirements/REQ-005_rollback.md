# REQ-005: Snapshot and Rollback

## Summary
Capture the deployed state of agents and semantic views before every change, and provide rollback capability to restore any prior state when something breaks due to semantic metadata conflicts or bad configurations.

## Business Context
When a semantic view change breaks an agent — perhaps a column was renamed, a table was dropped, or a metric definition changed — the team needs to restore the previous working state immediately. Without snapshots, the only recourse is to dig through Git history and manually reconstruct the prior deployment. Pre-deploy snapshots and a rollback script provide one-command restoration to any previous known-good state.

## Acceptance Criteria
- [ ] `snapshot_state.py` captures current agent spec via `DESCRIBE AGENT` and SV YAML via `SYSTEM$READ_YAML_FROM_SEMANTIC_VIEW`
- [ ] Snapshots saved as timestamped files in `agents/snapshots/` and `semantic-views/snapshots/`
- [ ] Snapshot metadata also persisted to Snowflake `CI_CD_SNAPSHOTS` table for auditability
- [ ] `rollback.py` re-deploys a specific snapshot by timestamp
- [ ] `rollback.py --target agents|semantic-views|both` controls rollback scope
- [ ] GitHub Actions prod workflow auto-triggers rollback on eval failure
- [ ] Snapshot files are `.gitignore`d (they are deployment artifacts, not source)

## User Stories
| Story ID | As a... | I want to... | So that... |
|----------|---------|-------------|------------|
| US-013   | operator | pre-deploy snapshots of current state | I always have a known-good state to restore if a deploy breaks something |
| US-014   | operator | rollback by timestamp | I can restore any prior deployment, not just the most recent one |
| US-015   | DevOps engineer | auto-rollback on prod eval failure | broken changes are automatically reversed without manual intervention |

## Dependencies
- REQ-001: Environment Configuration System (for connecting to the right environment)
- REQ-002: Semantic View CI/CD Pipeline (SV snapshot uses `SYSTEM$READ_YAML_FROM_SEMANTIC_VIEW`)
- REQ-003: Agent CI/CD Pipeline (agent snapshot uses `DESCRIBE AGENT`)

## Out of Scope
- Native Snowflake version timeline / rollback UI (does not exist today)
- Time Travel for agent objects (not supported)
- Rollback of dbt models or base tables (only agents and semantic views)
- Multi-environment coordinated rollback (each env rolls back independently)

## Notes
- `DESCRIBE AGENT <name>` returns AGENT_SPEC as JSON — preferred over `GET_DDL('CORTEX_AGENT', ...)` which has formatting bugs
- `SYSTEM$READ_YAML_FROM_SEMANTIC_VIEW(<fqn>)` returns the current deployed YAML
- Snapshots are local files + Snowflake table; local files are gitignored
- Rollback is effectively "re-deploy a previous spec" — same mechanism as forward deploy
- CI_CD_SNAPSHOTS table schema: timestamp, environment, object_type, object_name, spec_content
