# 03 — agent_management.snapshot_agent

## Problem

`agent_optimization/v0-baseline/` holds one-off JSON snapshots of agent state taken manually during a tuning session. There's no library API — engineers copy-paste shell commands to create them. With Cortex Agent Versioning landing, the *canonical* snapshot lives in Snowflake (`VERSION$N` + alias). Local snapshots remain useful for offline diff/audit, but must be produced by the library.

## Goal

A library module `agent_management/snapshot_agent.py`:

- `snapshot_agent(agent_fqn, *, version=None, alias=None, out_dir=None) -> Path`
  - If `version` given: reads that version's spec via `DESC AGENT … VERSION <n>` (or `SHOW VERSIONS` + YAML lookup when versioning enabled)
  - If `alias` given: resolves to the version under that alias
  - Default: current LIVE (unversioned or alias=LIVE)
  - Writes `snapshots/<agent>/<timestamp>_<version-or-LIVE>.json` with:
    ```json
    {
      "agent_fqn": "...",
      "snapshot_time": "2026-04-24T…",
      "version": "VERSION$3" | null,
      "aliases": ["production"],
      "spec": { … full spec YAML parsed to JSON … },
      "tools": [ … ],
      "instructions": "…"
    }
    ```
- `load_snapshot(path) -> dict` for diff tools
- `diff_snapshots(a_path, b_path) -> str` unified-diff-like output of spec fields

## CLI

```
python -m agent_management.snapshot_agent --env prod --agent RESORT_EXECUTIVE --alias production
python -m agent_management.snapshot_agent --diff snapshots/.../a.json snapshots/.../b.json
```

## Snapshot directory

`snapshots/` at repo root, **gitignored** (we don't commit snapshots). Users can redirect with `--out-dir`.

## Relationship to versioning

When `agent_versioning.enabled=true`:
- `snapshot_state.py` (already exists) runs *before deploy* and captures `VERSION$N` + aliases, returns a lightweight rollback pointer
- `snapshot_agent.py` produces *rich* JSON artifacts for audit/diff, not for rollback

Don't merge the two — they have different shapes and lifecycles.

## Migration

- Delete `agent_optimization/` (but preserve `v0-baseline/*.json` one-time by copying into `snapshots/v0-baseline/` locally; not committed)
- Add `snapshots/` to `.gitignore`
