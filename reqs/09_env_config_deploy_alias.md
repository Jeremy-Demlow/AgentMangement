# 09 — Env config for Option B (DEV + PROD only)

## Problem

Today we have three env YAMLs (`dev.env.yml`, `qa.env.yml`, `prod.env.yml`). With Option B, QA is collapsed into a `validated` alias on the PROD agent.

## Goal

Two env files. Prod declares both aliases it manages.

### `environments/dev.env.yml`

```yaml
snowflake:
  database: AM_SKI_RESORT_DEV
  semantic_schema: AM_SKI_RESORT_DEV.PUBLIC
  role: AM_DEPLOY_ROLE_DEV
  warehouse: AM_SKI_RESORT_WH_DEV
agent:
  deploy_alias: latest
  aliases: [latest]
  fqns:
    resort_executive: AM_SKI_RESORT_DEV.AGENTS.RESORT_EXECUTIVE_DEV
    ski_ops_assistant: AM_SKI_RESORT_DEV.AGENTS.SKI_OPS_ASSISTANT_DEV
```

### `environments/prod.env.yml`

```yaml
snowflake:
  database: AM_SKI_RESORT
  semantic_schema: AM_SKI_RESORT.PUBLIC
  role: AM_DEPLOY_ROLE
  warehouse: AM_SKI_RESORT_WH
agent:
  # alias moved by the deploy-prod-validated workflow on main merge
  deploy_alias: validated
  # aliases this env manages; `production` is moved by promote workflow only
  aliases: [validated, production]
  fqns:
    resort_executive: AM_SKI_RESORT.AGENTS.RESORT_EXECUTIVE
    ski_ops_assistant: AM_SKI_RESORT.AGENTS.SKI_OPS_ASSISTANT
```

### Delete

- `environments/qa.env.yml`
- Any references to `AM_SKI_RESORT_QA`, `RESORT_EXECUTIVE_QA`, `SKI_OPS_ASSISTANT_QA`, `AM_DEPLOY_ROLE_QA`, `AM_SKI_RESORT_WH_QA` in the codebase.

## Loader

`agent_management/utils/env_config.py` exposes:

```python
load_env_config(env: Literal["dev", "prod"]) -> EnvConfig
# EnvConfig: .snowflake, .agent (with .deploy_alias, .aliases, .fqns)
```

Unknown env name raises. No implicit defaults based on env name.

## Promote vs deploy

- `deploy_agent(..., deploy_alias="validated")` in prod commits a new version and moves `validated` to it.
- Promotion is a separate call: `versioning.set_alias(fqn, version, "production")` run by the approval-gated workflow, reading the version currently under `validated`.
