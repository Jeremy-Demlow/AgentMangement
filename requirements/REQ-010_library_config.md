# REQ-010: Library Configuration & Reusable Template

## Summary
Centralize all project-specific names (databases, schemas, warehouses, roles, raw tables) into a single `project.yml` configuration file, eliminating hardcoded references throughout the codebase so the framework can be reused for any domain.

## Business Context
The framework was developed against a ski resort demo dataset. Hardcoded references to `SKI_RESORT_DB`, `SADM_SKI_RESORT_DB`, `COMPUTE_WH`, etc. prevent anyone from reusing the framework for their own Cortex Agent + Semantic View CI/CD workflow. A project-level config makes the framework domain-agnostic and pip-installable.

## Acceptance Criteria
- [x] `project.yml` exists at repo root with all domain-specific names
- [x] `scripts/utils/config.py` exposes `get_expected_databases()`, `get_eval_source_database()`, `get_eval_config()`, `get_raw_tables()`, `get_project_schemas()`
- [x] Tests (`test_smoke.py`, `test_templates.py`) read expected DB names from project config, not hardcoded dicts
- [x] Eval configs (`agent-evaluation/configs/*.yaml`) use Jinja2 placeholders (`{{ eval.source_database }}`)
- [x] Eval datasets (`agent-evaluation/datasets/*.yaml`) use `{{ eval.source_database }}` instead of hardcoded DB names
- [x] GitHub Actions workflow (`daily_data_refresh.yml`) reads database/schema from `project.yml` at runtime
- [ ] `grep -r 'SKI_RESORT_DB\|SADM_SKI_RESORT_DB' scripts/ tests/test_smoke.py tests/test_templates.py agent-evaluation/configs/ agent-evaluation/datasets/ .github/workflows/` returns 0 matches (excluding snapshots/generated)
- [ ] All existing tests pass after refactor
- [ ] Documentation updated (architecture.md, dev_notes.md)

## User Stories
| Story ID | As a... | I want to... | So that... |
|----------|---------|-------------|------------|
| US-020   | Developer | change one config file to point at my own databases | I can reuse the framework without find-and-replace |
| US-021   | CI operator | have the workflow read DB names from config | I don't need to edit YAML workflow files to change targets |
| US-022   | OSS consumer | fork the repo and customize `project.yml` | I can deploy agents/SVs to my own Snowflake account immediately |

## Dependencies
- REQ-001: Environment Configuration System (provides per-env configs that complement project.yml)
- REQ-004: Eval Framework (eval configs/datasets now use templated DB names)
- REQ-006: GitHub Actions (workflow now reads from project.yml)

## Out of Scope
- Pip-installable package distribution (REQ-011, future phase)
- CLI tool for project initialization (`agent-mgmt init`)
- Auto-detection of Snowflake objects for project.yml generation

## Architecture

```
project.yml                    <-- Single source of truth for all names
  |
  +-- environments/{env}.env.yml   <-- Per-env overrides (database, thresholds)
  |
  +-- scripts/utils/config.py      <-- Loads both, exposes typed helpers
  |     |
  |     +-- get_expected_databases()      -> {"dev": "...", "qa": "...", "prod": "..."}
  |     +-- get_eval_source_database()    -> "SADM_SKI_RESORT_DB"
  |     +-- get_eval_config(env_config)   -> {source_database, stage, file_format, ...}
  |     +-- get_raw_tables()              -> ["PASS_USAGE", "LIFT_SCANS", ...]
  |     +-- get_project_schemas()         -> {"raw": "RAW", "marts": "MARTS", ...}
  |
  +-- tests/               <-- Read EXPECTED_DBS from config
  +-- agent-evaluation/    <-- {{ eval.source_database }} in YAML templates
  +-- .github/workflows/   <-- Reads project.yml at runtime
```

## Notes
- Snapshots and generated files (`agents/snapshots/`, `agents/generated/`, `semantic-views/snapshots/`) are expected to contain hardcoded names since they capture point-in-time state
- Documentation files (architecture.md, test_cases.md) use specific names for clarity in examples
- `data_generation/` scripts have their own hardcoded refs; these are out of scope for this REQ (separate domain)
