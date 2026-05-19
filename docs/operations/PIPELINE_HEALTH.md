# Pipeline Health & Exit Criteria

Single source of truth for "is the rebuild + deploy pipeline done?" Every
workflow failure maps to one of three categories; only two of them are
things we own.

## Error categories

```
+-------------------+----------------------------+-------------------------------+
| Category          | Example                    | Who owns the fix?             |
+-------------------+----------------------------+-------------------------------+
| Repo / config     | dbt model missing col      | us — code change              |
| Threshold failure | SV score 0.58 < 0.60       | us — spec/VQR change          |
| Platform blocker  | SYSTEM_AI_OBS_ANALYST_EVAL | Snowflake — wait for PuPr fix |
|                   | does not exist             |                               |
+-------------------+----------------------------+-------------------------------+
```

Exit code taxonomy across workflows (run_sv_eval.py, run_ci_eval.py,
deploy-dev.yml):

| Code | Meaning                                          | CI treatment                |
|------|--------------------------------------------------|-----------------------------|
| 0    | pass                                             | green                       |
| 1    | threshold fail (advisory in DEV, hard in PROD)   | red (DEV advisory only)     |
| 2    | crash / unhandled (always hard-fail)             | red, block                  |
| 3    | platform blocker (Snowflake PuPr bug)            | yellow, continue pipeline   |

## Exit criteria — "the rebuild is done"

Pipeline is considered healthy when every one of the following is true on
a fresh `push` to `dev`:

1. [`/.github/workflows/dcm-deploy.yml`](/Users/jdemlow/github/AgentMangement/.github/workflows/dcm-deploy.yml) succeeds on push to `dev` or `main`
   (uses `snow dcm create/plan/deploy` directly with
   `SNOWFLAKE_CONNECTIONS_DEFAULT_*` env vars and our shared
   [`snowflake-setup`](/Users/jdemlow/github/AgentMangement/.github/actions/snowflake-setup/action.yml) composite).
2. [`/.github/workflows/deploy-dev.yml`](/Users/jdemlow/github/AgentMangement/.github/workflows/deploy-dev.yml) reaches Agent Evaluation with:
   - Pre-deploy Snapshot: success
   - RAW seeds bootstrapped by [`scripts/bootstrap_raw_seeds.py`](/Users/jdemlow/github/AgentMangement/scripts/bootstrap_raw_seeds.py)
   - Deploy Semantic Views: success (dbt + deploy_semantic_views)
   - SV Evaluation Gate: `passed`, `threshold_fail`, or `platform_blocked`
     (never `crash`)
   - Deploy Agents: success AND
     [`assert_alias_points_to`](/Users/jdemlow/github/AgentMangement/agent_management/versioning.py) passes
     for the configured `deploy_alias`
   - Smoke test: passes the [`_preflight_selector`](/Users/jdemlow/github/AgentMangement/agent_management/smoke_test.py)
     check AND reaches prompt response
   - Agent Evaluation: threshold_pass or advisory fail
3. All GH environment config is reproducible from code
   (`scripts/bootstrap_gh_environments.py --check-secrets ...`).
4. All DCM-managed Snowflake objects recreatable via `snow dcm create/deploy`.

## Open platform dependency (gap #8)

`EXECUTE_AI_EVALUATION` against semantic views fails with:

```
Semantic View Optimization '<db>.SEMANTIC.SYSTEM_AI_OBS_ANALYST_EVAL_<sv>'
does not exist or not authorized.
```

- Partial mitigation: `GRANT READ UNREDACTED AI OBSERVABILITY EVENTS TABLE`
  codified in [`dcm/sources/definitions/access.sql`](/Users/jdemlow/github/AgentMangement/dcm/sources/definitions/access.sql).
- Residual: Snowflake PuPr bug per the engineering bug notice (fix rolling
  out account-wide). Full resolution requires the Snowflake deploy.
- Current CI behavior: [`run_sv_eval.py::is_platform_blocker`](/Users/jdemlow/github/AgentMangement/agent_management/run_sv_eval.py)
  detects the error signature, returns exit code 3, and deploy-dev.yml
  treats exit 3 as advisory so the rest of the pipeline proceeds.
- Revert plan: once Snowflake ships the fix, flip SV Eval Gate back from
  `continue-on-error: true` to a hard failure by removing the `exit 3` pass
  in deploy-dev.yml and optionally dropping the platform-blocker detection.

## What "good" looks like on the current account

After the changes in this round (PRs covering the DCM workflow rewrite,
SV eval classification, post-deploy alias assertion, smoke pre-flight,
RAW seed bootstrap):

- DCM workflow on push-to-main: **green**
- deploy-dev: **green** except the SV Eval Gate step which is **yellow
  (platform_blocked)** until Snowflake ships the fix.

Pipeline is considered done when the workflow is green OR yellow in that
shape. A red anywhere means real regression that we own.
