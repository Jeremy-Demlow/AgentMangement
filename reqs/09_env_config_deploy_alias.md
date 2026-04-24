# 09 — `agent.deploy_alias` in environment YAMLs

## Problem

`environments/dev.env.yml`, `qa.env.yml`, `prod.env.yml` describe the target DB/schema/warehouse/role per env but don't declare which *alias* the agent deploy should advance. Today that's implicit (always the live spec); with versioning, it must be explicit per env.

## Goal

Add `agent.deploy_alias` to each env file:

```yaml
# environments/dev.env.yml
agent:
  deploy_alias: latest
  fqns:
    resort_executive: AM_SKI_RESORT_DEV.AGENTS.RESORT_EXECUTIVE_DEV
    ski_ops_assistant: AM_SKI_RESORT_DEV.AGENTS.SKI_OPS_ASSISTANT_DEV

# environments/qa.env.yml
agent:
  deploy_alias: validated
  fqns:
    resort_executive: AM_SKI_RESORT_QA.AGENTS.RESORT_EXECUTIVE_QA
    ski_ops_assistant: AM_SKI_RESORT_QA.AGENTS.SKI_OPS_ASSISTANT_QA

# environments/prod.env.yml
agent:
  deploy_alias: production
  fqns:
    resort_executive: AM_SKI_RESORT.AGENTS.RESORT_EXECUTIVE
    ski_ops_assistant: AM_SKI_RESORT.AGENTS.SKI_OPS_ASSISTANT
```

## Loader change

`agent_management/utils/env_config.py` (or equivalent) exposes:

```python
load_env_config(env: str) -> EnvConfig
# EnvConfig has .agent.deploy_alias, .agent.fqns, .database, .schema, …
```

Callers that need the alias: `deploy_agents.py`, `rollback.py`, `promote-prod.yml`, `rollback.yml`.

## Defaults

If `agent.deploy_alias` missing in the YAML, the library picks based on env name:

| env contains | default alias |
|--------------|---------------|
| `dev`  | `latest` |
| `qa`   | `validated` |
| `prod` | `production` |

Missing env name → error.
