# Development Notes

Running log of decisions, findings, and progress. Newest entries at the top.

---

## 2026-04-06 — Agent Naming + Data Flow Direction (Session 15)

### Agent Naming Strategy (Single-Account)
When all environments share one Snowflake account, agents need disambiguated names:
- **PROD**: No suffix — `RESORT_EXECUTIVE`, `SKI_OPS_ASSISTANT` (the canonical agents)
- **DEV**: `_DEV` suffix — `RESORT_EXECUTIVE_DEV`, `SKI_OPS_ASSISTANT_DEV`
- **QA**: `_QA` suffix — `RESORT_EXECUTIVE_QA`, `SKI_OPS_ASSISTANT_QA`

Profile `display_name` automatically gets `[DEV]`/`[QA]` label for Snowsight UI visibility.

For cross-account deployments (separate dev/qa/prod accounts), all agents keep the same name since account isolation provides disambiguation. Controlled by `deployment.mode` in project.yml.

### Data Flow Direction
Reversed the clone direction: **PROD is source of truth**.
- PROD has the real data
- DEV/QA clone from PROD (not DEV → QA/PROD as before)
- Controlled by `deployment.data_source: prod` in project.yml

### Files Changed
- `project.yml` — Added `deployment.mode`, `deployment.data_source`, `name_suffix` per env
- `environments/dev.env.yml` — `name_suffix: _DEV`
- `environments/qa.env.yml` — `name_suffix: _QA`
- `agent_management/utils/config.py` — `_resolve_name_suffix()`, `get_deployment_mode()`, `get_data_source_env()`
- `agent_management/deploy_agents.py` — `resolve_profile()`, updated SQL builders
- `agent-evaluation/scripts/run_eval.py` — Read `agent.name_suffix` for auto-suffixing
- `tests/test_smoke.py` — Updated FQN assertions for suffixed names

### Snowflake State
| Env | Agents |
|-----|--------|
| DEV | RESORT_EXECUTIVE_DEV [DEV], SKI_OPS_ASSISTANT_DEV [DEV] |
| QA  | RESORT_EXECUTIVE_QA [QA], SKI_OPS_ASSISTANT_QA [QA] |
| PROD | RESORT_EXECUTIVE, SKI_OPS_ASSISTANT |

---

## 2026-04-06 — Full Pipeline Execution: DEV → QA → PROD (Session 14)

Executed the complete pipeline across all three environments. Migrated all eval references from `SADM_SKI_RESORT_DB` to per-environment `AM_SKI_RESORT_*` databases.

### SADM → AM Eval Migration

Removed `eval.source_database: SADM_SKI_RESORT_DB` from `project.yml`. Updated `get_eval_config()` to fall back to the environment's deployment database when no static source_database is configured. Tests updated to expect per-env databases (`AM_SKI_RESORT_DEV`, `_QA`, `_PROD`). **76/76 tests pass.**

### Connection Fixes
- `snowflake_client.py`: Reordered auth to check `SNOWFLAKE_CONNECTION_NAME` first (IDE leaks `SNOWFLAKE_PASSWORD` as JWT)
- `profiles.yml`: QA/PROD targets switched from password auth (`jd_service_account_admin`) to key-pair auth (`JDEMLOW`) for local dev
- Granted `AM_DEPLOY_ROLE_QA` and `AM_DEPLOY_ROLE_PROD` to user JDEMLOW

### Pipeline Execution Results

| Step | DEV | QA | PROD |
|------|-----|-----|------|
| DCM Deploy | 16 entities | 16 entities | 16 entities |
| RAW Data | 24 tables (original) | 24 tables (zero-copy clone) | 24 tables (zero-copy clone) |
| dbt Build | 193 PASS, 5 WARN, 0 ERR | 193 PASS, 5 WARN, 0 ERR | 193 PASS, 5 WARN, 0 ERR |
| Semantic Views | 11/11 deployed | 11/11 deployed | 11/11 deployed |
| Agents | 2 (11+4 tools) | 2 (11+4 tools) | 2 (11+4 tools) |

### Agent Evaluation Results

| Eval | answer_correctness | logical_consistency |
|------|-------------------|---------------------|
| DEV RESORT_EXECUTIVE | 0.53 | 0.93 |
| DEV SKI_OPS_ASSISTANT | 0.80 | 1.00 |
| QA RESORT_EXECUTIVE | 0.67 | 0.96 |
| QA SKI_OPS_ASSISTANT | 0.80 | 1.00 |
| PROD RESORT_EXECUTIVE | 0.42 | 1.00 |
| PROD SKI_OPS_ASSISTANT | pending | 1.00 |

- **logical_consistency** is consistently high (0.93–1.00) across all environments
- **answer_correctness** varies (0.42–0.80) due to dynamic ground truth comparison sensitivity
- SKI_OPS_ASSISTANT outperforms RESORT_EXECUTIVE on answer_correctness (fewer tools = more focused responses)

### Eval Run Names (for future reference)
- DEV: `resort_executive_eval_20260406_110203`, `ski_ops_assistant_eval_20260406_110337`
- QA: `resort_executive_eval_20260406_114225`, `ski_ops_assistant_eval_20260406_114327`
- PROD: `resort_executive_eval_20260406_114405`, `ski_ops_assistant_eval_20260406_114458`

### Files Changed
- `project.yml`: Removed `eval.source_database: SADM_SKI_RESORT_DB`
- `agent_management/utils/config.py`: `get_eval_source_database()` accepts optional `env_name`, `get_eval_config()` falls back to deployment database
- `agent_management/utils/snowflake_client.py`: Connection precedence fix (`SNOWFLAKE_CONNECTION_NAME` checked first)
- `dbt_ski_resort/profiles.yml`: QA/PROD targets use key-pair auth locally
- `tests/test_smoke.py`: Eval tests use per-env database expectations
- `tests/test_templates.py`: Removed static `EVAL_SOURCE_DB` variable
- `agent-evaluation/configs/ski_ops_assistant.yaml`: New eval config template
- `agent-evaluation/configs/resort_executive_eval_config.yaml`: Fixed SADM comment

---

## 2026-04-06 — Library Refactor: scripts/ to agent_management/ (Session 13 cont.)

Restructured the repository to separate reusable library code from domain-specific artifacts.

### What Changed

- **`scripts/` → `agent_management/`** — All 10 core modules, `utils/` (config, snowflake_client), and `ci/` (3 fdbt scripts) moved into a proper Python package.
- **`pyproject.toml`** — Package renamed `agent-management` v0.6.0. Entry points updated from `scripts.*` to `agent_management.*`. `[tool.setuptools.packages.find]` now includes `agent_management*`.
- **All internal imports** — `from scripts.` → `from agent_management.` across all 10 modules and 3 CI scripts.
- **Tests** — Removed `sys.path.insert` hacks from `test_smoke.py` and `test_templates.py`. All imports now use proper package paths.
- **GitHub Actions** — All 5 workflows updated (`validate-pr`, `deploy-dev`, `promote-qa`, `promote-prod`, `rollback`): `python -m scripts.*` → `python -m agent_management.*`.
- **AGENTS.md** — Folder structure updated to show `agent_management/` instead of `scripts/`.
- **Cleanup** — Removed old `scripts/` directory and stale `agent_mgmt.egg-info/`.

### Why

Clean separation between:
1. **Library** (`agent_management/`) — reusable CI/CD tooling for Cortex Agents, Semantic Views, and dbt
2. **Domain artifacts** — ski resort dbt models, agent specs, eval datasets, semantic view definitions

The library is pip-installable (`pip install -e .`) and importable as `agent_management`.

### Validation

- 76/76 pytest tests pass
- `python -m agent_management.validate_specs --env dev` — ALL VALID (2 agents, 11 SVs)
- `python -m agent_management.ci.check_test_coverage` — PASS (70.4%)
- `python -m agent_management.ci.check_pk_tests` — PASS (all non-skipped models have PK tests)
- Package imports: `from agent_management import __version__` → "0.6.0"

---

## 2026-04-04 — fdbt CI Integration (Session 13)

Integrated fdbt (fast dbt manifest parser) into the CI pipeline. fdbt runs in ~17ms with no Snowflake connection — parses the dbt manifest locally for instant test coverage, lineage, and impact analysis.

### New CI Scripts (`agent_management/ci/`)

**`check_test_coverage.py`** — Enforces minimum test coverage threshold (default 70%). Parses fdbt output to extract model coverage percentage and fails the PR if below threshold. Writes results to `GITHUB_OUTPUT` for downstream steps.

**`check_pk_tests.py`** — Validates every model has `not_null` + `unique` tests on its primary key. Skips semantic view models (no columns to test) and passthrough staging models. Parses the full `fdbt tests list` output (not per-model, which has a bug).

**`generate_lineage_comment.py`** — Generates a markdown PR comment showing impact analysis and downstream lineage for changed models. Auto-detects changed models from `git diff` or accepts explicit `--models` flag. Uses fdbt `impact` and `lineage` commands. The GHA workflow upserts the comment (updates existing if present).

### Workflow Changes

Updated `.github/workflows/validate-pr.yml`:
- Added `dbt_ski_resort/**` to path triggers
- New `dbt-quality-gate` job with 4 steps: install fdbt, check coverage, validate PK tests, post lineage comment
- `validate-snowflake` now depends on `dbt-quality-gate` in addition to lint and spec validation
- Lineage comment auto-posted to PR using `actions/github-script@v7`

### Current Coverage Stats
```
Model coverage: 70.4% (38/54 models tested, 16 untested)
16 untested: 11 semantic views + 5 passthrough staging models
140 total dbt tests
All non-skipped models have PK tests (not_null + unique)
```

### fdbt Learnings
- `fdbt tests list -m <model>` returns 0 tests (per-model filter broken) — use full `fdbt tests list` and parse
- `fdbt lineage -d` requires `--depth N` flag, not just `-d`
- `fdbt impact <model>` works without flags and provides criticality scoring
- fdbt binary lives in `~/.local/share/cortex/<version>/fdbt` — CI needs explicit install

---

## 2026-04-04 — dbt Build Against AM_SKI_RESORT_DEV + Data Quality Fixes (Session 12)

First full dbt build against the DCM-managed `AM_SKI_RESORT_DEV` database. Required auth changes, data quality fixes, and documentation updates.

### Authentication
- dbt dev target switched from password auth to key pair auth (`private_key_path`) matching the Snowflake CLI `myconnection` config
- `~` path expansion doesn't work in Jinja templates — absolute path required: `/Users/jdemlow/.snowflake/keys/snowflake_tf_key.p8`
- QA/prod targets retain password auth for CI service accounts

### Raw Data Population
- Created zero-copy clones from `SADM_SKI_RESORT_DB.RAW` into `AM_SKI_RESORT_DEV.RAW` (24 tables, instant, no storage cost)

### Data Quality Issues Found and Fixed

**8 uniqueness test failures — duplicate IDs in raw data**
- Root cause: same records loaded twice (12/05 and 12/08) with different `created_at` timestamps
- Fix: added dedup at staging layer using `QUALIFY ROW_NUMBER() OVER (PARTITION BY <pk> ORDER BY created_at DESC) = 1`
- Applied to 8 staging models: stg_ticket_sales, stg_food_beverage, stg_rentals, stg_customer_feedback, stg_grooming_logs, stg_incidents, stg_parking_occupancy, stg_ski_lessons
- Changed 5 raw source uniqueness tests to `severity: warn` (raw data is inherently untrusted; staging enforces uniqueness after dedup)

**3 accepted_values test failures — mixed case + new enum values**
- `LOWER()` applied to sentiment (stg_customer_feedback), incident_type and severity (stg_incidents)
- Expanded accepted_values lists: added 'critical', 'major' to severity; added 'injury', 'lift_stop', 'medical_emergency', 'weather_closure' to incident_type

### Final dbt Build Results
```
PASS=193  WARN=5  ERROR=0  SKIP=0  TOTAL=198
```
- 24 staging views, 6 dims, 4 seeds, 13 incremental facts, 11 semantic views
- All 140 data tests pass (5 raw uniqueness warnings expected)

### Documentation Updates
- `docs/architecture.md`: replaced single-DB schema-isolation with multi-DB pattern, updated role/warehouse names
- `docs/data_dictionary.md`: replaced 63 `SKI_RESORT_DB.` FQN prefixes with `{DATABASE}.`
- `README.md`: updated environment strategy to multi-DB diagram

### Key Design Decision: Staging Dedup Pattern
Raw data is treated as untrusted. Dedup happens at the staging layer, not in raw. Source uniqueness tests use `severity: warn` as a signal, not a gate. Staging tests enforce uniqueness after dedup. This pattern ensures the pipeline doesn't break when upstream sources double-load data.

### Test Results
- 76/76 Python tests pass
- 193/198 dbt tests pass (5 warn)

---

## 2026-04-03 — DCM Deployment to All 3 Environments (Session 11)

Deployed DCM to DEV, QA, and PROD on a single Snowflake account. Hit and resolved several DCM constraints along the way.

### CLI Upgrade: 3.13.0 → 3.16.0
- CLI 3.13.0 had a bundling bug: `snow dcm plan` only uploaded `manifest.yml` to the temp stage, completely missing `sources/` directory
- `--debug` output confirmed only `manifest.yml` was PUT; sources never bundled
- Upgraded to 3.16.0 via pip (`pip3 install snowflake-cli==3.16.0`) — Homebrew formula was broken (missing pydantic)
- Working binary: `/Users/jdemlow/miniconda3/bin/snow`

### DCM Single-Project Ownership Constraint
- DCM enforces that every named object (database, role, warehouse) can only belong to ONE project
- On a single account, DEV/QA/PROD must use **different names** for all account-level objects
- Solution: env-suffix everything — `AM_SKI_RESORT_DEV`, `AM_DEPLOY_ROLE_DEV`, `AM_SKI_RESORT_WH_DEV`
- Since the database name provides isolation, schema suffixes are no longer needed (`SEMANTIC` not `SEMANTIC_DEV`)

### Two Deployment Patterns Documented
- **Pattern A — Cross-Account**: Same object names, different `account_identifier` per target. No suffixes needed.
- **Pattern B — Single-Account** (used here): Env-suffix all account-level objects. `infrastructure.sql` uses `{{db}}` so suffixed names flow through automatically.

### Deployment Results
| Target | Project | Database | Warehouse | Entities |
|--------|---------|----------|-----------|----------|
| DEV | DCM.AM.AM_SKI_RESORT_DEV | AM_SKI_RESORT_DEV | AM_SKI_RESORT_WH_DEV (XS) | 16 (14 created, 2 altered) |
| QA | DCM.AM.AM_SKI_RESORT_QA | AM_SKI_RESORT_QA | AM_SKI_RESORT_WH_QA (S, 1-2) | 16 (14 created, 2 altered) |
| PROD | DCM.AM.AM_SKI_RESORT | AM_SKI_RESORT_PROD | AM_SKI_RESORT_WH_PROD (M, 1-3) | 16 (14 created, 2 altered) |

### Gotchas Discovered
- `snow dcm drop` removes project registration but does NOT drop created objects — manual cleanup required
- Deploy alias must be unique per project; failed deploys consume the alias
- Orphan cleanup pattern: `DROP ROLE/WAREHOUSE/DATABASE IF EXISTS`

### CI/CD Workflow (Session 10)
- Replaced 134-line custom `dcm-deploy.yml` with Snowflake-Labs official reusable actions (`Snowflake-Labs/snowflake_dcm_projects/actions@v1`)
- 4 composite actions: `dcm-parse-manifest`, `dcm-connection-test`, `dcm-plan`, `dcm-deploy`
- PR → plan+comment, push to main → plan+deploy DEV, manual → any target

### Files Changed
- `dcm/manifest.yml` — env-suffixed db/roles/warehouse for single-account pattern
- `dcm/README.md` — comprehensive docs with both deployment patterns, gotchas, role hierarchy
- `.github/workflows/dcm-deploy.yml` — rewritten with Snowflake-Labs reusable actions

---

## 2026-04-03 — Infrastructure as Code with DCM + Database Isolation (Session 9)

Migrated from SKI_RESORT_DB to AM_SKI_RESORT (Agent Management), replacing ACCOUNTADMIN with a proper role hierarchy via DCM.

### DCM Project Structure
- `dcm/manifest.yml` — DEV/QA/PROD targets with per-environment templating
- `dcm/sources/definitions/infrastructure.sql` — database, 6 schemas, warehouse (with full config: clusters, scaling, timeouts), internal stage
- `dcm/sources/definitions/access.sql` — three-tier database role hierarchy (ANALYST -> DEVELOPER -> ADMIN), AM_DEPLOY_ROLE, warehouse user role
- `dcm/sources/macros/grants_macro.sql` — 5 reusable grant macros: `schema_read_grants`, `schema_write_grants`, `schema_ddl_grants`, `schema_agent_grants`, `schema_stage_write_grants`

### Grant Expansion (Session 9b)
Audited every workload (dbt, deploy_agents, deploy_semantic_views, data_generation, eval pipeline) and added missing grants:
- **FUTURE grants**: ANALYST gets SELECT on FUTURE TABLES/VIEWS so new dbt objects are readable immediately
- **CREATE AGENT**: ADMIN on AGENTS + SEMANTIC schemas (for deploy_agents.py)
- **CREATE SEMANTIC VIEW**: ADMIN on SEMANTIC + AGENTS schemas (for deploy_semantic_views.py + dbt)
- **CREATE CORTEX SEARCH SERVICE**: ADMIN on DOCS + AGENTS schemas (for data_generation search service)
- **CREATE FUNCTION / CREATE PROCEDURE**: ADMIN on all schemas (for UDFs and stored procs)
- **Stage READ/WRITE**: DEVELOPER on AGENTS (eval config uploads), ADMIN on AGENTS + DOCS
- Validated all grants compile via Snowflake SQL (tested CREATE AGENT, CREATE SEMANTIC VIEW, CREATE CORTEX SEARCH SERVICE, FUTURE TABLES, stage grants)

### Role Hierarchy
- `AM_DEPLOY_ROLE` replaces ACCOUNTADMIN as the CI/CD deployment role
- `AM_SKI_RESORT_WH_USER` account role for warehouse access (database roles can't hold warehouse grants)
- Three database roles: ADMIN (DDL), DEVELOPER (DML), ANALYST (read-only)
- `AM_DEPLOY_ROLE -> SYSADMIN` (proper hierarchy)

### Project Alignment
- Updated all `environments/*.env.yml` to use `AM_DEPLOY_ROLE`, `AM_SKI_RESORT_WH`, `AM_SKI_RESORT`
- Updated `dbt_ski_resort/profiles.yml` defaults to match DCM-created resources
- Updated `project.yml` defaults for role, warehouse, database
- Created `.github/workflows/dcm-deploy.yml` with plan-only and deploy modes

### Warehouse Best Practices
- DEV: XSMALL, 1 cluster, 300s suspend, 1800s timeout
- QA: SMALL, 1-2 clusters, 300s suspend, 1800s timeout
- PROD: MEDIUM, 1-3 clusters, 120s suspend, 3600s timeout

### DCM Plan Result
- 16 entities: 14 create, 2 alter, 0 drop (clean, not yet deployed)
- Project registered as `DCM.AM.AM_SKI_RESORT_DEV`

### Key Decision: project_owner stays ACCOUNTADMIN in manifest.yml
The `project_owner` field in DCM targets must be a role that can CREATE the deploy role itself. ACCOUNTADMIN bootstraps the initial deploy, then all subsequent operations use AM_DEPLOY_ROLE.

### Requirements
- Added REQ-013: Infrastructure as Code (DCM)

---

## 2026-04-03 — Dual-Path Semantic View Deployment + dbt Env-Aware Schema (Session 8)

Closed the dbt environment isolation gap for semantic views and documented dual-path SV deployment.

### dbt Environment-Aware Schema Routing
- Rewrote `dbt_ski_resort/macros/generate_schema_name.sql` to intercept `schema: semantic` and reroute to `var('semantic_schema')` (SEMANTIC_DEV, SEMANTIC_QA, or SEMANTIC)
- Added `vars: { semantic_schema: "{{ env_var('DBT_SEMANTIC_SCHEMA', 'SEMANTIC') }}" }` to `dbt_project.yml`
- All 11 semantic models in `_semantic.yml` use `config: { materialized: semantic_view, schema: semantic }` — the macro handles env routing

### CI/CD Workflow Updates
- `deploy-dev.yml`: conditional dbt step with `DBT_SEMANTIC_SCHEMA: SEMANTIC_DEV`
- `promote-qa.yml`: conditional dbt step with `DBT_SEMANTIC_SCHEMA: SEMANTIC_QA`
- `promote-prod.yml`: conditional dbt step with `DBT_SEMANTIC_SCHEMA: SEMANTIC`
- `daily_data_refresh.yml`: added `DBT_SEMANTIC_SCHEMA: SEMANTIC` to existing dbt step
- All use `if: hashFiles('dbt_ski_resort/dbt_project.yml') != ''` guard

### Documentation
- Rewrote `README.md` with full project docs: quick start, dual-path SV explanation, CLI table, env strategy, repo structure
- Added "Semantic View Dual-Path Deployment" section to `docs/architecture.md` with ASCII diagram
- Fixed Data Flow diagram (removed duplicate line, added standalone SV path)
- Updated CI/CD Pipeline Flow to show dbt build step

### Key Design: Dual-Path SV Deployment
- **Path A (dbt-native):** `dbt_semantic_view` package materialization → `generate_schema_name` macro routes to env-specific schema
- **Path B (Python CI/CD):** `deploy_semantic_views.py` → renders Jinja2 YAML templates → `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML`
- Both produce identical Snowflake objects; CI/CD runs dbt first (if present), then standalone deploys

---

## 2026-04-03 — Completeness Sprint: Packaging, Metrics, Config, dbt (Session 7)

Closed all remaining gaps to make the framework a complete, forkable tool.

### Library Packaging (REQ-012)
- Created root `pyproject.toml` (`agent-mgmt==0.5.0`) with `setuptools` build backend
- 9 CLI entry points: `agent-mgmt-deploy-agents`, `agent-mgmt-deploy-svs`, `agent-mgmt-validate`, `agent-mgmt-snapshot`, `agent-mgmt-rollback`, `agent-mgmt-metrics`, `agent-mgmt-render-eval`, `agent-mgmt-detect-drift`, `agent-mgmt-check-sv-eval`
- `pip install -e .` works; all CLI commands functional

### Eval Framework (REQ-004) — Closed Gaps
- Added `compute_classification_metrics()` to `scripts/compute_metrics.py`: F1, precision, recall per metric. Each question scored against threshold -> TP or FN.
- Created `agent-evaluation/metrics/boundary_enforcement.yaml` — first custom LLM-judge metric YAML with `{{output}}`, `{{ground_truth}}`, `{{input}}` placeholders.

### data_generation/ Hardcoded Refs — Cleaned
- Created `data_generation/config.py` — reads `project.yml` for DATABASE, WAREHOUSE, schema names
- Replaced ~30 hardcoded `SKI_RESORT_DB` and `COMPUTE_WH` refs across 7 Python files with config-driven values
- Remaining: `load_documents.sql` (43 refs, SQL file — separate scope), fallback defaults in `config.py` and `snowflake_connection.py`

### dbt Integration (REQ-007) — Closed Gaps
- Upgraded `dbt_ski_resort/profiles.yml` to multi-target (dev/qa/prod) with `DBT_TARGET` env var selection
- Added conditional dbt steps to `promote-qa.yml` and `promote-prod.yml` (`if: hashFiles(...)`)
- Deploy order enforced: dbt build -> semantic views -> agents -> eval

### Test Results
- 76/76 tests pass after all changes

---

## 2026-04-03 — REQ-011: Eval Template Rendering Pipeline (Session 6)

Built the eval template rendering pipeline so `{{ eval.* }}` Jinja2 placeholders in eval configs and datasets resolve to environment-specific values before SQL execution.

### Problem
Eval configs and datasets use `{{ eval.source_database }}`, `{{ eval.agents_schema }}`, `{{ eval.stage }}` etc. as Jinja2 placeholders. These need resolving before files can be used by `run_eval.py` or uploaded to Snowflake stages. Additionally, eval metric prompts contain `{{output}}`, `{{ground_truth}}`, `{{input}}` — these are LLM-judge placeholders that must NOT be resolved by Jinja2.

### Solution

**`scripts/render_template.py`** — Extended `build_context()` to include an `eval` namespace alongside `env`:
- `eval.source_database` → from `project.yml` eval section (e.g., `SADM_SKI_RESORT_DB`)
- `eval.agents_schema` → source schema name only (e.g., `AGENTS`), NOT the deployment schema
- `eval.stage` → FQN using source database + source schema (e.g., `SADM_SKI_RESORT_DB.AGENTS.eval_config_stage`)
- `eval.run_date` → dynamic, defaults to today, overridable via `--run-date`

**`scripts/render_eval_templates.py`** — New CLI tool:
- Finds all eval YAML files in `agent-evaluation/` (configs, datasets, root)
- Resolves `{{ eval.* }}` and `{{ env.* }}` placeholders
- Uses `_PreserveUndefined(jinja2.Undefined)` class that renders unknown vars back as `{{ varname }}` — preserves LLM-judge prompt placeholders
- Outputs rendered files to `agent-evaluation/generated/{env}/`
- Supports `--dry-run`, `--file`, `--run-date` flags

### Bug Fix: eval.stage resolved to wrong schema
`get_eval_config()` in `config.py` used `config["deployment"]["agents_schema"]` (the deployment target, e.g., `AGENTS_DEV`) to build stage/file_format FQNs. But eval objects live in the eval source database's `AGENTS` schema. Fixed to read from `project.yml`'s `eval.source_schemas.agents` instead.

### Test Coverage
Added `TestEvalRendering` class to `test_smoke.py` — 12 new tests:
- `build_context` includes eval namespace with correct keys
- `eval.source_database` matches `get_eval_source_database()`
- `eval.agents_schema` is source (`AGENTS`), not deployment (`AGENTS_DEV`)
- `eval.stage` uses source schema, not deployment schema
- Context consistent across dev/qa/prod environments
- `run_date` override works
- Template rendering produces correct FQNs
- `_PreserveUndefined` passes through `{{output}}`, `{{ground_truth}}` untouched
- `_PreserveUndefined` works alongside resolved `{{ eval.* }}` vars
- `find_eval_files` discovers all eval YAML files

### Results
- 5/5 eval files rendered for dev environment (0 failures)
- 76 tests total: **76 PASS** (64 existing + 12 new eval rendering tests)

---

## 2026-04-02 — Session 5: Dev Environment Deployment

Deployed all 11 semantic views to `SKI_RESORT_DB.SEMANTIC_DEV` and both agents to `SKI_RESORT_DB.AGENTS_DEV`. Full dev environment now operational with schema isolation.

### Deployed Objects
- **11 Semantic Views** in `SEMANTIC_DEV`: SEM_CUSTOMER_BEHAVIOR, SEM_CUSTOMER_SATISFACTION, SEM_DAILY_SUMMARY, SEM_LESSONS_ANALYTICS, SEM_MARKETING_ANALYTICS, SEM_OPERATIONS, SEM_PASSHOLDER_ANALYTICS, SEM_REVENUE, SEM_SAFETY_INCIDENTS, SEM_STAFFING_ANALYTICS, SEM_WEATHER_ANALYTICS
- **2 Agents** in `AGENTS_DEV`: RESORT_EXECUTIVE (11 tools), SKI_OPS_ASSISTANT (4 tools)

---

## 2026-04-02 — REQ-010: Library Config & Hardcoded Reference Elimination (Session 4)

Addressed the biggest reusability blocker: hardcoded database names scattered throughout the codebase.

### Problem
Hardcoded references to `SKI_RESORT_DB`, `SADM_SKI_RESORT_DB`, `COMPUTE_WH` etc. in tests, eval datasets, eval configs, and CI workflows prevented anyone from forking the repo and using it with their own Snowflake objects.

### Audit Results (before fix)
| File/Area | Hardcoded Refs | Status |
|-----------|---------------|--------|
| `scripts/*.py` | 0 | Already clean (config-driven) |
| `tests/test_smoke.py` | 17 | Fixed: reads from project.yml |
| `tests/test_templates.py` | 9 | Fixed: reads from project.yml |
| `agent-evaluation/datasets/resort_executive_eval.yaml` | 125 | Fixed: `{{ eval.source_database }}` |
| `agent-evaluation/datasets/ski_ops_assistant_eval.yaml` | 87 | Fixed: `{{ eval.source_database }}` |
| `agent-evaluation/configs/resort_executive.yaml` | 7 | Fixed: Jinja2 placeholders |
| `agent-evaluation/resort_executive_eval_config.yaml` | 7 | Fixed: Jinja2 placeholders |
| `.github/workflows/daily_data_refresh.yml` | 35 | Fixed: reads from project.yml at runtime |
| snapshots/generated/ | many | Expected (point-in-time captures) |
| docs/ | some | Expected (documentation examples) |

### Solution: `project.yml`
Created a single project-level config at repo root that defines all domain-specific names:
- `environments.{dev,qa,prod}.database` — deployment target databases
- `eval.source_database` — database for eval validation queries
- `defaults.schemas` — RAW, STAGING, MARTS, SEMANTIC, AGENTS
- `raw_tables` — list of raw table names for data refresh workflow
- `defaults.snowflake` — warehouse, role, account

### Changes
1. **`project.yml`** — NEW: Single source of truth for all names
2. **`scripts/utils/config.py`** — Added: `get_expected_databases()`, `get_eval_source_database()`, `get_eval_config()`, `get_raw_tables()`, `get_project_schemas()`
3. **`tests/test_smoke.py`** — Replaced EXPECTED_DBS dict with `get_expected_databases()` call
4. **`tests/test_templates.py`** — Same; also replaced hardcoded `SADM_SKI_RESORT_DB` assertion with `get_eval_source_database()`
5. **`agent-evaluation/configs/resort_executive.yaml`** — Templatized with `{{ eval.* }}` placeholders
6. **`agent-evaluation/datasets/*.yaml`** — Global replace of SADM_SKI_RESORT_DB → `{{ eval.source_database }}`
7. **`.github/workflows/daily_data_refresh.yml`** — Added "Load Project Config" step; all SQL uses `${DB}.${SCHEMA}.TABLE` env vars
8. **`requirements/REQ-010_library_config.md`** — NEW: Full requirement doc

---

## 2026-04-02 — Gap Fixes and Full Audit (Session 3c)

Closed remaining gaps from the Phase 3 local testing audit:

### SV Template Coverage: 4/11 → 11/11
- Created 7 missing Jinja2 SV templates from prod snapshots: sem_customer_behavior, sem_customer_satisfaction, sem_lessons_analytics, sem_marketing_analytics, sem_passholder_analytics, sem_safety_incidents, sem_weather_analytics
- All 11 templates replace `database: SKI_RESORT_DB` with `{{ env.database }}`; also templatized FQN references in `module_custom_instructions`
- `validate_specs --env prod` → 11/11 VALID
- pytest expanded from 43 to 64 tests (11 SVs × 3 envs = 33 SV template tests)

### Eval Dataset: ski_ops_assistant
- Created `agent-evaluation/datasets/ski_ops_assistant_eval.yaml` with 11 golden questions
- Covers all 4 tools: LiftOperationsAnalytics (3), StaffingAnalytics (2), WeatherAnalytics (2), SafetyIncidentsAnalytics (2), cross-domain (1), plus weekend vs weekday comparison
- All questions use dynamic ground truth (validation_query + answer_template pattern)

### Tested and Verified
- **TC-010** (single-view deploy): `--view sem_operations` correctly scoped to 1 view
- **TC-028** (full rollback cycle): snapshot → rollback to earlier timestamp → restore back — 0 failures across round-trip
- **TC-019** (ski_ops eval dataset): PASS — 11 questions with validation_query

### Updated Scorecard
- 50 test cases: **33 PASS**, 0 FAIL, 5 BLOCKED, 12 NOT RUN
- Previous: 28 PASS, 1 FAIL, 5 BLOCKED, 16 NOT RUN
- Closed: TC-005 (expanded), TC-007 (expanded), TC-008 (expanded), TC-010, TC-019, TC-028

### Remaining Gaps
- TC-012: Drift detection with manual edit (manual test — low priority)
- TC-017: Deploy order enforcement (not implemented — agents deploy fine if SVs exist)
- TC-020/021: run_eval.py end-to-end (eval runner exists but not tested in CI context)
- TC-025: Custom metrics in eval output (needs eval run)
- TC-031-035: actionlint validation (not installed)
- TC-036-039: Live GitHub Actions triggers (requires pushing to GitHub)
- TC-042-046: dbt/data generation scope (separate pipeline)
- TC-047-049: SV eval (GET_ANALYST_AI_EVALUATION_DATA not on account)

---

## 2026-04-02 — Phase 3: GitHub Actions CI/CD Workflows (Session 3b)

Built and locally simulated all 5 CI/CD GitHub Actions workflows:

### Workflows Created
1. **validate-pr.yml** — PR to main: lint+unit (43 tests) → validate specs (3 envs) → Snowflake dry-run (SV + agent + drift)
2. **deploy-dev.yml** — On merge/manual: snapshot → deploy SVs → SV eval gate → deploy agents → agent eval
3. **promote-qa.yml** — Manual: pre-flight → snapshot → deploy → eval gate (strict)
4. **promote-prod.yml** — Manual + approval: pre-flight → snapshot → deploy → eval gate → auto-rollback on failure
5. **rollback.yml** — Manual: list snapshots or rollback by timestamp with target filtering

### Key Patterns
- Key-pair auth via SNOWFLAKE_PRIVATE_KEY secret → /tmp/snowflake_key.p8 (cleaned up in `if: always()`)
- PYTHONPATH set to `${{ github.workspace }}` for module imports
- Snapshot timestamp passed between jobs via `needs.snapshot.outputs.snapshot_timestamp`
- `environment: production` requires manual approval for prod deployments
- Artifact retention: dev=30d, qa=90d, prod=365d

### Bugs Fixed During Testing
1. `snapshot_state.py`: `'20260402_162031'::TIMESTAMP_NTZ` → `TO_TIMESTAMP(..., 'YYYYMMDD_HH24MISS')` — Snowflake can't auto-parse custom timestamp format
2. `snapshot_state.py`: f-string SQL interpolation → parameterized `%s` bind queries — JSON with single quotes broke SQL literals
3. `test_smoke.py` + `test_templates.py`: script-style (print+assert) → proper pytest classes with `@pytest.mark.parametrize` — pytest collected 0 items before this fix

### Local Simulation Results
- pytest: 43/43 PASS → validate_specs: 3/3 envs PASS → SV dry-run: 4/4 PASS → agent dry-run: 2/2 PASS → drift: NO DRIFT
- snapshot: 14 objects to CI_CD_SNAPSHOTS table → deploy SVs: 4/4 → deploy agents: 2/2 → compute_metrics: dev PASS (0.668 ≥ 0.6), prod FAIL (0.668 < 0.8)
- rollback: --list (5 timestamps) → --dry-run (14 objects) → --target agents (3 objects)

---

## 2026-04-02 — Integration of Existing Components

Added three major directories that map directly to framework requirements:

- **`agent-evaluation/`** → REQ-004 (Eval Framework)
  - `run_eval.py` (775 lines): end-to-end eval runner with dynamic ground truth, threshold gating, CI exit codes
  - 15 golden questions for RESORT_EXECUTIVE with `validation_query` + `answer_template`
  - Latest results: 92.4% answer_correctness, 87.2% logical_consistency (v3 run)
  - Remaining work: `compute_metrics.py` (F1/precision/recall), integration with env config, ski_ops eval dataset

- **`data_generation/`** → REQ-008 (new requirement)
  - Synthetic ski resort data: 8000 customers, 21 tables, 5 seasons (Nov 2020 - present)
  - `generate_daily_increment.py`: idempotent daily append with smart backfill
  - `generate_documents.py`: 14 unstructured docs for Cortex Search
  - Seed: RNG=42 for reproducibility

- **`dbt_ski_resort/`** → REQ-007 (dbt Integration — no longer placeholder)
  - Kimball model: 23 staging views, 6 dimensions, 13 incremental facts, 11 semantic views
  - Uses `dbt_semantic_view` package (Snowflake-Labs) for SV materialization
  - Profile: SKI_RESORT_DB, MARTS schema, COMPUTE_WH
  - Has been fully built (target/ and logs/ present)

- **`.github/workflows/daily_data_refresh.yml`** → REQ-006 (partial)
  - Daily 5am PST cron: integrity check -> smart backfill -> data gen -> dbt facts -> dbt semantic -> verify
  - Recovery options: rebuild_from_date, full_refresh, clear_raw_data
  - Uses snowflakedb/snowflake-cli-action@v1.5

### Key Architectural Decision

Two complementary pipelines share the same Snowflake objects:
1. **Data pipeline** (daily_data_refresh.yml): keeps data current — data_gen -> dbt -> verify
2. **CI/CD pipeline** (to be built): promotes spec changes — validate -> deploy SVs -> deploy agents -> eval gate

They are independent: CI/CD does NOT re-run dbt. It assumes base tables are current.

### Diagram Format Decision

Switched from Mermaid to ASCII box-and-arrow diagrams in architecture.md for readability in terminal/code review contexts.

---

## 2026-04-02 — Project Kickoff

- Initialized Cortex Agent CI/CD Reference Framework from blank template
- **Domain**: Ski resort (SKI_RESORT_DB) — leverages existing data, agents, and eval framework
- **Scope**: 2 agents (Resort Executive, Ski Ops Assistant), 4 semantic views (SEM_DAILY_SUMMARY, SEM_REVENUE, SEM_OPERATIONS, SEM_STAFFING_ANALYTICS)
- **Architecture**: config-as-code with Jinja2 env parameterization, GitHub Actions CI/CD, eval-gated promotions
- **Code quality standards**: Hybrid fast.ai (Jeremy Howard) + Snowflake best practices
- **Source material**: Adapted from SnowflakeAgentDevelopmentManagement repo (agent specs, semantic views, eval framework, GHA workflows)
- **Key decisions**:
  - Copy eval framework into repo (not submodule) for self-contained reference
  - Default environment isolation: separate databases (SKI_RESORT_DB with _DEV/_QA suffixes)
  - COPY INTO for stage uploads (not PUT) — critical lesson from eval framework development
  - `source_metadata.type` must be lowercase `"dataset"` in eval YAML
  - `agent_name` must be fully qualified in eval configs

### Requirements Created
- REQ-001: Environment Configuration System
- REQ-002: Semantic View CI/CD Pipeline
- REQ-003: Agent CI/CD Pipeline
- REQ-004: Evaluation Framework with Gate
- REQ-005: Snapshot and Rollback
- REQ-006: GitHub Actions Workflows
- REQ-007: dbt Integration Points
- REQ-008: Data Generation Pipeline (added post-integration)

### User Stories
- 23 user stories across all 8 requirements
- 46 test cases defined

---

<!-- Add new entries above this line. Format: ## [YYYY-MM-DD] — [Topic] -->
