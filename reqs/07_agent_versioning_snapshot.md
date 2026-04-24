# 07 — snapshot_state.py captures version + alias

## Problem (today)

`snapshot_state.py` writes a snapshot *before deploy* so rollback can re-apply. It currently captures the full spec YAML (via `DESC AGENT`). With versioning, this is wasted work — the spec is preserved in `VERSION$N` already.

## Goal

`snapshot_state.py` output, when `agent_versioning.enabled=true`, is a lightweight rollback pointer:

```json
{
  "agent_fqn": "AM_SKI_RESORT.AGENTS.RESORT_EXECUTIVE",
  "env": "prod",
  "snapshot_time": "2026-04-24T…",
  "versioning_enabled": true,
  "version_before": "VERSION$7",
  "alias_before": {
    "production": "VERSION$7",
    "validated": "VERSION$8"
  },
  "all_versions": ["VERSION$1", …, "VERSION$8"]
}
```

When versioning is off, it falls back to today's full-spec snapshot.

## Snowflake queries

```sql
SHOW VERSIONS ON AGENT <fqn>;
SHOW ALIASES ON AGENT <fqn>;
```

(exact DDL matches the Private Preview docs; add `SHOW VERSIONS IN AGENT` if that's the correct form; library should probe both and cache)

## API

```python
def snapshot_state(
    agent_fqn: str,
    *,
    env: str,
    use_versioning: bool,
    out_path: Path | None = None,
) -> SnapshotPointer
```

## Lifecycle

Called from `deploy_agents.py` immediately before the deploy step. Stored under `.snowflake/ci/snapshots/<env>/<agent>/<timestamp>.json`. The last snapshot per (env, agent) is what `rollback.py` reads by default.
