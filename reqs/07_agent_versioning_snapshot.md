# 07 — snapshot_state.py: pointer-only capture

## Problem (today)

`snapshot_state.py` writes a snapshot *before deploy* so rollback can re-apply. It captures the full spec YAML — which is redundant once `VERSION$N` preserves specs immutably.

## Goal

`snapshot_state.py` writes a lightweight rollback pointer only:

```json
{
  "agent_fqn": "AM_SKI_RESORT.AGENTS.RESORT_EXECUTIVE",
  "env": "prod",
  "snapshot_time": "2026-04-24T…",
  "version_before": "VERSION$7",
  "alias_before": {
    "validated": "VERSION$7",
    "production": "VERSION$6"
  },
  "all_versions": ["VERSION$1", "...", "VERSION$7"]
}
```

No spec YAML is captured. If a full-spec snapshot is needed for audit, use `agent_management.snapshot_agent` (separate module).

## Snowflake queries

```sql
SHOW VERSIONS ON AGENT <fqn>;
SHOW ALIASES ON AGENT <fqn>;
```

Exact DDL form matches the Private Preview docs; the library probes once per connector and caches.

## API

```python
def snapshot_state(
    agent_fqn: str,
    *,
    env: str,
    out_path: Path | None = None,
) -> SnapshotPointer
```

No `use_versioning` parameter.

## Lifecycle

Called from `deploy_agents.py` immediately before the deploy step. Stored under `.snowflake/ci/snapshots/<env>/<agent>/<timestamp>.json`. The last snapshot per `(env, agent, alias)` is what `rollback.py` reads by default.
