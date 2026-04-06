# GitHub Actions Pipeline Setup

Complete setup guide for all CI/CD workflows in this repository.

## Required GitHub Secrets

Go to **Settings → Secrets and variables → Actions** and add these repository secrets:

| Secret | Used By | Description | Example |
|--------|---------|-------------|---------|
| `SNOWFLAKE_ACCOUNT` | All workflows | Snowflake account identifier | `trb65519` |
| `SNOWFLAKE_USER` | All workflows | Service account or user | `JDEMLOW` |
| `SNOWFLAKE_PRIVATE_KEY` | All except dcm-deploy | PEM-encoded private key (the full file contents, including `-----BEGIN/END-----` headers) | See [Key Pair Auth](#key-pair-auth) |
| `SNOWFLAKE_PRIVATE_KEY_RAW` | dcm-deploy | Same key but used by DCM actions (separate secret name required by the Snowflake DCM reusable actions) | Same value as `SNOWFLAKE_PRIVATE_KEY` |
| `SNOWFLAKE_WAREHOUSE` | All except dcm-deploy | Default compute warehouse | `AM_SKI_RESORT_WH_PROD` |
| `SNOWFLAKE_ROLE` | All except dcm-deploy | Role for CI/CD operations | `AM_DEPLOY_ROLE_PROD` |

### Quick Setup via Scripts

Automated scripts live in `.github/scripts/`. Each script documents exactly what it creates and why.

```bash
# 1. Set all 6 secrets (account, user, key x2, warehouse, role)
.github/scripts/setup_github_secrets.sh

# 2. Create all 4 GitHub environments (DEV, QA, PROD, production)
.github/scripts/setup_github_environments.sh
```

To tear everything down and start fresh:

```bash
.github/scripts/teardown.sh
```

#### What the scripts create

| Script | What it does |
|--------|-------------|
| `setup_github_secrets.sh` | Sets 6 repo secrets: `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PRIVATE_KEY`, `SNOWFLAKE_PRIVATE_KEY_RAW`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_ROLE`. Reads the private key from `~/.snowflake/keys/snowflake_tf_key.p8`. No password needed — all workflows use key-pair (JWT) auth. |
| `setup_github_environments.sh` | Creates 4 GitHub environments: `DEV`, `QA`, `PROD` (no protection), `production` (requires repo owner approval before prod promote runs). |
| `teardown.sh` | Deletes all 6 secrets and all 4 environments. Use to reset before re-running setup. |

All scripts support overrides via environment variables (see script headers for details):

```bash
SNOWFLAKE_KEY_PATH=~/alt_key.p8 GH_REPO=myorg/myrepo .github/scripts/setup_github_secrets.sh
```

## Required GitHub Environments

The `promote-prod.yml` and `dcm-deploy.yml` workflows use [GitHub Environments](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment) for approval gates.

Go to **Settings → Environments** and create:

| Environment | Purpose | Recommended Settings |
|-------------|---------|---------------------|
| `DEV` | DCM deploys to dev | No protection rules needed |
| `QA` | DCM deploys to QA | Optional: require reviewer |
| `PROD` | DCM deploys to prod | Optional: require reviewer |
| `production` | Prod promote pre-flight check | **Required reviewers** (1+), prevents accidental prod deploys |

The `production` environment is referenced by `promote-prod.yml` → `pre-flight` job. Without it, the workflow will fail with a "deployment protection rule" error. If you don't want manual approval, create the environment with no protection rules.

## Key Pair Auth

All deploy/promote/validate workflows use key-pair (JWT) authentication. The workflow writes the key to a temp file, uses it, then cleans up:

```yaml
- name: Write private key
  run: echo "${{ secrets.SNOWFLAKE_PRIVATE_KEY }}" > /tmp/snowflake_key.p8

- name: Cleanup
  if: always()
  run: rm -f /tmp/snowflake_key.p8
```

To generate a key pair if you don't have one:

```bash
# Generate unencrypted private key
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out snowflake_tf_key.p8 -nocrypt

# Extract public key
openssl rsa -in snowflake_tf_key.p8 -pubout -out snowflake_tf_key.pub

# Assign to Snowflake user
# In Snowflake:
#   ALTER USER JDEMLOW SET RSA_PUBLIC_KEY='<contents of .pub file without headers>';
```

The secret value should be the **entire file contents** of the `.p8` file, including the `-----BEGIN PRIVATE KEY-----` and `-----END PRIVATE KEY-----` lines.

## Workflow Overview

| Workflow | File | Trigger | Secrets Used | Env Required |
|----------|------|---------|-------------|-------------|
| **Validate PR** | `validate-pr.yml` | PR to `main` | ACCOUNT, USER, KEY, WH, ROLE | — |
| **Deploy Dev** | `deploy-dev.yml` | Push to `main` (agents/SVs/envs changed) | ACCOUNT, USER, KEY, WH, ROLE | — |
| **Promote QA** | `promote-qa.yml` | Manual dispatch | ACCOUNT, USER, KEY, WH, ROLE | — |
| **Promote Prod** | `promote-prod.yml` | Manual dispatch | ACCOUNT, USER, KEY, WH, ROLE | `production` |
| **Rollback** | `rollback.yml` | Manual dispatch | ACCOUNT, USER, KEY, WH, ROLE | `production` (for prod) |
| **Daily Data Refresh** | `daily_data_refresh.yml` | Cron (5am PST) or manual | ACCOUNT, USER, KEY, WH, ROLE | — |
| **DCM Deploy** | `dcm-deploy.yml` | Push/PR to `main` (dcm/ changed) or manual | USER, KEY_RAW | DEV/QA/PROD |

## Verifying Setup

After setting all secrets, test with the simplest workflow first:

```bash
# 1. Test validate-pr (doesn't modify Snowflake, just lints)
#    Open a PR to main — the workflow should run automatically

# 2. Test DCM plan (read-only)
gh workflow run dcm-deploy.yml -f target=DEV -f plan_only=true

# 3. Test deploy-dev (makes changes)
gh workflow run deploy-dev.yml
```

## Common Failures

| Error | Cause | Fix |
|-------|-------|-----|
| `Failed to connect to DB: 250001` | Bad account, user, or key | Verify `SNOWFLAKE_ACCOUNT` and `SNOWFLAKE_USER`. Test key locally: `snow connection test` |
| `Private key is not in PKCS8 format` | Key format wrong | Re-export: `openssl pkcs8 -topk8 -inform PEM -in key.pem -out key.p8 -nocrypt` |
| `SQL access control error` | Role lacks grants | Run DCM first to create roles/grants, or use `ACCOUNTADMIN` initially |
| `Environment 'production' not found` | Missing GH environment | Create `production` environment in Settings → Environments |
| `SNOWFLAKE_PRIVATE_KEY_RAW not set` | DCM secret missing | Set `SNOWFLAKE_PRIVATE_KEY_RAW` (same value as `SNOWFLAKE_PRIVATE_KEY`) |
| `dbt deps fails` | Key not written to disk | Ensure the `Write private key` step runs before dbt steps |

## Per-Environment Role/Warehouse Strategy

The workflows currently use a single set of secrets (`SNOWFLAKE_ROLE`, `SNOWFLAKE_WAREHOUSE`) for all environments. For production setups, you may want per-environment secrets:

```
SNOWFLAKE_ROLE_DEV=AM_DEPLOY_ROLE_DEV
SNOWFLAKE_ROLE_QA=AM_DEPLOY_ROLE_QA
SNOWFLAKE_ROLE_PROD=AM_DEPLOY_ROLE_PROD

SNOWFLAKE_WAREHOUSE_DEV=AM_SKI_RESORT_WH_DEV
SNOWFLAKE_WAREHOUSE_QA=AM_SKI_RESORT_WH_QA
SNOWFLAKE_WAREHOUSE_PROD=AM_SKI_RESORT_WH_PROD
```

This would require updating the workflow `env:` blocks to reference the correct secret per environment. The current setup works fine when using `ACCOUNTADMIN` or a role that has access to all three databases.

## Optional: Two-Environment Setup (No QA)

QA is optional. To run dev → prod only:

1. Don't trigger `promote-qa.yml`
2. Optionally remove `environments/qa.env.yml` and the `qa:` block from `project.yml`
3. Consider making dev's eval gate stricter (change `continue-on-error: true` to `false` in `deploy-dev.yml` → `sv-eval-gate`)
