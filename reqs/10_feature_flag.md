# 10 — Feature flag for Cortex Agent Versioning

## Why

Cortex Agent Versioning is Private Preview. We can't guarantee the feature is enabled on every Snowflake account that clones this repo. We need a flag that:

1. Turns the whole versioning code path on/off
2. Falls back to the legacy deploy/rollback when off
3. Lets us flip envs independently (dev on, prod off) during rollout

## `project.yml` addition

```yaml
agent_versioning:
  enabled: true              # master switch
  per_env:
    dev: true
    qa: true
    prod: false              # flip to true once GA
  fallback_to_spec_restore: true
  keep_last_n_versions: 10
  aliases:                   # canonical alias names (informational)
    - latest
    - validated
    - production
```

## Runtime decision

```python
def versioning_enabled(env: str, cfg: dict) -> bool:
    if not cfg["agent_versioning"]["enabled"]:
        return False
    return cfg["agent_versioning"]["per_env"].get(env, False)
```

Every `deploy_agents`, `rollback`, `snapshot_state`, `run_eval` call reads this and branches.

## Fallback behavior

When versioning is disabled for an env:
- Deploy: legacy `CREATE OR ALTER AGENT` (today's behavior)
- Rollback: snapshot-restore
- Snapshot: full spec YAML capture
- Eval: live spec only

All code paths must test-pass in both modes.

## Diagram

See `diagrams/07_feature_flag_decision.txt`.
