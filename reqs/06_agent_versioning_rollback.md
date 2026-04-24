# 06 — Alias-only rollback in rollback.py

## Problem (today)

`rollback.py` reads the last snapshot JSON (`snapshot_state.py`), reconstructs a spec YAML, and re-applies via `CREATE OR ALTER AGENT`. This is slow, error-prone, and not atomic.

## Goal (target — single code path)

Rollback is one SQL statement:

```sql
ALTER AGENT <fqn> MODIFY VERSION <target_version> SET ALIAS = <deploy_alias>;
```

Where `<target_version>` is read from the snapshot pointer captured by `snapshot_state.py` *before the last deploy*. There is no spec-restore fallback.

## API

```python
def rollback_agent(
    agent_fqn: str,
    *,
    env: str,
    deploy_alias: str,                   # alias to move back
    target_version: str | None = None,   # VERSION$N; default = last snapshot's version_before
) -> RollbackResult
```

## Safety checks

Before flipping the alias:

1. `version_exists(agent_fqn, target_version)` — fail if not
2. `get_aliases(agent_fqn)` — log current alias holder
3. Confirm `target_version` ≠ current alias target (no-op guard)

Any check failure raises; no silent fallback.

## CLI

```
python -m agent_management.rollback --env prod --agent RESORT_EXECUTIVE --alias production
# rolls `production` back to version_before from the latest snapshot

python -m agent_management.rollback --env prod --agent RESORT_EXECUTIVE --alias production --to VERSION$5
# explicit target
```

## Diagram

See `diagrams/04_rollback_flow_versioned.txt`.
