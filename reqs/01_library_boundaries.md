# 01 — Library boundaries

## Problem

We drifted. `framework/`, `agent_optimization/`, and `test_agents_live.py` are parallel to the library. They use the same Snowflake connection helpers, same spec files, same SVs — but they live outside `agent_management/` and are invoked as loose scripts.

## Goal

`agent_management/` is the single Python package. Everything consumable by a developer or CI job is:

```
from agent_management import X
```

or

```
python -m agent_management.<module> --args
```

## Module inventory (target)

```
agent_management/
  __init__.py                  — re-exports public API
  paths.py                     — repo path helpers
  utils/                       — connection, logging, yaml loaders
  ci/                          — CI entrypoints

  # existing
  deploy_agents.py             — single path: versioned
  deploy_semantic_views.py
  deploy_svs_yaml.py
  rollback.py                  — single path: alias reassignment
  detect_drift.py
  detect_sv_drift.py
  snapshot_state.py            — pointer-only (version + aliases)
  sync_vqrs_to_dbt.py
  validate_specs.py
  render_template.py
  render_eval_templates.py
  run_sv_eval.py
  run_ci_eval.py
  check_sv_eval.py
  check_sv_evals.py
  check_qa_recency.py
  compute_metrics.py
  get_sv_eval_scores.py

  # NEW in this refactor
  smoke_test.py                — replaces test_agents_live.py
  snapshot_agent.py            — replaces agent_optimization/
  validate_spec_format.py      — extracted from tests/test_templates.py

  # NEW for versioning
  versioning.py                — ALTER AGENT COMMIT / aliases / VERSION$N helpers
```

## Deletions

- `test_agents_live.py` at repo root
- `agent_optimization/` directory (content moves into `agent_management/snapshot_agent.py` + `snapshots/` dir that is gitignored)
- `framework/` stays on disk but is gitignored (content moves into `CONTRIBUTING.md` / `docs/`)
- Legacy `CREATE OR ALTER AGENT` spec-apply code paths in `deploy_agents.py` and `rollback.py`

## Public API (new `__init__.py` exports)

```python
from agent_management.smoke_test import run_smoke_test
from agent_management.snapshot_agent import snapshot_agent, load_snapshot, diff_snapshots
from agent_management.validate_spec_format import validate_spec_format
from agent_management.versioning import (
    commit_version, list_versions, get_aliases,
    set_alias, drop_version, version_exists,
)
from agent_management.deploy_agents import deploy_agent
from agent_management.rollback import rollback_agent
```

All callables use keyword-only env parameters and take an explicit Snowflake connector rather than opening one themselves (makes them test-friendly).

## No fallback / no flag

There is **no** `use_versioning` argument, **no** `fallback_to_spec_restore` argument, **no** `agent_versioning.enabled` flag. Versioning is the only path. If the Cortex Agent Versioning Private Preview is not enabled on the account, deploy/rollback will fail loudly at the SQL layer — which is correct behavior for a repo whose contract is versioning.

## Non-goals

- Not refactoring `dbt_ski_resort/` (dbt project is separate)
- Not rewriting `deploy_semantic_views.py` — already library-shaped
- Not publishing `framework/` docs externally yet
