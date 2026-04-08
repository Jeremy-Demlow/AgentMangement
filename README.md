# Agent Management — CI/CD Reference Framework for Snowflake Cortex Agents

A production-quality CI/CD framework for managing **Snowflake Cortex Agents**, **Semantic Views**, and **dbt** as code. Define agents and semantic views in YAML, deploy through environment-parameterized pipelines, evaluate with golden question sets, and rollback from snapshots when things break.

Built as a reference implementation — fork it, swap in your domain, ship it.

## What This Repo Does

```
RAW data (12 tables)
  → dbt transforms (23 staging views → 6 dimensions → 13 facts)
    → 11 Semantic Views (Cortex Analyst)
      → 2 Cortex Agents (natural language interface)
        → Automated Evaluations (answer_correctness, logical_consistency)
```

The framework manages the full lifecycle across three environments (DEV, QA, PROD), each in its own Snowflake database. Infrastructure is provisioned by DCM. Data flows from PROD (source of truth) to DEV/QA via zero-copy clones.

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────────┐
│  Git Repository                                                 │
│                                                                 │
│  project.yml ─── Single source of truth for names/config        │
│       │                                                         │
│  environments/                                                  │
│    dev.env.yml ── Database, role, warehouse, agent name_suffix  │
│    qa.env.yml                                                   │
│    prod.env.yml                                                 │
│       │                                                         │
│  ┌────┴──────────────────────────────────────────────────┐      │
│  │  Deploy Pipeline (order matters)                       │      │
│  │                                                        │      │
│  │  1. DCM         → databases, schemas, roles, grants    │      │
│  │  2. dbt run    → staging → dims → facts → semantic     │      │
│  │  3. Deploy SVs  → SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML│      │
│  │  4. Deploy Agents → ALTER AGENT / CREATE AGENT         │      │
│  │  5. Evaluate    → EXECUTE_AI_EVALUATION + thresholds   │      │
│  └────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  Snowflake (single account, 3 databases)                        │
│                                                                 │
│  AM_SKI_RESORT_DEV          AM_SKI_RESORT_QA                    │
│    RAW (cloned from PROD)     RAW (cloned from PROD)            │
│    STAGING                    STAGING                            │
│    MARTS                      MARTS                             │
│    SEMANTIC (11 SVs)          SEMANTIC (11 SVs)                 │
│    AGENTS                     AGENTS                            │
│      RESORT_EXECUTIVE_DEV       RESORT_EXECUTIVE_QA             │
│      SKI_OPS_ASSISTANT_DEV      SKI_OPS_ASSISTANT_QA            │
│                                                                 │
│  AM_SKI_RESORT_PROD (source of truth)                           │
│    RAW (real data)                                              │
│    STAGING / MARTS / SEMANTIC / AGENTS / DBT_TEST__AUDIT        │
│      RESORT_EXECUTIVE           (no suffix — canonical)         │
│      SKI_OPS_ASSISTANT                                          │
└─────────────────────────────────────────────────────────────────┘
```

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

## Repository Structure

```
AgentMangement/
│
├── project.yml                      # Central config: databases, schemas, deployment mode
├── pyproject.toml                   # pip install -e . (agent-mgmt 0.5.0)
│
├── environments/                    # Per-env config (database, role, warehouse, name_suffix)
│   ├── dev.env.yml
│   ├── qa.env.yml
│   └── prod.env.yml
│
├── agent_management/                # Core Python library (pip-installable)
│   ├── deploy_agents.py             #   ALTER AGENT / CREATE AGENT
│   ├── deploy_semantic_views.py     #   SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML
│   ├── render_template.py           #   Jinja2 env substitution
│   ├── snapshot_state.py            #   Pre-deploy state capture
│   ├── rollback.py                  #   Restore from snapshot
│   ├── validate_specs.py            #   YAML lint + dry-run
│   ├── detect_drift.py              #   Git vs Snowflake diff
│   ├── compute_metrics.py           #   F1/precision/recall from eval
│   ├── check_sv_eval.py             #   SV eval quality gate
│   ├── render_eval_templates.py     #   Render eval configs per env
│   ├── ci/                          #   CI checks (test coverage, PK tests, lineage)
│   └── utils/
│       ├── config.py                #   Config loading, FQN helpers, suffix resolution
│       └── snowflake_client.py      #   Snowflake connection wrapper
│
├── agents/                          # Cortex Agent definitions
│   └── specs/                       #   Jinja2 YAML templates
│       ├── resort_executive.yml
│       └── ski_ops_assistant.yml
│
├── semantic-views/                  # Semantic View definitions (standalone path)
│   └── definitions/                 #   11 Jinja2 YAML templates
│
├── agent-evaluation/                # Evaluation framework (separate README)
│   ├── scripts/run_eval.py          #   End-to-end eval runner
│   ├── configs/                     #   One config per agent
│   ├── datasets/                    #   Golden question sets per agent
│   ├── metrics/                     #   Custom LLM-judge metrics
│   └── results/                     #   JSON results from runs
│
├── dbt_ski_resort/                  # dbt project (separate README)
│   └── models/
│       ├── staging/                 #   23 type-safe views
│       ├── marts/dimensions/        #   6 dimension tables
│       ├── marts/facts/             #   13 fact tables (incremental)
│       └── marts/semantic/          #   11 semantic views (dbt materialization)
│
├── dcm/                             # Infrastructure as Code (separate README)
│   ├── manifest.yml                 #   DEV/QA/PROD targets
│   └── sources/                     #   Database, schemas, roles, grants
│
├── data_generation/                 # Synthetic ski resort data
│
├── .github/workflows/               # CI/CD pipelines
│   ├── deploy-dev.yml               #   Deploy on merge to main (environment: DEV)
│   ├── promote-qa.yml               #   Manual promote with eval gate (environment: QA)
│   ├── promote-prod.yml             #   Manual promote with approval (environment: PROD)
│   ├── validate-pr.yml              #   Lint + validate on PR
│   ├── rollback.yml                 #   Rollback any environment
│   ├── daily_data_refresh.yml       #   Daily data pipeline (environment: PROD)
│   └── dcm-deploy.yml              #   DCM infrastructure deploy
│
├── .github/scripts/                 # CI/CD helper scripts
│   ├── setup_github_secrets.sh      #   Set repo + environment secrets via gh CLI
│   ├── setup_github_environments.sh #   Create GitHub environments with descriptions
│   ├── teardown.sh                  #   Remove all secrets + environments
│   └── test_workflow_locally.sh     #   Run workflow steps locally against real Snowflake
│
├── .github/PIPELINE_SETUP.md        # CI/CD pipeline setup guide
│
├── tests/                           # Python tests (smoke + template rendering)
├── docs/                            # Architecture, data dictionary, dev notes
├── requirements/                    # Traceable requirements (REQ-001..013)
└── models/                          # Data model documentation
```

## Deployment Mode

Configured in `project.yml` under `deployment.mode`:

| Mode | Agent Naming | Use Case |
|------|-------------|----------|
| `single_account` | PROD: `RESORT_EXECUTIVE` (no suffix), DEV: `RESORT_EXECUTIVE_DEV`, QA: `RESORT_EXECUTIVE_QA` | All envs in one Snowflake account |
| `cross_account` | Same name in every account (no suffix needed) | Separate Snowflake accounts per env |

In single-account mode, `name_suffix` from each environment config is appended to agent names. The agent's `display_name` in Snowsight also gets a label (e.g., `[DEV]`) via `resolve_profile()`.

## Data Flow Direction

PROD is the source of truth. DEV and QA clone RAW tables from PROD using zero-copy clones:

```
PROD (real data)  ──clone──>  DEV (iterate on agents/SVs)
                  ──clone──>  QA  (validate before promoting)
```

Configured via `deployment.data_source: prod` in `project.yml`.

## Two Paths for Semantic Views

### Path A: dbt-native (recommended if you have dbt)

Semantic views live in `dbt_ski_resort/models/marts/semantic/` using the `dbt_semantic_view` materialization. Each dbt target deploys to the corresponding environment database.

```bash
dbt run --target dev --select "marts.semantic"   # → AM_SKI_RESORT_DEV.SEMANTIC
dbt run --target prod --select "marts.semantic"  # → AM_SKI_RESORT_PROD.SEMANTIC
```

### Path B: Python CI/CD (works without dbt)

Standalone YAML definitions in `semantic-views/definitions/` with Jinja2 placeholders, deployed via `agent-mgmt-deploy-svs`.

Both paths produce identical Snowflake objects and can coexist.

## Agent Deploy Strategy

Agents are deployed using ALTER (preserves eval history) by default:

```
Agent exists?  ──yes──>  ALTER AGENT ... MODIFY LIVE VERSION SET SPECIFICATION
     │
     no ──> CREATE AGENT IF NOT EXISTS ...

--force-create:  CREATE OR REPLACE (WARNING: destroys eval history)
```

## CLI Commands

After `pip install -e .`:

| Command | Description |
|---------|-------------|
| `agent-mgmt-deploy-agents` | Deploy agents from YAML specs |
| `agent-mgmt-deploy-svs` | Deploy semantic views from YAML definitions |
| `agent-mgmt-validate` | Validate YAML specs (lint + optional dry-run) |
| `agent-mgmt-snapshot` | Snapshot current agent/SV state for rollback |
| `agent-mgmt-rollback` | Restore from a timestamped snapshot |
| `agent-mgmt-metrics` | Compute F1/precision/recall from eval results |
| `agent-mgmt-render-eval` | Render eval templates for a target environment |
| `agent-mgmt-detect-drift` | Detect Git vs Snowflake spec drift |
| `agent-mgmt-check-sv-eval` | Check semantic view evaluation results |

## Evaluations

See [`agent-evaluation/README.md`](agent-evaluation/README.md) for the full evaluation framework. Quick version:

```bash
cd agent-evaluation && uv sync

# Dry run
uv run python scripts/run_eval.py configs/resort_executive.yaml --dry-run

# Full eval (polls, checks thresholds, saves JSON)
uv run python scripts/run_eval.py configs/resort_executive.yaml --connection myconnection --env dev
```

## Adapting for Your Domain

1. Edit `project.yml` — change database names, schemas, raw tables, deployment mode
2. Edit `environments/*.env.yml` — change deployment targets and name suffixes
3. Write agent specs in `agents/specs/`
4. Write SV definitions in `semantic-views/definitions/` and/or `dbt_*/models/marts/semantic/`
5. Create eval datasets in `agent-evaluation/datasets/`
6. Run `agent-mgmt-validate --env dev` to check everything

## Tests

```bash
pip install -e ".[dev]"
pytest tests/ -q
```

## CI/CD Authentication

All GitHub Actions workflows use **RSA key-pair (JWT) authentication** — no passwords in pipelines.

Secrets are split between **repo-level** (shared across all workflows) and **environment-level** (per DEV/QA/PROD):

| Level | Secret | Example Value |
|-------|--------|---------------|
| Repo | `SNOWFLAKE_ACCOUNT` | `trb65519` |
| Repo | `SNOWFLAKE_USER` | `JDEMLOW` |
| Repo | `SNOWFLAKE_PRIVATE_KEY` | Contents of `.p8` file |
| Env: DEV | `SNOWFLAKE_WAREHOUSE` | `AM_SKI_RESORT_WH_DEV` |
| Env: DEV | `SNOWFLAKE_ROLE` | `AM_DEPLOY_ROLE_DEV` |
| Env: DEV | `SNOWFLAKE_DATABASE` | `AM_SKI_RESORT_DEV` |
| Env: QA | `SNOWFLAKE_WAREHOUSE` | `AM_SKI_RESORT_WH_QA` |
| Env: QA | `SNOWFLAKE_ROLE` | `AM_DEPLOY_ROLE_QA` |
| Env: QA | `SNOWFLAKE_DATABASE` | `AM_SKI_RESORT_QA` |
| Env: PROD | `SNOWFLAKE_WAREHOUSE` | `AM_SKI_RESORT_WH_PROD` |
| Env: PROD | `SNOWFLAKE_ROLE` | `AM_DEPLOY_ROLE_PROD` |
| Env: PROD | `SNOWFLAKE_DATABASE` | `AM_SKI_RESORT_PROD` |

Each workflow job declares `environment: DEV` (or QA/PROD), and `${{ secrets.SNOWFLAKE_DATABASE }}` resolves to the correct value for that environment.

Setup: `.github/scripts/setup_github_secrets.sh` · Teardown: `.github/scripts/teardown.sh`

See [`.github/PIPELINE_SETUP.md`](.github/PIPELINE_SETUP.md) for the full setup guide.

## Local Testing

Run CI/CD workflow steps locally against real Snowflake:

```bash
PYTHON=/path/to/python DBT=/path/to/dbt TARGET_ENV=dev \
  .github/scripts/test_workflow_locally.sh snapshot
```

Available steps: `snapshot`, `dbt`, `deploy-svs`, `sv-eval`, `deploy-agents`, `agent-eval`, `compute-metrics`

The script force-sets `SNOWFLAKE_DATABASE`, `SNOWFLAKE_ROLE`, and `SNOWFLAKE_WAREHOUSE` per `TARGET_ENV` to avoid IDE environment contamination.

## Requirements

- Python 3.11+
- Snowflake account with Cortex Agents enabled
- dbt-snowflake (optional, for dbt path)
- Snowflake CLI 3.16+ (for DCM)
