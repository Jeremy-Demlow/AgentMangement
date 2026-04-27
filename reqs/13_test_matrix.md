# 13 — Test matrix (versioning-only)

## New unit tests

| Module | Test file | Cases |
|--------|-----------|-------|
| `smoke_test` | `tests/test_smoke_test.py` | happy path (mocked HTTP), prompt failure, latency timeout, alias-pinned request |
| `snapshot_agent` | `tests/test_snapshot_agent.py` | snapshot from alias, from explicit version, diff two snapshots, out-dir override |
| `validate_spec_format` | `tests/test_validate_spec_format.py` | missing section, out-of-order sections, hardcoded season string, valid spec returns [] |
| `versioning` | `tests/test_versioning.py` | commit (4-step SQL order), list versions, set alias, drop version (skips aliased), version_exists |
| `deploy_agents` (versioned) | `tests/test_deploy_agents.py` | emits ADD LIVE FROM LAST → MODIFY LIVE SPEC → COMMIT → SET ALIAS in order; DropPolicy keeps aliased versions; raises on SQL error (no fallback) |
| `rollback` (alias) | `tests/test_rollback.py` | alias reassignment SQL emitted; raises when target_version missing; no-op guard |
| `snapshot_state` | `tests/test_snapshot_state.py` | pointer captures version + aliases; no spec YAML in pointer |
| `env_config` | `tests/test_env_config.py` | dev + prod loaders, alias list parsed, unknown env raises |

## Integration test (manual)

`tests/integration/test_versioning_roundtrip.py` (gated by `SNOWFLAKE_INTEGRATION=1`):

1. Deploy agent to dev → VERSION$1, alias=latest
2. Deploy again → VERSION$2, alias=latest moved
3. Rollback (alias=latest → VERSION$1)
4. Snapshot captures VERSION$2 before rollback
5. Drop version cleanup leaves aliased versions intact

## CI wiring

- `pytest tests/` runs all unit tests on every PR.
- `pytest tests/integration/` gated by env var; not in default CI.

## Existing tests

- `tests/test_templates.py` → rewritten as a thin wrapper around `validate_spec_format`.
- `tests/test_detect_sv_drift.py` — unchanged.
- `tests/test_deploy_semantic_views.py` — unchanged.
- Any test that touched QA env — deleted or updated to use `prod`.

## What we explicitly do NOT test

- Legacy `CREATE OR ALTER AGENT` spec-apply path — it no longer exists.
- Feature-flag on/off branching — there is no flag.
