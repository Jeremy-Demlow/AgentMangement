# 13 — Test matrix

## New unit tests

| Module | Test file | Cases |
|--------|-----------|-------|
| `smoke_test` | `tests/test_smoke_test.py` | happy path (mocked HTTP), prompt failure, latency timeout, alias-pinned request |
| `snapshot_agent` | `tests/test_snapshot_agent.py` | snapshot from alias, snapshot from explicit version, diff two snapshots, out-dir override |
| `validate_spec_format` | `tests/test_validate_spec_format.py` | missing section, out-of-order sections, hardcoded season string, valid spec returns [] |
| `versioning` | `tests/test_versioning.py` | commit, list versions, set alias, drop version, version_exists probes |
| `deploy_agents` versioned path | `tests/test_deploy_agents_versioned.py` | 4-step SQL sequence emitted in order (with mocked cursor), fallback path when feature disabled |
| `rollback` alias path | `tests/test_rollback_versioned.py` | alias reassignment SQL emitted, fallback to spec-restore on API error |
| `snapshot_state` | `tests/test_snapshot_state_versioned.py` | captures version + alias_before when versioning on; captures full spec when off |
| `env_config.deploy_alias` | `tests/test_env_config.py` | reads alias from yaml; defaults when missing; errors on unknown env |

## Integration tests (manual, not in CI)

`tests/integration/test_versioning_roundtrip.py` (gated by `SNOWFLAKE_INTEGRATION=1` env var):

1. Deploy agent to dev with versioning → VERSION$1 created, alias=latest
2. Deploy again → VERSION$2 created, alias=latest moved
3. Rollback → alias=latest reassigned to VERSION$1
4. Snapshot before rollback captures VERSION$2
5. Drop version cleanup leaves aliased versions intact

## CI wiring

- `pytest tests/` runs all unit tests on every PR
- `pytest tests/integration/` runs on manual workflow dispatch only (requires Snowflake creds + the PP enabled on the account)

## Existing tests that must still pass

- `tests/test_templates.py` — rewritten to call `validate_spec_format`
- `tests/test_detect_sv_drift.py` — unchanged
- `tests/test_deploy_semantic_views.py` — unchanged
