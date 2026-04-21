# GitHub Actions Pipeline Setup

Complete setup guide for all CI/CD workflows in this repository.

## Secrets & Variables Architecture

Credentials are split between **repo-level secrets** (sensitive) and **environment-level variables** (non-sensitive):

> **Why variables, not secrets?** GitHub masks any secret value wherever it appears in log output.
> Database names, roles, and warehouses are not sensitive — masking them breaks Snowsight URLs
> and makes CI logs harder to read. Only truly sensitive values use secrets.

### Repo-Level Secrets (4)

Go to **Settings → Secrets and variables → Actions → Repository secrets**:

| Secret | Description | Example |
|--------|-------------|---------|
| `SNOWFLAKE_ACCOUNT` | Snowflake account identifier | Your account locator (e.g., `abc12345`) |
| `SNOWFLAKE_USER` | Service account or user | `JDEMLOW` |
| `SNOWFLAKE_PRIVATE_KEY` | PEM-encoded private key (full file contents including headers) | See [Key Pair Auth](#key-pair-auth) |
| `SNOWFLAKE_PRIVATE_KEY_RAW` | Same key (required by DCM reusable actions) | Same as above |

### Environment-Level Variables (3 per environment)

Go to **Settings → Environments → [env name] → Environment variables**:

| Variable | DEV | QA | PROD / production |
|----------|-----|-----|-------------------|
| `SNOWFLAKE_WAREHOUSE` | `AM_SKI_RESORT_WH_DEV` | `AM_SKI_RESORT_WH_QA` | `AM_SKI_RESORT_WH` |
| `SNOWFLAKE_ROLE` | `AM_DEPLOY_ROLE_DEV` | `AM_DEPLOY_ROLE_QA` | `AM_DEPLOY_ROLE` |
| `SNOWFLAKE_DATABASE` | `AM_SKI_RESORT_DEV` | `AM_SKI_RESORT_QA` | `AM_SKI_RESORT` |

Each workflow job declares `environment: DEV` (or QA/PROD/production), and `${{ vars.SNOWFLAKE_WAREHOUSE }}` resolves to the correct environment-specific value.

### Quick Setup via Scripts

```bash
# 1. Create all 4 GitHub environments (DEV, QA, PROD, production)
.github/scripts/setup_github_environments.sh

# 2. Set 4 repo secrets + 12 environment variables (3 per env x 4 envs)
.github/scripts/setup_github_secrets.sh
```

To tear everything down and start fresh:

```bash
.github/scripts/teardown.sh
```

#### What the scripts create

| Script | What it does |
|--------|-------------|
| `setup_github_environments.sh` | Creates 4 GitHub environments: `DEV`, `QA`, `PROD` (no protection), `production` (requires repo owner approval). |
| `setup_github_secrets.sh` | Sets 4 repo secrets + 3 environment variables per env (DEV/QA/PROD/production = 16 total). Reads the private key from `~/.snowflake/keys/snowflake_tf_key.p8`. All workflows use key-pair (JWT) auth. |
| `teardown.sh` | Deletes all repo secrets, environment variables, and environments. |

All scripts support overrides via environment variables (see script headers for details):

```bash
SNOWFLAKE_KEY_PATH=~/alt_key.p8 GH_REPO=myorg/myrepo .github/scripts/setup_github_secrets.sh
```

## Required GitHub Environments

Go to **Settings → Environments** and create:

| Environment | Used By | Purpose | Protection |
|-------------|---------|---------|------------|
| `DEV` | `deploy-dev.yml` | Auto-deploy on push to main | None |
| `QA` | `promote-qa.yml` | Manual promote to QA | None (optional: add reviewer) |
| `PROD` | `promote-prod.yml`, `daily_data_refresh.yml` | Deploy + eval jobs | None |
| `production` | `promote-prod.yml` (pre-flight job) | Approval gate before prod deploy | **Required reviewer** |

The `production` environment gates the first job in `promote-prod.yml`. Without it, the workflow fails with a "deployment protection rule" error.

## Key Pair Auth

All workflows use key-pair (JWT) authentication. The workflow writes the key to a temp file, uses it, then cleans up:

```yaml
- name: Write private key
  run: echo "${{ secrets.SNOWFLAKE_PRIVATE_KEY }}" > /tmp/snowflake_key.p8

- name: Cleanup
  if: always()
  run: rm -f /tmp/snowflake_key.p8
```

To generate a key pair:

```bash
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out snowflake_tf_key.p8 -nocrypt
openssl rsa -in snowflake_tf_key.p8 -pubout -out snowflake_tf_key.pub

# In Snowflake:
#   ALTER USER JDEMLOW SET RSA_PUBLIC_KEY='<contents of .pub file without headers>';
```

## Workflow Overview

| Workflow | File | Trigger | Environment |
|----------|------|---------|-------------|
| **Deploy Dev** | `deploy-dev.yml` | Push to `dev` (agents/SVs/envs changed) | `DEV` |
| **Deploy QA (auto)** | `deploy-qa-on-main.yml` | Push to `main` | `QA` |
| **Promote QA** | `promote-qa.yml` | Manual dispatch | `QA` |
| **Promote Prod** | `promote-prod.yml` | Manual dispatch | `production` (pre-flight) + `PROD` |
| **Daily Data Refresh** | `daily_data_refresh.yml` | Cron (5am PST) or manual | `PROD` |
| **Validate PR** | `validate-pr.yml` | PR to `main` | — |
| **Rollback** | `rollback.yml` | Manual dispatch | `production` (for prod) |
| **DCM Deploy** | `dcm-deploy.yml` | Push/PR to `main` (dcm/ changed) | `DEV`/`QA`/`PROD` |

## Pipeline Stage Ordering

All deployment workflows follow this stage order:

```
snapshot → deploy-svs → sv-eval-gate → deploy-agents → agent-eval-gate
```

The SV eval gate runs **after** semantic views are deployed but **before** agents are deployed.
This ensures agents are never deployed against semantic views that fail evaluation.

| Environment | SV Eval Gate | Agent Eval Gate |
|-------------|-------------|-----------------|
| DEV | Advisory (`continue-on-error: true`) | Advisory |
| QA | Hard gate (blocks agent deploy) | Hard gate |
| PROD | Hard gate (triggers rollback on failure) | Hard gate (triggers rollback on failure) |

## SV Eval Configuration

### Agent-to-SV Mapping (`project.yml`)

Define which semantic views each agent uses in `project.yml`:

```yaml
agents:
  resort_executive:
    semantic_views:
      - SEM_DAILY_SUMMARY
      - SEM_REVENUE
      - SEM_OPERATIONS
  ski_ops_assistant:
    semantic_views:
      - SEM_OPERATIONS
      - SEM_STAFFING_ANALYTICS
```

This mapping enables scoped evaluation — when an agent changes, only its SVs are tested.

### SV Eval Stage Config (`project.yml`)

```yaml
eval:
  sv_eval:
    stage: sv_eval_stage          # Stage in SEMANTIC schema for eval configs
    file_format: yaml_file_format # File format for eval YAML upload
    default_scope: all            # "all" or "agent" — default eval scope
```

### Running SV Evaluations

```bash
# Evaluate all semantic views
python -m agent_management.run_sv_eval --env prod

# Evaluate a single SV
python -m agent_management.run_sv_eval --env prod --sv SEM_REVENUE

# Evaluate only SVs used by a specific agent
python -m agent_management.run_sv_eval --env prod --agent ski_ops_assistant

# Dry run (show config without executing)
python -m agent_management.run_sv_eval --env dev --dry-run

# Check status of a running eval
python -m agent_management.run_sv_eval --env prod --status --run-name "CI-abc123"

# Fetch results of a completed eval
python -m agent_management.run_sv_eval --env prod --results --run-name "CI-abc123"
```

## Local Testing

Use `test_workflow_locally.sh` to run workflow steps locally before pushing to CI:

```bash
# Run all steps against DEV
TARGET_ENV=dev .github/scripts/test_workflow_locally.sh

# Run a single step
TARGET_ENV=dev .github/scripts/test_workflow_locally.sh snapshot

# Override python/dbt paths
PYTHON=/path/to/python DBT=/path/to/dbt TARGET_ENV=dev .github/scripts/test_workflow_locally.sh
```

The script force-sets `SNOWFLAKE_DATABASE`, `SNOWFLAKE_ROLE`, and `SNOWFLAKE_WAREHOUSE` to avoid IDE environment contamination.

## Verifying Setup

```bash
# Check repo secrets
gh secret list

# Check environment variables
gh variable list --env DEV
gh variable list --env QA
gh variable list --env PROD

# Test the simplest workflow first
gh workflow run deploy-dev.yml
```

## Common Failures

| Error | Cause | Fix |
|-------|-------|-----|
| `Failed to connect to DB: 250001` | Bad account, user, or key | Verify `SNOWFLAKE_ACCOUNT` and `SNOWFLAKE_USER` |
| `Private key is not in PKCS8 format` | Key format wrong | `openssl pkcs8 -topk8 -inform PEM -in key.pem -out key.p8 -nocrypt` |
| `SQL access control error` | Role lacks grants | Check environment variables point to correct role |
| `Environment 'production' not found` | Missing GH environment | Run `setup_github_environments.sh` |
| `SNOWFLAKE_WAREHOUSE` is empty | Missing env variable | Job needs `environment:` declaration + env-level variable set |
| `DATASCIENCE.RAW` in dbt errors | IDE env contamination | Force-set `SNOWFLAKE_DATABASE` or use `test_workflow_locally.sh` |
| `dbt source tests fail` | Deploy role can't create test schema | Use `dbt run` not `dbt build` in deploy workflows |

## Optional: Two-Environment Setup (No QA)

QA is optional. To run dev → prod only:

1. Don't trigger `promote-qa.yml`
2. Optionally remove `environments/qa.env.yml` and the `qa:` block from `project.yml`
3. Consider making dev's eval gate stricter (`continue-on-error: false` in `deploy-dev.yml` → `sv-eval-gate`)
