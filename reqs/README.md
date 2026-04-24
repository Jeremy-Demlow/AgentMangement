# reqs/ — Subsystem requirements for the library refactor + agent versioning

This folder captures the design targets for two overlapping workstreams:

1. **Library-first refactor** — fold parallel structures (`framework/`, `agent_optimization/`, `test_agents_live.py`) into the `agent_management/` library as first-class modules + CLIs.
2. **Cortex Agent Versioning adoption (Option B, versioning-only)** — one DEV env (iteration), one PROD env with two aliases (`validated`, `production`). No QA env. No legacy code path. No feature flag. Single human approval gate on the `validated -> production` alias flip.

A subagent should be able to read this folder top-to-bottom and independently re-derive the changes required across code, workflows, and docs.

## Execution order

| # | File | What it specifies |
|---|------|------------------|
| 00 | `diagrams/00_overall_architecture.txt` | Big picture: repo → CI → Snowflake → consumers |
| 01 | `01_library_boundaries.md` | Where code lives; what `agent_management` exposes |
| 02 | `02_smoke_test.md` | `agent_management.smoke_test` module + CLI |
| 03 | `03_snapshot_agent.md` | `agent_management.snapshot_agent` module + CLI |
| 04 | `04_validate_spec_format.md` | `agent_management.validate_spec_format` module |
| 05 | `05_agent_versioning_deploy.md` | Versioned deploy path in `deploy_agents.py` (single code path) |
| 06 | `06_agent_versioning_rollback.md` | Alias-only rollback in `rollback.py` |
| 07 | `07_agent_versioning_snapshot.md` | `snapshot_state.py` pointer-only capture |
| 08 | `08_agent_versioning_eval.md` | Version / alias targeted eval in `run_eval.py` |
| 09 | `09_env_config_deploy_alias.md` | DEV + PROD env files; `prod.env.yml` carries two aliases |
| 11 | `11_workflows_diff.md` | GitHub Actions workflows for 2-env + one approval model |
| 12 | `12_docs_integration.md` | Fold `framework/*.md` into `CONTRIBUTING.md` + `docs/` |
| 13 | `13_test_matrix.md` | Unit + integration tests per new module |

> Note: there is intentionally no `10_feature_flag.md`. Versioning is mandatory and has no runtime opt-out. Accounts without Cortex Agent Versioning Private Preview enabled cannot deploy — there is no fallback path.

## Diagrams

| # | File | What it shows |
|---|------|--------------|
| 00 | `diagrams/00_overall_architecture.txt` | Repo → CI → Snowflake topology (2-env) |
| 02 | `diagrams/02_deploy_flow_versioned.txt` | Deploy: ADD LIVE FROM LAST → MODIFY LIVE SPEC → COMMIT → SET ALIAS |
| 04 | `diagrams/04_rollback_flow_versioned.txt` | Rollback: `MODIFY VERSION … SET ALIAS` (single statement) |
| 05 | `diagrams/05_env_agent_matrix.txt` | DEV + PROD × agent × alias × version matrix |
| 06 | `diagrams/06_library_module_map.txt` | `agent_management/*` module responsibilities |
| 08 | `diagrams/08_ci_pipeline.txt` | Branch → DEV → main merge → PROD `validated` → approval → PROD `production` |

> Note: `01_deploy_flow_today.txt`, `03_rollback_flow_today.txt`, and `07_feature_flag_decision.txt` have been removed — they described the legacy path / feature flag, which no longer exist in the design.

## Guiding principles

- **Library is the product.** Every capability is importable via `from agent_management import …`. CLIs are thin wrappers.
- **No parallel trees.** `framework/` and `agent_optimization/` do not ship.
- **Versioning is mandatory.** No runtime fallback; no feature flag.
- **2 envs only.** DEV for dbt/SV iteration and developer smoke, PROD for customer traffic and internal validation via `validated` alias.
- **Rollback is one SQL statement.** `ALTER AGENT <fqn> MODIFY VERSION <n> SET ALIAS = production`.
- **Eval pins an alias.** CI evals `<fqn>!validated` before a human flips `production`.
- **One approval gate.** GitHub `production-promote` environment approves the alias flip to `production`; no other human gates.
