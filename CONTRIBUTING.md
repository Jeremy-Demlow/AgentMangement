# Contributing

## Development Workflow

```
feature-branch  →  PR to dev   →  validate-pr (dry-run)
                    merge to dev →  deploy-dev.yml (real deploy to DEV, evals advisory)
dev             →  PR to main  →  validate-pr (dry-run)
                    merge to main → (code is "released")
                    manual dispatch → promote-qa.yml / promote-prod.yml
```

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
| `validate-specs` | Validates YAML specs for all three environments |
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

### 6. Merge dev to main → Promote to QA

When DEV looks good, open a PR from `dev` to `main` and merge. Then trigger **Promote to QA** manually from the Actions tab. This runs pre-flight checks, snapshots, deploys, and runs evaluations. QA eval failures are hard failures.

### 7. Promote to Production

Trigger **Promote to Production** manually. Requires reviewer approval (the `production` environment has a protection rule). If post-deploy evals fail, auto-rollback kicks in.

## CI/CD Pipeline Architecture

```
PR opened (to dev or main)  →  validate-pr.yml      (dry-run only, no side effects)
Merge to dev               →  deploy-dev.yml       (real deploy, evals advisory)
Manual dispatch            →  promote-qa.yml       (real deploy, evals required)
Manual dispatch            →  promote-prod.yml     (approval gate, auto-rollback on failure)
Manual dispatch   →  rollback.yml         (any env, from snapshot)
Scheduled daily   →  daily_data_refresh   (PROD data pipeline)
Manual dispatch   →  dcm-deploy.yml       (infrastructure changes)
```

## Environment Mapping

| Input value | GitHub Environment | Snowflake Database | Snowflake Role |
|-------------|-------------------|-------------------|----------------|
| `dev` | `DEV` | `AM_SKI_RESORT_DEV` | `AM_DEPLOY_ROLE_DEV` |
| `qa` | `QA` | `AM_SKI_RESORT_QA` | `AM_DEPLOY_ROLE_QA` |
| `prod` | `production` (with approval) or `PROD` | `AM_SKI_RESORT` | `AM_DEPLOY_ROLE` |

## Secrets Architecture

- **Repo-level**: `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PRIVATE_KEY`
- **Environment-level** (per DEV/QA/PROD/production): `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_ROLE`, `SNOWFLAKE_DATABASE`

Every job that connects to Snowflake declares `environment:` to pull the correct secrets.

## Evaluation Strategy

| Environment | Eval behavior | On failure |
|-------------|--------------|------------|
| DEV | `continue-on-error: true` | Advisory — logged, not blocking |
| QA | Hard failure | Deploy blocked |
| PROD | Hard failure | Auto-rollback from snapshot |

All evals go through `python -m agent_management.run_ci_eval --env <env>` which handles agent name suffix resolution.

## Agent Naming

Single-account mode uses suffixes:

| Environment | Agent name |
|-------------|-----------|
| DEV | `RESORT_EXECUTIVE_DEV` |
| QA | `RESORT_EXECUTIVE_QA` |
| PROD | `RESORT_EXECUTIVE` (no suffix) |

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
- **Approval workflows**: Slack/Teams integration for QA→PROD promotion gates
