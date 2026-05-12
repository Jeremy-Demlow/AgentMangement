# Cortex Analyst SV Evaluation — companion object not auto-provisioning

## TL;DR

`EXECUTE_AI_EVALUATION('START', …)` against a semantic view fails with
error `210007 (P0000)`:

```
Semantic View Optimization
'AM_SKI_RESORT_DEV.SEMANTIC.SYSTEM_AI_OBS_ANALYST_EVAL_SEM_REVENUE'
does not exist or not authorized.
in function EXECUTE_AI_EVALUATION
```

The companion `SYSTEM_AI_OBS_ANALYST_EVAL_<sv>` object is Snowflake-
internal and is supposed to be provisioned automatically when an
evaluation is first run. It is not being created on fresh accounts /
after teardown + rebuild, even with every privilege listed in the
[official evaluation docs](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst/evaluation) applied.

- Yesterday (2026-05-01 01:43 UTC) the same code path passed (SV Eval
  Gate green for all 11 SVs).
- Today (2026-05-01 14:34 UTC onward) every run fails on every SV with
  the same error after a teardown + clean DCM deploy.
- No repo changes between those times to the SV code path or to the
  `deploy_role` privilege set.
- Retries persist for ≥ 2 hours after SEMANTIC views are recreated.

## Environment

- Account: `TRB65519` (sfsenorthamerica / demo_jdemlow)
- Role used for eval: `AM_DEPLOY_ROLE_DEV`
- Database: `AM_SKI_RESORT_DEV`
- Schema: `SEMANTIC` (owner: `AM_DEPLOY_ROLE_DEV`)
- Warehouse: `AM_SKI_RESORT_WH_DEV`
- Snowflake release: PuPr feature (Cortex Analyst Evaluations)

## Exact reproduction

### 1. Semantic view exists and is readable

```sql
USE ROLE AM_DEPLOY_ROLE_DEV;
USE WAREHOUSE AM_SKI_RESORT_WH_DEV;
SHOW SEMANTIC VIEWS IN SCHEMA AM_SKI_RESORT_DEV.SEMANTIC;
-- 11 rows, all owned by AM_DEPLOY_ROLE_DEV, created 2026-05-01 09:42 PDT

DESCRIBE SEMANTIC VIEW AM_SKI_RESORT_DEV.SEMANTIC.SEM_REVENUE;
-- succeeds, returns full dimension / fact / metric / VQR structure
```

### 2. All docs-required privileges are granted

The role has each privilege listed at
<https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst/evaluation#prerequisites>:

```sql
-- Verified via SHOW GRANTS TO ROLE AM_DEPLOY_ROLE_DEV
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE AM_DEPLOY_ROLE_DEV;
GRANT APPLICATION ROLE SNOWFLAKE.AI_OBSERVABILITY_EVENTS_LOOKUP TO ROLE AM_DEPLOY_ROLE_DEV;
GRANT EXECUTE TASK ON ACCOUNT TO ROLE AM_DEPLOY_ROLE_DEV;
GRANT CREATE TASK ON SCHEMA AM_SKI_RESORT_DEV.SEMANTIC TO ROLE AM_DEPLOY_ROLE_DEV;
GRANT CREATE DATASET ON SCHEMA AM_SKI_RESORT_DEV.SEMANTIC TO ROLE AM_DEPLOY_ROLE_DEV;
GRANT SELECT ON ALL SEMANTIC VIEWS IN SCHEMA AM_SKI_RESORT_DEV.SEMANTIC TO ROLE AM_DEPLOY_ROLE_DEV;
GRANT MONITOR ON ALL SEMANTIC VIEWS IN SCHEMA AM_SKI_RESORT_DEV.SEMANTIC TO ROLE AM_DEPLOY_ROLE_DEV;
GRANT READ UNREDACTED AI OBSERVABILITY EVENTS TABLE ON ACCOUNT TO ROLE AM_DEPLOY_ROLE_DEV;
```

### 3. Upload eval config YAML to stage

Standard format per docs:

```yaml
evaluation:
  analyst_params:
    analyst_name: "AM_SKI_RESORT_DEV.SEMANTIC.SEM_REVENUE"
    analyst_type: "SEMANTIC VIEW"
  run_params:
    label: "SEM_REVENUE evaluation"
    description: "Automated SV evaluation - <run_name>"
  source_metadata:
    type: "verified_queries"

metrics:
  - "sql_correctness"
```

### 4. START call fails immediately

```sql
CALL EXECUTE_AI_EVALUATION(
    'START',
    OBJECT_CONSTRUCT('run_name', 'REPRO_CASE_1'),
    '@AM_SKI_RESORT_DEV.SEMANTIC.sv_eval_stage/sv_eval_sem_revenue.yaml'
);

-- 210007 (P0000): 01c41538-0208-bece-004d-de0711ae2c3a:
-- User Error Report: Failed to get Run: SQL compilation error:
-- Semantic View Optimization
--   'AM_SKI_RESORT_DEV.SEMANTIC.SYSTEM_AI_OBS_ANALYST_EVAL_SEM_REVENUE'
--   does not exist or not authorized.
-- in function EXECUTE_AI_EVALUATION
```

Query IDs from recent attempts (ACCOUNTADMIN can look these up):

```
01c41538-0208-bece-004d-de0711ae2c3a   2026-05-01 16:05 PDT
01c41539-0208-bece-004d-de0711ae2c3a   2026-05-01 16:06 PDT
01c4153b-0208-bdf1-004d-de0711aea846   2026-05-01 16:08 PDT
```

### 5. The companion object really doesn't exist

```sql
SHOW TABLES LIKE 'SYSTEM_AI_OBS%' IN SCHEMA AM_SKI_RESORT_DEV.SEMANTIC;
-- 0 rows

SHOW VIEWS LIKE 'SYSTEM_AI_OBS%' IN SCHEMA AM_SKI_RESORT_DEV.SEMANTIC;
-- 0 rows

-- Historical view (ACCOUNT_USAGE has ~45m latency):
SELECT TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME, CREATED, DELETED
FROM SNOWFLAKE.ACCOUNT_USAGE.TABLES
WHERE TABLE_NAME LIKE 'SYSTEM_AI_OBS%'
ORDER BY CREATED DESC LIMIT 30;
-- 0 rows (no object has ever been created by that name in this account)
```

Interestingly, `AI_EVALS_*` background tasks DID run yesterday when the
eval worked — from `SNOWFLAKE.ACCOUNT_USAGE.TASK_HISTORY`:

```
AI_EVALS_INGESTION_<id>
AI_EVALS_COMPUTE_METRICS_<id>_ANSWER_CORRECTNESS
AI_EVALS_COMPUTE_METRICS_<id>_LOGICAL_CONSISTENCY
AI_EVALS_FINALIZER_<id>
```

…but those are agent-eval tasks, not SV-eval tasks (different id prefix).
No `*ANALYST_EVAL*` tasks ever ran.

## What we tried

1. Applied every grant from the docs (see section 2 above). No change.
2. Dropped and recreated the semantic view via `dbt run --full-refresh`
   so it's owned by the properly-privileged role. No change.
3. Waited ~2 hours in case the companion object is created by an
   async task. No change.
4. Verified role via `SELECT CURRENT_ROLE()` is the owner role. No change.

## What we'd like

- Confirmation of whether the `SYSTEM_AI_OBS_ANALYST_EVAL_<sv>` object
  is supposed to be auto-created by Snowflake when the SV is created,
  when `EXECUTE_AI_EVALUATION('START', …)` is first called, or by some
  other trigger.
- A documented way to explicitly provision the companion object (or
  documentation that confirms clicking the Snowsight "Evaluations" tab
  is required as a one-time bootstrap per SV).
- Whether the Apr-29 PuPr bug notice has been re-opened — this account's
  behavior matches the pre-mitigation symptom even after the mitigation
  grant has been applied.

## Cross-check — agent eval works fine on the same account

To rule out account-level misconfiguration: `EXECUTE_AI_EVALUATION`
against **agents** (not SVs) on this same account, same role, same
warehouse, works end-to-end. Local eval run from 2026-05-01 15:41 PDT:

```
RESORT_EXECUTIVE_DEV:
  answer_correctness   62.3% (threshold 0.60) PASS
  logical_consistency  91.1% (threshold 0.60) PASS
SKI_OPS_ASSISTANT_DEV:
  answer_correctness   86.7% PASS
  logical_consistency  76.6% PASS
```

So the account has the right `AI_OBS` plumbing for agents; only the SV
eval path is broken.

## Contact

- Internal owner: Jeremy Demlow (@jdemlow)
- Repo: https://github.com/Jeremy-Demlow/AgentMangement
- Related CI run where SV Eval was green: 25198195841 (2026-05-01 01:43 UTC)
- Related CI run where SV Eval first failed: 25218201885 (2026-05-01 14:34 UTC)
