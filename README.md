# Agent Management — CI/CD Reference Framework

> **Status:** Complete (v0.5.0)
> **Owner:** Jeremy Demlow
> **Created:** April 2026

A production-quality, pip-installable CI/CD framework for managing **Snowflake Cortex Agents**, **Semantic Views**, and **dbt** as code. Define agents and semantic views in YAML, deploy through environment-parameterized GitHub Actions, evaluate with golden question sets, and rollback from snapshots when things break.

Built as a reference implementation for a Medium article — fork it, swap in your domain, ship it.

## Quick Start

```bash
git clone https://github.com/Jeremy-Demlow/AgentMangement.git
cd AgentMangement

pip install -e ".[dev]"

# Validate all specs
agent-mgmt-validate --env dev

# Dry-run deploy
agent-mgmt-deploy-svs --env dev --dry-run
agent-mgmt-deploy-agents --env dev --dry-run

# Deploy for real
agent-mgmt-deploy-svs --env dev
agent-mgmt-deploy-agents --env dev
```

## Two Paths for Semantic Views

This framework supports **both** approaches to deploying semantic views. Use whichever fits your team, or both together.

### Path A: dbt-native (recommended if you have dbt)

Semantic views are defined as dbt models using the `dbt_semantic_view` materialization from `Snowflake-Labs/dbt_semantic_view`. They live alongside your facts and dimensions in the dbt DAG.

```
dbt_ski_resort/models/marts/semantic/
  sem_operations.sql          <-- {{ config(materialized='semantic_view') }}
  sem_revenue.sql
  sem_customer_behavior.sql
  ... (11 total)
  _semantic.yml               <-- model configs
```

Each dbt target points at the corresponding environment database (`AM_SKI_RESORT_DEV`, `AM_SKI_RESORT_QA`, `AM_SKI_RESORT_PROD`). Semantic views always land in the `SEMANTIC` schema.

```bash
# Dev: SVs land in AM_SKI_RESORT_DEV.SEMANTIC
dbt run --target dev --select "marts.semantic"

# QA: SVs land in AM_SKI_RESORT_QA.SEMANTIC
dbt run --target qa --select "marts.semantic"

# Prod: SVs land in AM_SKI_RESORT_PROD.SEMANTIC
dbt run --target prod --select "marts.semantic"
```

**Why choose dbt:** dependency graph, lineage, dbt tests, single source of truth for data + semantic layer.

### Path B: Python CI/CD (works without dbt)

Semantic views are defined as standalone YAML files with Jinja2 environment placeholders. Deployed via `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML`.

```
semantic-views/definitions/
  sem_operations.yaml         <-- {{ env.database }}.MARTS.FACT_LIFT_SCANS
  sem_revenue.yaml
  sem_customer_behavior.yaml
  ... (11 total)
```

```bash
agent-mgmt-deploy-svs --env dev       # -> AM_SKI_RESORT_DEV.SEMANTIC
agent-mgmt-deploy-svs --env qa        # -> AM_SKI_RESORT_QA.SEMANTIC
agent-mgmt-deploy-svs --env prod      # -> AM_SKI_RESORT_PROD.SEMANTIC
```

**Why choose this:** no dbt dependency, supports snapshot/rollback, dry-run validation, works for any team.

### Using Both Together

In the CI/CD workflows, dbt runs first (facts then semantic views), then the Python deployer handles any SVs not managed by dbt. The GitHub Actions workflows include conditional dbt steps:

```yaml
- name: Run dbt build (if dbt project exists)
  if: hashFiles('dbt_ski_resort/dbt_project.yml') != ''
  run: |
    cd dbt_ski_resort
    dbt build --target dev --select "marts.semantic"
```

## Deploy Order

```
dbt build (facts + semantic)  ->  Python SV deploy  ->  Agent deploy  ->  Evaluation
```

Each layer depends on the one before it. The workflows enforce this ordering.

## CLI Commands

After `pip install -e .`:

| Command | Description |
|---------|-------------|
| `agent-mgmt-deploy-agents` | Deploy agents from YAML specs (ALTER if exists, CREATE if new) |
| `agent-mgmt-deploy-svs` | Deploy semantic views from YAML definitions |
| `agent-mgmt-validate` | Validate YAML specs (lint + optional Snowflake dry-run) |
| `agent-mgmt-snapshot` | Snapshot current agent/SV state for rollback |
| `agent-mgmt-rollback` | Restore from a timestamped snapshot |
| `agent-mgmt-metrics` | Compute F1/precision/recall from eval results |
| `agent-mgmt-render-eval` | Render eval templates for a target environment |
| `agent-mgmt-detect-drift` | Detect Git vs Snowflake spec drift |
| `agent-mgmt-check-sv-eval` | Check semantic view evaluation results |

## Environment Strategy

Separate databases per environment, managed by DCM:

```
AM_SKI_RESORT_DEV   (dev)    AM_SKI_RESORT_QA   (qa)    AM_SKI_RESORT_PROD   (prod)
  +-- RAW                      +-- RAW                    +-- RAW
  +-- STAGING                  +-- STAGING                +-- STAGING
  +-- MARTS                    +-- MARTS                  +-- MARTS
  +-- SEMANTIC                 +-- SEMANTIC               +-- SEMANTIC
  +-- AGENTS                   +-- AGENTS                 +-- AGENTS
```

Configured in `project.yml` + `environments/*.env.yml`.

## Repository Structure

```
AgentMangement/
  project.yml                     # Single source of truth for names
  pyproject.toml                  # pip install -e . (agent-mgmt 0.5.0)
  agents/specs/                   # Agent YAML templates (Jinja2)
  semantic-views/definitions/     # SV YAML templates (Jinja2)
  scripts/                        # Deploy, eval, snapshot, rollback
  agent-evaluation/               # Eval configs, datasets, metrics, results
  data_generation/                # Synthetic ski resort data
  dbt_ski_resort/                 # dbt project (23 staging, 6 dims, 13 facts, 11 SVs)
  environments/                   # Per-env config (dev, qa, prod)
  .github/workflows/             # CI/CD pipelines
  requirements/                   # Traceable requirements (REQ-001..011)
  docs/                           # Architecture, dev notes
  tests/                          # 76 pytest tests
```

## Agent Deploy Strategy

Agents are deployed using ALTER (preserves eval history) by default:

```
Agent exists?  --yes-->  ALTER AGENT ... MODIFY LIVE VERSION SET SPECIFICATION
     |
     no --> CREATE AGENT IF NOT EXISTS ...

--force-create flag:  CREATE OR REPLACE (WARNING: destroys eval history)
```

## Adapting for Your Domain

1. Edit `project.yml` — change database names, schemas, raw tables
2. Edit `environments/*.env.yml` — change deployment targets
3. Write agent specs in `agents/specs/`
4. Write SV definitions in `semantic-views/definitions/` and/or `dbt_*/models/marts/semantic/`
5. Create eval datasets in `agent-evaluation/datasets/`
6. Run `agent-mgmt-validate --env dev` to check everything

## Tests

```bash
pip install -e ".[dev]"
pytest tests/ -q
# 76 passed
```

## Requirements

- Python 3.11+
- Snowflake account with Cortex Agents enabled
- dbt-snowflake (optional, for dbt path)
