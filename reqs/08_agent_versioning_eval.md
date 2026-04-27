# 08 — Version / alias targeted eval in run_eval.py

## Problem (today)

`agent-evaluation/scripts/run_eval.py` evals "the current agent" — whatever is live at the FQN. With versioning, we need to eval *a specific candidate version* before flipping the `production` alias.

## Goal

Mandatory `--alias` (or `--version`) for CI eval runs so the eval target is explicit and reproducible.

## Snowflake API

Per Private Preview docs, agent invocations take a selector:

- `<fqn>!LIVE`, `<fqn>!FIRST`, `<fqn>!LAST`, `<fqn>!DEFAULT`
- `<fqn>!<alias_name>` (e.g., `RESORT_EXECUTIVE!validated`)
- `<fqn>!VERSION$3` (if supported by the API)

Library probes which form the server accepts and caches.

## Flow (Option B)

```
deploy-prod-validated.yml on main merge:
  1. deploy_agents --env prod   → commits VERSION$N in prod, alias=validated moves
  2. smoke_test    --env prod --alias validated
  3. run_eval      --env prod --alias validated         ← evals the candidate

promote-validated-to-production.yml (manual approval):
  1. versioning.set_alias(production, <version currently validated>)
  2. smoke_test    --env prod --alias production
  3. run_eval      --env prod --alias production        ← post-flip smoke eval
```

## API

```python
def run_eval(
    agent_fqn: str,
    *,
    env: str,
    version: str | None = None,
    alias: str | None = None,
    eval_table: str,
    metrics: list[str],
) -> EvalResult
```

At least one of `version` or `alias` is required in CI mode. Local exploratory use can omit both.
