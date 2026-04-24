# reqs/ — Subsystem requirements for the library refactor + agent versioning

This folder captures the design targets for two overlapping workstreams:

1. **Library-first refactor** — fold parallel structures (`framework/`, `agent_optimization/`, `test_agents_live.py`) into the `agent_management/` library as first-class modules + CLIs.
2. **Cortex Agent Versioning adoption (Private Preview)** — switch deploy, rollback, snapshot, and eval to use `ALTER AGENT COMMIT` + aliases (`production`, `dev`) instead of full spec re-apply on every change.

A subagent should be able to read this folder top-to-bottom and independently re-derive the changes required across code, workflows, and docs.

## Execution order

| # | File | What it specifies |
|---|------|------------------|
| 00 | `diagrams/00_overall_architecture.txt` | Big picture: repo → CI → Snowflake → consumers |
| 01 | `01_library_boundaries.md` | Where code lives; what `agent_management` exposes |
| 02 | `02_smoke_test.md` | `agent_management.smoke_test` module + CLI |
| 03 | `03_snapshot_agent.md` | `agent_management.snapshot_agent` module + CLI |
| 04 | `04_validate_spec_format.md` | `agent_management.validate_spec_format` module |
| 05 | `05_agent_versioning_deploy.md` | Versioned deploy path in `deploy_agents.py` |
| 06 | `06_agent_versioning_rollback.md` | Alias-first rollback in `rollback.py` |
| 07 | `07_agent_versioning_snapshot.md` | `snapshot_state.py` captures version + alias |
| 08 | `08_agent_versioning_eval.md` | Version-targeted eval in `run_eval.py` |
| 09 | `09_env_config_deploy_alias.md` | `agent.deploy_alias` in environment YAMLs |
| 10 | `10_feature_flag.md` | `agent_versioning.enabled` flag + fallback behavior |
| 11 | `11_workflows_diff.md` | GitHub Actions workflow diff for versioned world |
| 12 | `12_docs_integration.md` | Fold `framework/*.md` into `CONTRIBUTING.md` + `docs/` |
| 13 | `13_test_matrix.md` | Unit + integration tests per new module |

## Diagrams

| # | File | What it shows |
|---|------|--------------|
| 00 | `diagrams/00_overall_architecture.txt` | Repo → CI → Snowflake topology |
| 01 | `diagrams/01_deploy_flow_today.txt` | Current deploy flow (spec re-apply) |
| 02 | `diagrams/02_deploy_flow_versioned.txt` | Target: COMMIT + alias reassignment |
| 03 | `diagrams/03_rollback_flow_today.txt` | Current rollback (re-apply old spec) |
| 04 | `diagrams/04_rollback_flow_versioned.txt` | Target: `MODIFY VERSION … SET ALIAS` |
| 05 | `diagrams/05_env_agent_matrix.txt` | env × agent × alias × version matrix |
| 06 | `diagrams/06_library_module_map.txt` | `agent_management/*` module responsibilities |
| 07 | `diagrams/07_feature_flag_decision.txt` | Runtime decision tree for `agent_versioning.enabled` |
| 08 | `diagrams/08_ci_pipeline.txt` | PR → QA → PROD pipeline with versioning gates |

## Guiding principles

- **Library is the product.** Every capability is importable via `from agent_management import …`. CLIs are thin wrappers.
- **No parallel trees.** `framework/` and `agent_optimization/` do not ship.
- **Versioning is feature-flagged.** Deploys, rollbacks, and snapshots all branch on `agent_versioning.enabled`; legacy path stays until GA.
- **Rollback is one SQL statement.** `ALTER AGENT <fqn> MODIFY VERSION <n> SET ALIAS = production`.
- **Eval pins a version.** QA evals the candidate version *before* alias flips to production.
