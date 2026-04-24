# 08 — Version-targeted eval in run_eval.py

## Problem (today)

`agent-evaluation/scripts/run_eval.py` evals "the current agent" — whatever is live at the FQN. With versioning, we need to eval *a specific candidate version* before flipping the `production` alias, so we can reject bad versions before exposing them.

## Goal

Support `--version VERSION$N` or `--alias validated` to target evals at a non-live version.

## Snowflake API

When targeting a version, the eval call needs to include a version or alias selector in the agent identifier. Per Private Preview docs, formats like:

- `<fqn>!LIVE`, `<fqn>!FIRST`, `<fqn>!LAST`, `<fqn>!DEFAULT`
- `<fqn>!<alias_name>` (e.g., `RESORT_EXECUTIVE!validated`)
- `<fqn>!VERSION$3` (if supported)

Library probes which form the server accepts and caches.

## Flow

```
CI (promote-qa.yml):
  1. deploy_agents → creates VERSION$N, moves alias=validated
  2. run_eval --alias validated         ← evals the candidate
  3. if eval passes → promote-prod.yml (manual approval)
  4. promote-prod.yml:
     - ALTER AGENT … MODIFY VERSION <N> SET ALIAS = production
     - run_eval --alias production      ← smoke eval on prod
```

## API

```python
def run_eval(
    agent_fqn: str,
    *,
    version: str | None = None,   # VERSION$N
    alias: str | None = None,     # alias name
    eval_table: str,
    metrics: list[str],
) -> EvalResult
```

## Backward compat

When neither `version` nor `alias` is supplied, evals the live spec (legacy behavior).
