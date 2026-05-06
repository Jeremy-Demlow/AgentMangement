# Pipeline Health & Exit Criteria

Single source of truth for "is the rebuild + deploy pipeline done?" Every
workflow failure maps to one of two categories: pass or fail-loud.

## Error categories

```
+-------------------+----------------------------+-------------------------------+
| Category          | Example                    | Who owns the fix?             |
+-------------------+----------------------------+-------------------------------+
| Repo / config     | dbt model missing col      | us — code change              |
| Threshold failure | SV score 0.58 < 0.60       | us — spec/VQR change          |
| Crash             | Snowflake transient hang   | re-run workflow               |
| Platform blocker  | SYSTEM_AI_OBS_ANALYST_EVAL | escalate to Snowflake support |
|                   | does not exist             |                               |
+-------------------+----------------------------+-------------------------------+
```

All four categories **hard-fail** the gate. The taxonomy is for
classification (Step Summary, on-call decisioning, support cases) — not
for advisory flow control.

Exit code taxonomy across workflows (run_sv_eval.py, run_ci_eval.py):

| Code | Meaning                                          | CI treatment                        |
|------|--------------------------------------------------|-------------------------------------|
| 0    | pass                                             | green                               |
| 1    | threshold fail                                   | RED — fix the SV/agent              |
| 2    | crash / unhandled                                | RED — re-run workflow once first    |
| 3    | platform blocker (Snowflake regression)          | RED — open Snowflake support case   |

The previous "advisory yellow" treatment of exit 1 and exit 3 was removed
in `refactor/eval-gates-fail-loud` after [IAC_GAPS.md #8](IAC_GAPS.md)
was resolved (Snowflake landed the companion-object fix on 2026-05-05).
Hiding genuine threshold failures behind `continue-on-error: true`
suppressed real signal — see the `sql_correctness=0.0` regression on
SEM_REVENUE that lived for 2 days unnoticed.

## Exit criteria — "the rebuild is done"

Pipeline is considered healthy when every one of the following is true on
a fresh `push` to `dev`:

1. [`/.github/workflows/dcm-deploy.yml`](/Users/jdemlow/github/AgentMangement/.github/workflows/dcm-deploy.yml) succeeds on push-to-main
   (bug fixed — uses `snow dcm create/plan/deploy` directly with
   `SNOWFLAKE_CONNECTIONS_DEFAULT_*` env vars and our shared
   [`snowflake-setup`](/Users/jdemlow/github/AgentMangement/.github/actions/snowflake-setup/action.yml) composite).
2. [`/.github/workflows/deploy-dev.yml`](/Users/jdemlow/github/AgentMangement/.github/workflows/deploy-dev.yml) reaches Agent Evaluation with:
   - Pre-deploy Snapshot: success
   - RAW seeds bootstrapped by [`scripts/bootstrap_raw_seeds.py`](/Users/jdemlow/github/AgentMangement/scripts/bootstrap_raw_seeds.py)
   - Deploy Semantic Views: success (dbt + deploy_semantic_views)
   - SV Evaluation Gate: `passed` (no advisory exits accepted)
   - Deploy Agents: success AND
     [`assert_alias_points_to`](/Users/jdemlow/github/AgentMangement/agent_management/versioning.py) passes
     for the configured `deploy_alias`
   - Smoke test: passes the [`_preflight_selector`](/Users/jdemlow/github/AgentMangement/agent_management/smoke_test.py)
     check AND reaches prompt response
   - Agent Evaluation: `passed` (no advisory exits accepted)
3. All GH environment config is reproducible from code
   (`scripts/bootstrap_gh_environments.py --check-secrets ...`).
4. All DCM-managed Snowflake objects recreatable via `snow dcm create/deploy`.

## Re-run vs. fix decision tree

When a gate fails red, the Step Summary surfaces which category. Use this
to decide:

- **threshold_fail** — content signal, fix the SV / agent / VQRs and push
  again. Re-running the workflow will not change the score.
- **crash** — likely a transient Snowflake blip (warehouse busy, eval
  service hiccup). Re-run the workflow once. If it crashes again, open
  the logs.
- **platform_blocked** — Snowflake-side regression. Open a support case
  before re-running. See [IAC_GAPS.md #8](IAC_GAPS.md) for the
  precedent.
