# 06 — Alias-first rollback in rollback.py

## Problem (today)

`rollback.py` reads the last snapshot JSON (`snapshot_state.py`), reconstructs a spec YAML, and re-applies via `CREATE OR ALTER AGENT`. This is:

- Slow (full spec re-apply, re-validation)
- Error-prone (spec JSON round-trip loses comments, risks subtle field reordering)
- Not atomic (if the re-apply fails halfway the agent is in a broken state)

## Goal (target)

Rollback becomes a single SQL statement:

```sql
ALTER AGENT <fqn> MODIFY VERSION <target_version> SET ALIAS = <deploy_alias>;
```

Where `<target_version>` is read from the snapshot pointer captured by `snapshot_state.py` *before the last deploy*.

## API

```python
def rollback_agent(
    agent_fqn: str,
    *,
    env: str,
    target_version: str | None = None,   # VERSION$N; default = last snapshot's version_before
    deploy_alias: str,                   # alias to move back
    use_versioning: bool,
    fallback_to_spec_restore: bool = True,
) -> RollbackResult
```

## Fallback

When versioning is off or the API call fails:

1. Read the snapshot JSON
2. Restore the spec via `CREATE OR ALTER AGENT`
3. Log which path was used

`fallback_to_spec_restore=False` disables this (strict mode for tests).

## Safety checks

Before flipping the alias:

1. `version_exists(agent_fqn, target_version)` — fail if not
2. `get_alias(agent_fqn, deploy_alias)` — log current alias holder
3. Confirm target_version ≠ current alias target (no-op guard)

## CLI

```
python -m agent_management.rollback --env prod --agent RESORT_EXECUTIVE
# rolls production alias back to version_before from latest snapshot

python -m agent_management.rollback --env prod --agent RESORT_EXECUTIVE --to VERSION$5
# explicit target
```

## Diagram

See `diagrams/04_rollback_flow_versioned.txt`.
