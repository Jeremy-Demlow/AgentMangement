# Contributing

## Development Workflow

This repo uses **two** Snowflake environments and **Cortex Agent Versioning**
for all agent lifecycle operations.

```
feature-branch  →  PR to dev    →  validate-pr.yml (dry-run matrix: dev, prod)
                     merge to dev  →  deploy-dev.yml (real deploy to DEV, alias=latest)
dev             →  PR to main   →  validate-pr.yml (dry-run matrix: dev, prod)
                     merge to main →  deploy-prod-validated.yml (deploy to PROD, alias=validated, eval)
main            →  manual dispatch →  promote-validated-to-production.yml
                                        (approval gate: production-promote env)
incident        →  manual dispatch →  rollback.yml (single alias-reassignment)
```

There is no QA environment. The "pre-production eval" that QA used to serve now
runs against the `validated` alias on the PROD agent. Customer traffic follows
the `production` alias, which only moves after a human approval.

See:

- [docs/operations/AGENT_VERSIONING.md](docs/operations/AGENT_VERSIONING.md)
- [docs/operations/ROLLBACK_RUNBOOK.md](docs/operations/ROLLBACK_RUNBOOK.md)
- [docs/semantic-views/VQR_GUIDE.md](docs/semantic-views/VQR_GUIDE.md)
- [reqs/README.md](reqs/README.md)

## Agent spec style guide

Every `tools[i].description` in `agents/specs/*.yml` must contain these seven
sections in order:

```
PURPOSE:               what the tool does, in one sentence
DATA:                  which tables / SVs the tool reads
KEY METRICS:           the main numeric outputs
KEY DIMENSIONS:        which slicing dimensions apply
USE FOR:               representative question styles
NOT FOR:               question styles this tool should refuse
CROSS-REFERENCE WITH:  sibling tools the agent can chain with
```

Validate locally:

```bash
python -m agent_management.validate_spec_format agents/specs/resort_executive.yml
```

Seasons must be resolved from `DIM_DATE`; hard-coded strings like `2024-2025`
in `instructions:` blocks will fail validation.

### 1. Create a feature branch

```bash
git checkout -b feature/my-change
```

### 2. Make changes

- Agent specs → `agents/specs/*.yml`
- Semantic view definitions → `semantic-views/definitions/*.yml`
- Eval configs/datasets → `agent-evaluation/configs/` and `agent-evaluation/datasets/`
- dbt models → `dbt_ski_resort/models/`

### 3. Validate locally

```bash
pip install -e ".[dev]"

# Lint + unit tests
pytest tests/test_smoke.py tests/test_templates.py -v

# Validate specs for all envs
python -m agent_management.validate_specs --env dev
python -m agent_management.validate_specs --env qa
python -m agent_management.validate_specs --env prod

# Dry-run deploy against DEV
python -m agent_management.deploy_semantic_views --env dev --dry-run
python -m agent_management.deploy_agents --env dev --dry-run
```

### 4. Open a PR

Push your branch and open a PR to `dev` (for development iteration) or `main` (for release). The **Validate PR** workflow runs automatically:

| Job | What it does |
|-----|-------------|
| `lint-and-unit` | Runs pytest smoke tests |
| `validate-specs` | Validates YAML specs for both environments (dev, prod) |
| `dbt-quality-gate` | Parses the dbt project |
| `validate-snowflake` | Dry-run deploys against DEV (no actual changes) |

All four jobs must pass before merge.

### 5. Merge to dev → Auto-deploy to DEV

Merging to `dev` triggers **Deploy Dev**:
1. Snapshots current DEV state (for rollback)
2. Runs dbt
3. Deploys semantic views
4. Deploys agents (ALTER preserves eval history)
5. Runs evaluations (advisory — failures don't block)

### 6. Merge dev to main → Deploy PROD `validated`

When DEV looks good, open a PR from `dev` to `main` and merge. The merge automatically runs **deploy-prod-validated.yml**, which requires a single approval on the `PROD` GitHub environment, then snapshots, deploys SVs and agents (alias=`validated`), and runs smoke + eval against the validated alias. Threshold failures on the post-deploy eval are advisory: the deploy still completes, but the alias does not move to `production` until you manually promote.

### 7. Promote validated → production

Trigger **promote-validated-to-production.yml** manually. It requires a second reviewer approval (the `production-promote` GitHub environment) and flips the `production` alias to the version currently held by `validated`. A post-promote smoke + eval runs as a safety check; if it regresses, trigger **rollback.yml** to reassign the `production` alias back to a prior version.

## CI/CD Pipeline Architecture

```
PR opened (to dev or main)  →  validate-pr.yml                       (dry-run + evals; blocking on main)
Merge to dev                →  deploy-dev.yml                        (real deploy, alias=latest, evals advisory)
Merge to main               →  deploy-prod-validated.yml             (PROD approval, alias=validated, eval advisory)
Manual dispatch             →  promote-validated-to-production.yml   (production-promote approval, alias flip + smoke + eval)
Manual dispatch             →  rollback.yml                          (alias reassignment)
Scheduled daily             →  daily_data_refresh.yml                (PROD data pipeline + DEV sync)
Manual dispatch             →  sync_env_data.yml                     (copy RAW data from PROD to DEV)
PR / push (dev or main)     →  dcm-deploy.yml                        (infra plan/deploy, paths: dcm/**)
```

There is intentionally no QA environment. Pre-production internal validation runs against the `validated` alias on the same PROD agent that will eventually receive customer traffic via the `production` alias.

## Environment Mapping

| Input value | GitHub Environment | Snowflake Database | Snowflake Role |
|-------------|-------------------|-------------------|----------------|
| `dev` | `DEV` | `AM_SKI_RESORT_DEV` | `AM_DEPLOY_ROLE_DEV` |
| `prod` | `PROD` (single approval) + `production-promote` (second approval for alias flip) | `AM_SKI_RESORT` | `AM_DEPLOY_ROLE` |

## Secrets & Variables Architecture

- **Repo-level secrets**: `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PRIVATE_KEY`
- **Environment-level variables** (per DEV/PROD): `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_ROLE`, `SNOWFLAKE_DATABASE`

> **Why variables, not secrets?** GitHub Actions masks any value stored as a secret wherever it
> appears in log output. Database names, roles, and warehouses are not sensitive, and masking
> them breaks Snowsight URLs and makes CI logs harder to read. Only truly sensitive values
> (account identifier, username, private key) are stored as secrets.

Every job that connects to Snowflake declares `environment:` to pull the correct variables and secrets.

## Data Pipeline & Environment Sync

Data generation runs only in **PROD** (`daily_data_refresh.yml`). DEV receives data via **sync**, not independent generation — this ensures both environments test against the same dataset.

**Flow:**

```
daily_data_refresh.yml (PROD)
  └── generate_daily_increment.py → AM_SKI_RESORT.RAW.*
  └── dbt run → STAGING + MARTS in PROD
  └── sync_env_data.yml (DEV)
        ├── TRUNCATE + INSERT RAW tables from PROD
        └── dbt run → rebuild STAGING + MARTS
```

**Manual sync**: Run `sync_env_data.yml` with `target_envs: dev` to copy current PROD data.

**Adding new RAW tables**: Add the table name to `raw_tables` in `project.yml`. The sync workflow reads this list. Also ensure the table DDL exists in all environments (create via DCM or manual `CREATE TABLE ... LIKE`).

**Local generation to a specific env**: `python generate_daily_increment.py --env dev --date 2026-01-01 --days 30`

## Evaluation Strategy

| Environment | Eval behavior | On failure |
|-------------|--------------|------------|
| PR to `dev` | Advisory (`continue-on-error` true on dev base ref) | Logged; can merge |
| PR to `main` | Blocking SV + agent eval | Merge blocked |
| `deploy-dev.yml` (post-merge to dev) | Advisory | Logged; deploy still updates `latest` |
| `deploy-prod-validated.yml` (post-merge to main) | Advisory threshold; crash hard-fails | Operator decides whether to promote |
| `promote-validated-to-production.yml` | Advisory threshold; crash hard-fails | Trigger `rollback.yml` if regressed |

All evals go through `python -m agent_management.run_ci_eval --env <env>` which handles agent name suffix resolution.

### Eval Thresholds

Thresholds are **environment-driven**, not hardcoded. Each environment defines pass/fail gates in `environments/<env>.env.yml`:

```yaml
eval:
  thresholds:
    answer_correctness: 0.60    # DEV — lenient while establishing baseline
    logical_consistency: 0.60
```

| Environment | answer_correctness | logical_consistency |
|-------------|-------------------|-------------------|
| DEV | 0.60 | 0.60 |
| PROD | 0.80 | 0.80 |

The eval config templates in `agent-evaluation/configs/` use `{{ eval.thresholds.answer_correctness }}` Jinja2 placeholders. These are resolved at two points:

1. **CI runtime** — `run_ci_eval.py` renders templates via `render_file()` before running evals
2. **Pre-generation** — `render_eval_templates.py` generates resolved configs into `agent-evaluation/generated/<env>/`

To change thresholds, edit the `eval.thresholds` section in the environment config — **not** the template configs or generated configs.

## Agent Naming

Single-account mode uses suffixes:

| Environment | Agent name |
|-------------|-----------|
| DEV | `RESORT_EXECUTIVE_DEV` |
| PROD | `RESORT_EXECUTIVE` (no suffix; aliases `validated` and `production` distinguish pre/customer traffic) |

## Rollback

```bash
# List available snapshots
# (via GitHub Actions → Rollback → leave timestamp empty)

# Or locally:
python -m agent_management.rollback --env dev --list
python -m agent_management.rollback --env dev --timestamp 20260409_120000 --target all --dry-run
```

## Future Development

- **Multi-account deployment**: Separate Snowflake accounts per environment (cross-account mode in `project.yml`)
- **Feature branch environments**: Ephemeral Snowflake databases per PR branch (individual developer iteration)
- **Evaluation dashboard**: Streamlit app for historical eval trend analysis
- **Approval workflows**: Slack/Teams integration for the validated→production promotion gate
