# Architecture

## Overview

The Cortex Agent CI/CD Reference Framework provides a production-quality, end-to-end pipeline for managing Snowflake Cortex Agents and Semantic Views as code. It defines agents and semantic views as YAML in Git, deploys them through environment-parameterized GitHub Actions workflows, evaluates agent quality with golden question sets and custom metrics, and provides snapshot-based rollback when changes break production. The ski resort domain (2 agents, 4 semantic views, 11 in full deployment) demonstrates patterns that scale to any number of agents and views.

## Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Data Warehouse | Snowflake | AM_SKI_RESORT_{DEV|QA|PROD} (RAW, STAGING, MARTS, SEMANTIC, AGENTS, DBT_TEST__AUDIT schemas) |
| Data Generation | Python (Snowpark) | `data_generation/` — synthetic ski resort data for 12 RAW tables |
| Data Transform | dbt (dbt-snowflake) | `dbt_ski_resort/` — 23 staging, 6 dims, 13 facts, 11 semantic views |
| Semantic Layer | Cortex Semantic Views | YAML-defined, deployed via SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML |
| AI Agents | Cortex Agents | YAML-defined, deployed via ALTER AGENT (existing) or CREATE AGENT (new) |
| Evaluation | Cortex Agent Evaluations | `agent-evaluation/` — EXECUTE_AI_EVALUATION + custom LLM-judge metrics |
| CI/CD | GitHub Actions | Data pipeline (daily_data_refresh.yml) + promotion workflows |
| Config | YAML + Jinja2 | `project.yml` (project-wide) + `environments/*.env.yml` (per-env) |
| Language | Python 3.11+ | Deploy, eval, snapshot, rollback scripts |
| Infrastructure | DCM (Database Change Management) | `dcm/` — declarative database, warehouse, roles, grants |
| Auth (CI) | Key-pair (RSA) | GitHub environment secrets (4 repo-level + 3 per env), no passwords in pipelines |

## Repository Structure

```
AgentMangement/
  +-- project.yml                    <-- Single source of truth for all names (REQ-010)
  +-- pyproject.toml                 <-- pip-installable package config (agent-mgmt 0.5.0)
  +-- agents/                       <-- Agent spec templates (Jinja2 YAML)
  |   +-- specs/
  |   |   +-- resort_executive.yml
  |   |   +-- ski_ops_assistant.yml
  |
  +-- semantic-views/               <-- SV definition templates (Jinja2 YAML)
  |   +-- definitions/              <-- 11 templates (all SVs templatized)
  |   |   +-- sem_customer_behavior.yaml
  |   |   +-- sem_customer_satisfaction.yaml
  |   |   +-- sem_daily_summary.yaml
  |   |   +-- sem_lessons_analytics.yaml
  |   |   +-- sem_marketing_analytics.yaml
  |   |   +-- sem_operations.yaml
  |   |   +-- sem_passholder_analytics.yaml
  |   |   +-- sem_revenue.yaml
  |   |   +-- sem_safety_incidents.yaml
  |   |   +-- sem_staffing_analytics.yaml
  |   |   +-- sem_weather_analytics.yaml
  |   +-- snapshots/                <-- Timestamped SV snapshots for rollback
  |
  +-- environments/                 <-- Per-env config (database, schema, warehouse)
  |   +-- dev.env.yml
  |   +-- qa.env.yml
  |   +-- prod.env.yml
  |
  +-- agent_management/              <-- Core Python library (pip-installable)
  |   +-- deploy_semantic_views.py  <-- CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML
  |   +-- deploy_agents.py          <-- ALTER AGENT (existing) / CREATE AGENT (new)
  |   +-- snapshot_state.py         <-- Captures to local files + CI_CD_SNAPSHOTS table
  |   +-- rollback.py               <-- Timestamp-based, target-filtered restore
  |   +-- compute_metrics.py        <-- F1/precision/recall with threshold gating
  |   +-- check_sv_eval.py          <-- SV eval gate (REQ-009)
  |   +-- validate_specs.py         <-- YAML structure + Snowflake dry-run
  |   +-- render_template.py        <-- Jinja2 env + eval substitution
  |   +-- render_eval_templates.py <-- CLI for rendering eval configs/datasets
  |   +-- detect_drift.py           <-- Git vs Snowflake diff
  |   +-- ci/                       <-- CI checks (test coverage, PK tests, lineage)
  |   +-- utils/
  |       +-- config.py             <-- Config loading, FQN helpers, suffix resolution
  |       +-- snowflake_client.py
  |
  +-- agent-evaluation/             <-- Eval framework (EXISTS)
  |   +-- scripts/run_eval.py
  |   +-- configs/resort_executive.yaml
  |   +-- datasets/
  |   |   +-- resort_executive_eval.yaml   (15 golden questions)
  |   |   +-- ski_ops_assistant_eval.yaml  (11 golden questions)
  |   +-- metrics/                    <-- Custom LLM-judge metric YAMLs
  |   |   +-- boundary_enforcement.yaml
  |   +-- generated/                 <-- Rendered eval files per env (REQ-011)
  |   |   +-- dev/
  |   |   +-- qa/
  |   |   +-- prod/
  |   +-- results/
  |
  +-- data_generation/              <-- Synthetic data gen (EXISTS)
  |   +-- config.py                 <-- Reads project.yml for DB/warehouse names
  |   +-- generate_complete_ski_data.py
  |   +-- generate_daily_increment.py
  |   +-- shared.py
  |
  +-- dbt_ski_resort/               <-- dbt project (EXISTS)
  |   +-- models/staging/
  |   +-- models/marts/dimensions/
  |   +-- models/marts/facts/
  |   +-- models/marts/semantic/
  |
  +-- dcm/                          <-- Infrastructure as Code (DCM)
  |   +-- manifest.yml              <-- Project manifest with DEV/QA/PROD targets
  |   +-- sources/
  |   |   +-- definitions/
  |   |   |   +-- infrastructure.sql <-- Database, schemas, warehouse, stage
  |   |   |   +-- access.sql        <-- Roles, grants, user assignments
  |   |   +-- macros/
  |   |       +-- grants_macro.sql   <-- Reusable grant macros
  |   +-- post_deploy.sql           <-- Reserved for non-DEFINE objects
  |
  +-- .github/workflows/            <-- CI/CD pipelines
  |   +-- daily_data_refresh.yml    (environment: PROD)
  |   +-- dcm-deploy.yml            <-- DCM infrastructure deploy
  |   +-- validate-pr.yml
  |   +-- deploy-dev.yml            (environment: DEV)
  |   +-- promote-qa.yml            (environment: QA)
  |   +-- promote-prod.yml          (environment: PROD)
  |   +-- rollback.yml
  +-- .github/scripts/              <-- CI/CD helper scripts
  |   +-- setup_github_secrets.sh   (repo + env-level secrets)
  |   +-- setup_github_environments.sh
  |   +-- teardown.sh
  |   +-- test_workflow_locally.sh  (local workflow testing)
  +-- .github/PIPELINE_SETUP.md     <-- Full pipeline setup guide
  |
  +-- docs/                         <-- Architecture, data dictionary, dev notes
  +-- models/                       <-- Data model documentation
  +-- requirements/                 <-- Traceable requirements (REQ-001..011)
  +-- tests/                        <-- Test cases linked to requirements
```

## Configuration Architecture (REQ-010)

All domain-specific names are centralized in `project.yml`. Per-environment overrides live in `environments/{env}.env.yml`. No hardcoded database names exist in scripts, tests, eval datasets, or CI workflows.

```
project.yml (repo root)
  |
  +-- environments/dev.env.yml     project.yml defines:
  +-- environments/qa.env.yml      - environments.{dev,qa,prod}.database
  +-- environments/prod.env.yml    - deployment.mode (single_account / cross_account)
  |                                - deployment.data_source (prod = source of truth)
  |                                - defaults.schemas (RAW, STAGING, MARTS, ...)
  +-- agent_management/utils/config.py
        |                          - raw_tables (for data refresh workflow)
        |                          - defaults.snowflake (warehouse, role)
        +-- load_env_config(env)        --> per-env deployment config
        +-- get_expected_databases()    --> {"dev":"...", "qa":"...", "prod":"..."}
        +-- get_agent_fqn(config, name) --> DB.SCHEMA.AGENT_NAME{_SUFFIX}
        +-- get_deployment_mode()       --> "single_account" or "cross_account"
        +-- get_data_source_env()       --> "prod" (source of truth for clones)
        +-- get_eval_config(config)     --> stage, file_format, warehouse FQNs
        +-- get_raw_tables()            --> list of raw table names
```

To reuse the framework for a different domain:
1. Edit `project.yml` — change database names, schemas, raw tables
2. Edit `environments/*.env.yml` — change deployment targets
3. Write new agent specs in `agents/specs/` and SV definitions in `semantic-views/definitions/`
4. Create eval datasets in `agent-evaluation/datasets/`

## Two Complementary Pipelines

This framework has two independent pipelines that share the same Snowflake objects:

```
  DATA PIPELINE (keeps data current)          CI/CD PIPELINE (promotes spec changes)
  ===================================         ====================================

  Trigger: Daily cron (5am PST)               Trigger: PR / merge / manual
  or manual with recovery options              with environment selection
        |                                            |
        v                                            v
  +-------------------+                        +-------------------+
  | Check Integrity   |                        | Validate Specs    |
  | (gap detection,   |                        | (lint YAML,       |
  |  coverage stats)  |                        |  dry-run deploy)  |
  +--------+----------+                        +--------+----------+
           |                                            |
           v                                            v
  +-------------------+                        +-------------------+
  | Generate Data     |                        | Deploy SVs        |
  | (data_generation/ |                        | (SYSTEM$CREATE_   |
  |  daily increment) |                        |  SEMANTIC_VIEW_   |
  +--------+----------+                        |  FROM_YAML)       |
  |                                             | Or dbt semantic   |
  |                                             |  materialization  |
           |                                   +--------+----------+
           v                                            |
  +-------------------+                                 v
  | dbt run facts     |                        +-------------------+
  | (dbt_ski_resort/  |                        | SV Eval Gate      |
  |  incremental)     |                        | (check_sv_eval.py |
  +--------+----------+                        |  SQL correctness) |
           |                                   +--------+----------+
           v                                            |
  +-------------------+                          +------+------+
  | dbt run semantic  |                          |             |
  | (dbt_ski_resort/  |                        Pass          Fail --> Block
  |  materialization) |                          |
  +--------+----------+                          v
           |                                   +-------------------+
           v                                   | Deploy Agents     |
  +-------------------+                        | (ALTER AGENT if   |
  | Verify            |                        |  exists, else     |
  | (record counts,   |                        |  CREATE AGENT)    |
  |  freshness check) |                        +--------+----------+
  +-------------------+                                 |
                                                        v
                                               +-------------------+
                                               | Agent Eval Gate   |
                                               | (EXECUTE_AI_      |
                                               |  EVALUATION)      |
                                               +--------+----------+
                                                        |
                                                  +-----+------+
                                                  |            |
                                                Pass         Fail
                                                  |            |
                                                  v            v
                                            +----------+ +-----------+
                                            | Promote  | | Rollback  |
                                            | to next  | | from      |
                                            | env      | | snapshot  |
                                            +----------+ +-----------+
```

**Why two pipelines?**
- The **data pipeline** ensures base tables (RAW -> STAGING -> MARTS -> SEMANTIC) have fresh, correct data every day
- The **CI/CD pipeline** ensures agent/SV spec changes are validated and promoted safely across dev -> QA -> prod
- They share the same target objects but are triggered independently
- The CI/CD pipeline optionally runs dbt (if `dbt_ski_resort/dbt_project.yml` exists) to ensure base tables are current before deploying SVs and agents

## Data Flow

```
  +------------------+      +------------------+      +--------------------+
  | Git Repository   |      | GitHub Actions   |      | Snowflake          |
  |                  |      |                  |      |                    |
  | data_generation/ +----->+ generate_daily   +----->+ RAW: 12 tables     |
  |                  |      | _increment.py    |      |                    |
  | dbt_ski_resort/  +----->+ dbt run          +----->+ STAGING: 23 views  |
  |  models/staging  |      |                  |      | MARTS: 6 dims      |
  |  models/facts    |      |                  |      | MARTS: 13 facts    |
  |  models/semantic |      |                  |      | SEMANTIC: 11 SVs   |
  |                  |      |                  |      |                    |
  | SV YAML (alt)   +----->+ deploy_semantic  +----->+ SEMANTIC: 11 SVs   |
  |  definitions/    |      | _views.py        |      | (standalone path)  |
  |                  |      |                  |      |                    |
  | Agent YAML      +----->+ deploy_agents.py +----->+ AGENTS: 2+ agents  |
  |  specs/          |      |                  |      |                    |
  |                  |      |                  |      |                    |
  | Eval datasets   +----->+ run_eval.py      +----->+ Eval results       |
  |  datasets/       |      | compute_metrics  |      |                    |
  +------------------+      +------------------+      +--------------------+
```

## CI/CD Pipeline Flow

```
  PR to main             Merge to main          Manual Trigger          Manual + Approval
       |                       |                      |                        |
       v                       v                      v                        v
  +-----------+         +-------------+        +--------------+        +----------------+
  | VALIDATE  |         | DEPLOY DEV  |        | PROMOTE QA   |        | PROMOTE PROD   |
  |           |         |             |        |              |        |                |
  | Lint YAML |         | Snapshot    |        | Snapshot     |        | Snapshot       |
  | Dry-run   |         | dbt run*    |        | dbt run*     |        | dbt run*       |
  | dbt check |         | Deploy SVs  |        | Deploy SVs   |        | Deploy SVs     |
  +-----------+         | SV Eval     |        | SV Eval Gate |        | SV Eval Gate   |
  +-----------+         | Deploy Agts |        | Deploy Agents|        | Deploy Agents  |
                        | Eval (warn) |        | Agent Eval   |        | Agent Eval     |
                        +-------------+        |  |      |    |        |  |       |     |
                                               | Pass  Fail   |        | Pass   Fail    |
                                               |  |      |    |        |  |       |     |
                                               | Done  Block  |        | Done  Rollback |
                                               +--------------+        +----------------+
```

**`*` dbt run, not dbt build:** Deploy workflows use `dbt run` because the deploy role cannot create the `DBT_TEST__AUDIT` schema required by `dbt build` (which stores test failures). After DCM deploys that schema, `dbt build` becomes viable. The `+` prefix in `--select "+marts.facts"` builds all upstream staging dependencies first.

## GitHub Environment Secrets

Secrets are split between repo-level (shared) and environment-level (per DEV/QA/PROD). Each workflow job declares `environment: DEV` (or QA/PROD), and `${{ secrets.SNOWFLAKE_DATABASE }}` resolves to the correct value for that environment.

```
  Repo-Level Secrets (4)                  Environment-Level Secrets (3 per env)
  ======================                  =====================================

  SNOWFLAKE_ACCOUNT   (trb65519)          DEV:
  SNOWFLAKE_USER      (JDEMLOW)             SNOWFLAKE_WAREHOUSE  (AM_SKI_RESORT_WH_DEV)
  SNOWFLAKE_PRIVATE_KEY                     SNOWFLAKE_ROLE       (AM_DEPLOY_ROLE_DEV)
  SNOWFLAKE_PRIVATE_KEY_RAW                 SNOWFLAKE_DATABASE   (AM_SKI_RESORT_DEV)

                                          QA:
                                            SNOWFLAKE_WAREHOUSE  (AM_SKI_RESORT_WH_QA)
                                            SNOWFLAKE_ROLE       (AM_DEPLOY_ROLE_QA)
                                            SNOWFLAKE_DATABASE   (AM_SKI_RESORT_QA)

                                          PROD / production:
                                            SNOWFLAKE_WAREHOUSE  (AM_SKI_RESORT_WH_PROD)
                                            SNOWFLAKE_ROLE       (AM_DEPLOY_ROLE_PROD)
                                            SNOWFLAKE_DATABASE   (AM_SKI_RESORT_PROD)
```

Setup: `.github/scripts/setup_github_secrets.sh` · Teardown: `.github/scripts/teardown.sh`

## Agent Lifecycle

```
  Define YAML       PR Review       Merge to main     Render for env      Deploy
  agents/specs/        |                 |             (Jinja2)              |
       |               |                 |                |                  |
       v               v                 v                v                  v
  +---------+    +-----------+    +------------+    +------------+    +-------------+
  | Author  +--->+ Validate  +--->+ Merge to   +--->+ Render for +--->+ ALTER AGENT |
  | agent   |    | lint +    |    | main       |    | target env |    | if exists   |
  | YAML    |    | dry-run   |    |            |    | (dev/qa/   |    | else CREATE |
  +---------+    +-----------+    +------------+    | prod)      |    | AGENT       |
                                                    +------------+    +------+------+
                                                                             |
       +---------------------------------------------------------------------+
       |
       v
  +------------+    +------------+    +------------+    +------------+
  | Evaluate   +--->+ Promote    +--->+ Evaluate   +--->+ Promote    |
  | in dev     |    | to QA      |    | in QA      |    | to prod    |
  | (warn)     |    |            |    | (gate)     |    |            |
  +------------+    +------------+    +-----+------+    +-----+------+
                                            |                 |
                                      +-----+------+   +-----+------+
                                      |            |   |            |
                                    Pass         Fail Pass        Fail
                                      |            |   |            |
                                      v            v   v            v
                                    Done        Block Live      Rollback
                                                              from snapshot
```

## Evaluation Pipeline

```
  INPUTS                          EXECUTION                        RESULTS
  ======                          =========                        =======

  +-------------------+     +---------------------+     +---------------------+
  | Golden Questions  +---->+ Resolve Dynamic     +---->+ Per-Question        |
  | datasets/*.yaml   |     | Ground Truth        |     | Scores              |
  | (15 per agent)    |     | (run SQL queries,   |     | (correctness,       |
  +-------------------+     |  format answers)    |     |  consistency)       |
                            +----------+----------+     +----------+----------+
  +-------------------+                |                            |
  | Custom Metrics    |                v                            v
  | metrics/*.yaml    |     +---------------------+     +---------------------+
  | (relevance,       +---->+ Upload to Stage     |     | Compute             |
  |  faithfulness,    |     | (COPY INTO, not PUT)|     | F1 / Precision /    |
  |  boundary)        |     +----------+----------+     | Recall              |
  +-------------------+                |                | (score >= threshold  |
                                       v                |  = TP, else FN)     |
  +-------------------+     +---------------------+     +----------+----------+
  | Thresholds        |     | EXECUTE_AI_         |                |
  | thresholds.yml    |     | EVALUATION('START') |                v
  | (min scores per   +---->+ Poll until complete +---->+---------------------+
  |  metric)          |     +---------------------+     | Check Thresholds    |
  +-------------------+                                 | Exit 0=Pass 1=Fail  |
                                                        +---------------------+
```

## Eval Template Rendering (REQ-011)

Eval configs and datasets use Jinja2 placeholders (`{{ eval.* }}`) that must be resolved before
execution. The rendering pipeline handles this while preserving LLM-judge prompt placeholders.

```
  SOURCE TEMPLATES                     RENDER                          GENERATED OUTPUT
  ================                     ======                          ================

  agent-evaluation/                    scripts/                        agent-evaluation/
  +-- configs/                         render_eval_templates.py        generated/{env}/
  |   +-- resort_executive.yaml        |                               +-- configs/
  |   +-- resort_executive_            | 1. load_env_config(env)       |   +-- resort_executive.yaml
  |       eval_config.yaml             | 2. build_context(config)      |   +-- resort_executive_
  +-- datasets/                        |    -> env.* namespace         |       eval_config.yaml
  |   +-- resort_executive_eval.yaml   |    -> eval.* namespace        +-- datasets/
  |   +-- ski_ops_assistant_eval.yaml  | 3. Jinja2 render with         |   +-- resort_executive_eval.yaml
  +-- resort_executive_eval_config.yaml|    _PreserveUndefined         |   +-- ski_ops_assistant_eval.yaml
                                       | 4. Write to generated/       +-- resort_executive_eval_config.yaml
                                       +--+---+---+---+
                                          |   |   |   |
                                          v   v   v   v
                                    {{ eval.source_database }} -> SADM_SKI_RESORT_DB
                                    {{ eval.agents_schema }}   -> AGENTS
                                    {{ eval.stage }}           -> SADM_SKI_RESORT_DB.AGENTS.eval_config_stage
                                    {{ eval.run_date }}        -> 20260403 (or override)
                                    {{ output }}               -> {{ output }}  (preserved)
                                    {{ ground_truth }}         -> {{ ground_truth }}  (preserved)
```

**Key design: `_PreserveUndefined`** — Custom Jinja2 `Undefined` subclass that renders unknown
variables back as `{{ varname }}` instead of raising errors or rendering empty. This is critical
because eval metric prompts contain `{{output}}`, `{{ground_truth}}`, `{{input}}` which are
LLM-judge placeholders, not Jinja2 variables.

## Semantic View Dual-Path Deployment

Two parallel paths for deploying semantic views — choose one or both per project:

```
  PATH A: dbt-native                          PATH B: Python CI/CD (standalone)
  ====================                        =================================

  dbt_ski_resort/                             semantic-views/
  models/marts/semantic/                      definitions/
  +-- sem_revenue.sql                         +-- sem_revenue.yaml
  +-- _semantic.yml                           +-- sem_customer_behavior.yaml
      (materialized: semantic_view)               (Jinja2 templates, {{ env.* }})

       |                                            |
       v                                            v
  dbt run --target dev                        scripts/deploy_semantic_views.py
  --select "marts.semantic"                   --env dev
  (reads environments/dev.env.yml)
       |                                            |
       v                                            v
  dbt_semantic_view materialization            CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML(...)
  calls SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML
       |                                            |
       v                                            v
  AM_SKI_RESORT_DEV.SEMANTIC.SEM_REVENUE      AM_SKI_RESORT_DEV.SEMANTIC.SEM_REVENUE
```

**Path A (dbt-native)** uses the `dbt_semantic_view` package (Snowflake-Labs). Models
have `materialized: semantic_view` and `schema: semantic` in `_semantic.yml`. Each dbt
target (dev/qa/prod) points at the corresponding environment database, and the
`generate_schema_name` macro passes through `custom_schema_name` as-is:

```
  generate_schema_name.sql:
    -> returns custom_schema_name directly (e.g. SEMANTIC, STAGING, MARTS)

  Environment isolation is at the database level:
    dev  target -> AM_SKI_RESORT_DEV.SEMANTIC
    qa   target -> AM_SKI_RESORT_QA.SEMANTIC
    prod target -> AM_SKI_RESORT_PROD.SEMANTIC
```

**Path B (Python CI/CD)** uses `deploy_semantic_views.py` which renders Jinja2 YAML
templates from `semantic-views/definitions/`, substituting `{{ env.database }}`,
`{{ env.semantic_schema }}` etc., then calls `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML`.
Schema routing comes from `environments/<env>.env.yml`.

**When to use which:**
- Path A: When you already have a dbt project managing your data models — SVs live alongside
  the dimension/fact models they reference, and dbt handles the full DAG.
- Path B: When SVs are managed independently of dbt, or when non-dbt teams own SVs, or when
  you need finer-grained control over the deployment script.
- Both paths produce identical Snowflake objects and can coexist. The CI/CD workflows run
  dbt first (if present), then deploy_semantic_views.py for any standalone definitions.

## Environment Isolation Patterns

This framework supports three isolation strategies, configured via `environments/*.env.yml`:

### Pattern 1: Database Isolation (Default)

```
  +-------------------------------+  +-------------------------------+
  | AM_SKI_RESORT_DEV             |  | AM_SKI_RESORT_QA              |
  |  +-- RAW                      |  |  +-- RAW                      |
  |  +-- STAGING                  |  |  +-- STAGING                  |
  |  +-- MARTS                    |  |  +-- MARTS                    |
  |  +-- SEMANTIC (dev SVs)       |  |  +-- SEMANTIC (qa SVs)        |
  |  +-- AGENTS  (dev agents)     |  |  +-- AGENTS  (qa agents)      |
  +-------------------------------+  +-------------------------------+

  +-------------------------------+
  | AM_SKI_RESORT_PROD            |
  |  +-- RAW                      |
  |  +-- STAGING                  |
  |  +-- MARTS                    |
  |  +-- SEMANTIC (prod SVs)      |
  |  +-- AGENTS  (prod agents)    |
  +-------------------------------+
```

Each database is fully independent. Schema names stay the same (`SEMANTIC`, `AGENTS`); the database name provides isolation. This is the default pattern, managed by DCM.

### Pattern 2: Account Isolation

```
  +-----------------------------+  +-----------------------------+
  | dev-account.snowflake.com   |  | qa-account.snowflake.com    |
  |  AM_SKI_RESORT_DEV          |  |  AM_SKI_RESORT_QA           |
  |   +-- SEMANTIC              |  |   +-- SEMANTIC              |
  |   +-- AGENTS                |  |   +-- AGENTS                |
  +-----------------------------+  +-----------------------------+

  +-----------------------------+
  | prod-account.snowflake.com  |
  |  AM_SKI_RESORT_PROD         |
  |   +-- SEMANTIC              |
  |   +-- AGENTS                |
  +-----------------------------+
```

Separate Snowflake accounts per environment. Database names follow the same `AM_SKI_RESORT_{ENV}` convention. Configured via `snowflake.account` in the env config.

## Key Design Decisions

### Config-as-Code for Agents
- **Date:** 2026-04-02
- **Decision:** Define agents as YAML specs in Git, deploy via SQL, never configure in the Snowsight UI
- **Rationale:** UI-only configuration has no version history, no PR review, no way to reproduce state across environments, and no rollback path
- **Alternatives considered:** UI-only management, Terraform provider (no agent resource exists), REST API only (less readable than YAML)

### Jinja2 for Environment Parameterization
- **Date:** 2026-04-02
- **Decision:** Use Jinja2 templates in agent and SV YAML files with environment-specific variable substitution
- **Rationale:** Avoids maintaining separate copies of specs per environment; single source of truth with parameterized deployment
- **Alternatives considered:** sed/envsubst (fragile), separate files per env (drift risk), Snowflake variables (not supported in DDL)

### COPY INTO for Stage Uploads
- **Date:** 2026-04-02
- **Decision:** Use `COPY INTO @stage/filename FROM (SELECT '...')` instead of `PUT` for uploading YAML configs to stages
- **Rationale:** PUT creates nested subdirectories (`@stage/filename/tmpXYZ.yaml`) which breaks `EXECUTE_AI_EVALUATION`; COPY INTO writes flat files at the expected path
- **Alternatives considered:** PUT with cleanup (unreliable), external stages (unnecessary complexity)

### Exit-Code Gating for Eval Results
- **Date:** 2026-04-02
- **Decision:** `compute_metrics.py` exits 0 (pass) or 1 (fail) based on threshold comparison, used directly as a GitHub Actions step condition
- **Rationale:** Simplest possible CI gate — no custom GitHub Actions, no webhook callbacks, just Unix exit codes
- **Alternatives considered:** GitHub Status API (more complex), custom GitHub Action (maintenance burden), manual approval only (no automation)

### Deploy Order: dbt -> SVs -> Agents -> Eval
- **Date:** 2026-04-02
- **Decision:** Enforce strict ordering: dbt materializes base tables, then semantic views are created on those tables, then agents are created referencing those views, then evaluations validate the full chain
- **Rationale:** Each layer depends on the one below it; deploying out of order causes missing-table or missing-view errors that are hard to diagnose
- **Alternatives considered:** Parallel deploy (fails on dependencies), single monolithic script (less visible, harder to debug)

### Separate Data and CI/CD Pipelines
- **Date:** 2026-04-02
- **Decision:** Keep the daily data refresh (data_generation + dbt) as a separate pipeline from the CI/CD promotion workflows
- **Rationale:** Data freshness is a daily concern independent of spec changes. Coupling them means a dbt failure blocks agent promotions, and agent promotions unnecessarily re-run dbt. The CI/CD pipeline assumes base tables are current.
- **Alternatives considered:** Single monolithic pipeline (too coupled), CI/CD always runs dbt (slow and unnecessary)

## Infrastructure as Code (DCM)

All Snowflake infrastructure is defined declaratively using Database Change Management (DCM).
The DCM project lives in `dcm/` and manages database, schemas, warehouse, roles, and grants.

```
  Role Hierarchy
  ==============

  SYSADMIN (Snowflake built-in)
      |
  AM_DEPLOY_ROLE_{DEV|QA|PROD} (CI/CD service account — owns DCM project, runs dbt, deploys agents)
      |
      +-- AM_SKI_RESORT_WH_{DEV|QA|PROD}_USER (account role — warehouse USAGE)
      |
      +-- AM_SKI_RESORT_{DEV|QA|PROD}.ADMIN (database role — DDL + Cortex objects on all schemas)
              |
          AM_SKI_RESORT_{DEV|QA|PROD}.DEVELOPER (database role — DML on RAW/STAGING, stage WRITE on AGENTS)
              |
          AM_SKI_RESORT_{DEV|QA|PROD}.ANALYST (database role — SELECT on all schemas + future objects)
```

**Grant Matrix — What Each Role Can Do:**

```
  Schema     | ANALYST (read)       | DEVELOPER (write)         | ADMIN (DDL + Cortex)
  -----------+----------------------+---------------------------+------------------------------
  RAW        | SELECT (all+future)  | INSERT/UPDATE/DELETE       | CREATE TABLE/VIEW/DT/STAGE
  STAGING    | SELECT (all+future)  | INSERT/UPDATE/DELETE       | CREATE TABLE/VIEW/DT/STAGE
  MARTS      | SELECT (all+future)  | —                         | CREATE TABLE/VIEW/DT/STAGE
  DOCS       | SELECT (all+future)  | —                         | CREATE TABLE/VIEW/DT/STAGE
             |                      |                           | + CREATE CORTEX SEARCH SERVICE
  SEMANTIC   | SELECT (all+future)  | —                         | CREATE TABLE/VIEW/DT/STAGE
             |                      |                           | + CREATE SEMANTIC VIEW
             |                      |                           | + CREATE AGENT
  AGENTS     | SELECT (all+future)  | stage READ/WRITE (evals)  | CREATE TABLE/VIEW/DT/STAGE
             |                      |                           | + CREATE AGENT
             |                      |                           | + CREATE SEMANTIC VIEW
             |                      |                           | + CREATE CORTEX SEARCH SERVICE
  DBT_TEST   | SELECT (all+future)  | —                         | CREATE TABLE/VIEW/DT/STAGE
  __AUDIT    |                      |                           | (dbt build store_failures)
  ALL        | —                    | —                         | + CREATE FUNCTION
             |                      |                           | + CREATE PROCEDURE
```

**Why these grants:**
- **dbt** runs as ADMIN: needs CREATE TABLE (dims, facts), CREATE VIEW (staging), CREATE DYNAMIC TABLE
- **deploy_agents.py** runs as ADMIN: needs CREATE AGENT on AGENTS schema
- **deploy_semantic_views.py** runs as ADMIN: needs CREATE SEMANTIC VIEW on SEMANTIC schema
- **data_generation** runs as ADMIN: needs CREATE TABLE on RAW, CREATE CORTEX SEARCH SERVICE on DOCS
- **eval pipeline** runs as DEVELOPER: needs stage READ/WRITE on AGENTS for config uploads
- **FUTURE grants** on ANALYST: ensures new tables/views created by dbt are immediately readable

```
  DCM Deployment Flow
  ===================

  dcm/manifest.yml          snow dcm plan         snow dcm deploy
  (DEV/QA/PROD targets)     (validate, preview)   (apply changes)
       |                          |                      |
       v                          v                      v
  +------------------+    +------------------+    +---------------------+
  | Template vars    |    | 16 entities      |    | AM_SKI_RESORT_{ENV} |
  | per environment  |--->| 14 create        |--->| database created    |
  | (wh_size, users) |    | 2 alter          |    | roles granted       |
  |                  |    | 0 drop           |    | warehouse ready     |
  +------------------+    +------------------+    +---------------------+
```

Warehouse configuration varies by environment:

| Property | DEV | QA | PROD |
|----------|-----|-----|------|
| Size | SMALL | SMALL | SMALL |
| Min Clusters | 1 | 1 | 1 |
| Max Clusters | 1 | 3 | 5 |
| Auto-Suspend | 300s | 300s | 120s |
| Queued Timeout | 600s | 600s | 300s |
| Statement Timeout | 1800s | 1800s | 3600s |

## Environment Setup
- Snowflake connection: Configured per environment in `environments/*.env.yml`
- Database: AM_SKI_RESORT_DEV / AM_SKI_RESORT_QA / AM_SKI_RESORT_PROD (created by DCM)
- Schemas: RAW, STAGING, MARTS, DOCS, SEMANTIC, AGENTS, DBT_TEST__AUDIT (same in every database)
- Warehouse: AM_SKI_RESORT_WH_DEV / AM_SKI_RESORT_WH_QA / AM_SKI_RESORT_WH_PROD (created by DCM)
- Role: AM_DEPLOY_ROLE_DEV / AM_DEPLOY_ROLE_QA / AM_DEPLOY_ROLE_PROD (created by DCM)
- Snapshot table: `<database>.AGENTS.CI_CD_SNAPSHOTS` (auto-created by snapshot_state.py)

## Agent Deploy Strategy

Agents are deployed using a three-tier approach that preserves evaluation history:

```
  Agent exists?  --yes-->  ALTER AGENT <fqn> MODIFY LIVE VERSION SET SPECIFICATION = $$ spec $$
       |
       no
       |
       v
  CREATE AGENT IF NOT EXISTS <fqn> ... FROM SPECIFICATION $$ spec $$

  --force-create flag:
  CREATE OR REPLACE AGENT <fqn> ... FROM SPECIFICATION $$ spec $$
  (WARNING: destroys eval history — use only when schema changes require it)
```

`ALTER AGENT` is preferred because it preserves the agent's evaluation run history,
allowing trend analysis across deployments. `CREATE OR REPLACE` resets this history.

## Test Results Summary (Session 7, 2026-04-03)

```
  50 test cases across 9 requirements
  33 PASS | 0 FAIL | 5 BLOCKED | 12 NOT RUN

  pytest tests (smoke + eval rendering + template rendering)
  All PASS (14/14 config tests verified)

  pip install -e . verified, 9 CLI entry points functional

  BLOCKED: actionlint not installed (5), GET_ANALYST_AI_EVALUATION_DATA unavailable (3)
  NOT RUN: GitHub trigger tests (4), dbt/data-gen scope (5), deploy order enforcement (1)
```

## Packaging and Installation

The framework is pip-installable as `agent-mgmt`:

```
pip install -e .                   # Development install (editable)
pip install -e ".[dev]"           # With pytest + ruff
pip install -e ".[crypto]"        # With cryptography for key-pair auth
```

9 CLI entry points are available after installation:

```
agent-mgmt-deploy-agents          # Deploy agents from YAML specs
agent-mgmt-deploy-svs             # Deploy semantic views
agent-mgmt-validate               # Validate YAML specs
agent-mgmt-snapshot               # Snapshot current state
agent-mgmt-rollback               # Rollback from snapshot
agent-mgmt-metrics                # Compute eval metrics (F1/precision/recall)
agent-mgmt-render-eval            # Render eval templates for target env
agent-mgmt-detect-drift           # Detect Git vs Snowflake drift
agent-mgmt-check-sv-eval          # Check SV evaluation results
```

## Patterns and Conventions
- All Snowflake SQL: uppercase keywords, lowercase identifiers, fully qualified object names
- All Python: snake_case, type hints, no comments unless explaining why
- YAML specs: Jinja2 placeholders for env-specific values, static for everything else
- Git: feature branches -> PR to main -> merge triggers deploy
- Naming: agent specs match Snowflake object names (resort_executive.yml -> RESORT_EXECUTIVE)
- Eval datasets: one YAML per agent, questions cover all bound semantic views
