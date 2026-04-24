# VQR Authoring Guide

Verified Queries (VQRs) are the single biggest accuracy lever that is not
instruction tuning. This guide explains how to pick, write, and deploy them.

## What a VQR does

When Cortex Analyst receives a question that matches a VQR's `question`
field, it bypasses LLM SQL generation and returns the canonical SQL
directly. Result: **faster, deterministic, correct** answers for the
questions you've pre-verified.

VQRs live in:
- `semantic-views/verified_queries/<sv_name>.yaml` — the source of truth
- The embedded JSON inside the dbt `semantic_view` model — deployed as part
  of the SV itself via `dbt run`

## When to add a VQR

Add a VQR when any of these are true:

1. **A common question scores < 0.67 in the eval.** Check
   `agent_optimization/<agent>/versions/v*/evals/` for the latest run.
2. **The SQL is non-trivial** (multiple CTEs, seasonal filtering, joins
   across tables) — pre-verifying avoids LLM drift.
3. **The business expects a canonical answer** (e.g. "what's our total
   ticket revenue last season" should always return the same number).

Do NOT add a VQR for:
- Open-ended exploration questions ("what's interesting about Q4?").
- Questions the agent already answers at 1.00.
- Questions that will rarely be asked.

## Picking VQR candidates from eval failures

Workflow:

1. Read the latest eval output:
   `agent-evaluation/results/<agent>_<env>_<timestamp>.json` or the
   summary markdown.
2. Sort questions by `answer_correctness` ascending.
3. For each failing question:
   - Run the validation_query from `agent-evaluation/datasets/<agent>_eval.yaml`
     to see the ground truth.
   - Ask the agent the question directly (via `test_agents_live.py` or
     Snowsight) to see the current answer.
   - If the gap is because the agent writes bad SQL, it's a VQR candidate.
   - If the gap is because the validation_query is wrong, fix the eval
     dataset, not the SV.

## Writing the VQR

Use this structure:

```yaml
- name: snake_case_name
  question: "Natural-language question as a user would ask it."
  sql: >-
    <canonical SQL that produces the right answer>
  verified_by: "Cortex Analyst"
  verified_at: <unix timestamp>
  use_as_onboarding_question: <true if this should show up as a suggested
                               question in Snowsight; false for deep-dive
                               analytical queries>
```

### Two SQL styles — pick the right one

**Style 1 — SEMANTIC_VIEW query** (preferred for simple cases):
```sql
SELECT * FROM SEMANTIC_VIEW(
  SEMANTIC.SEM_MY_VIEW
  DIMENSIONS dim1, dim2
  METRICS metric1, metric2
  WHERE dim1 = 'value'
)
```

**Style 2 — Raw SQL with CTE** (needed for multi-step logic, sub-queries,
dynamic filters):
```sql
WITH last_season AS (
  SELECT MAX(ski_season) AS season
  FROM SEMANTIC_VIEW(
    SEMANTIC.SEM_MY_VIEW
    DIMENSIONS ski_season
    METRICS total_count
  )
  WHERE ski_season < (
    SELECT ski_season FROM MARTS.DIM_DATE WHERE full_date = CURRENT_DATE()
  )
)
SELECT ski_season, metric1, metric2
FROM SEMANTIC_VIEW(
  SEMANTIC.SEM_MY_VIEW
  DIMENSIONS ski_season
  METRICS metric1, metric2
)
WHERE ski_season = (SELECT season FROM last_season)
```

### Dynamic time resolution

NEVER hardcode season strings like `'2024-2025'` in VQRs. Use this pattern
for "last season":

```sql
WITH last_season AS (
  SELECT MAX(ski_season) AS season
  FROM SEMANTIC_VIEW(
    SEMANTIC.SEM_MY_VIEW
    DIMENSIONS ski_season
    METRICS <any_metric>
  )
  WHERE ski_season < (
    SELECT ski_season FROM MARTS.DIM_DATE WHERE full_date = CURRENT_DATE()
  )
)
```

For "this season" or "current season":
```sql
WITH current_season AS (
  SELECT ski_season FROM MARTS.DIM_DATE WHERE full_date = CURRENT_DATE()
)
```

### For SVs without a SKI_SEASON dimension

Some SVs (e.g. `SEM_LESSONS_ANALYTICS`) don't join to `DIM_DATE`. Use the
fact-table date column directly with a computed season boundary:

```sql
WITH __fact_lessons AS (
  SELECT lesson_id, lesson_date, total_lesson_revenue
  FROM MARTS.FACT_LESSONS
  WHERE lesson_date BETWEEN
    (SELECT DATEADD(year, -1, DATE_TRUNC('year', CURRENT_DATE()) - INTERVAL '2 months'))
    AND (SELECT DATE_TRUNC('year', CURRENT_DATE()) - INTERVAL '2 months' - INTERVAL '1 day')
)
SELECT ...
```

(Better long-term: add `DATE_KEY` to the fact and a `DIM_DATE` join to the
SV. File that as a follow-up.)

## Verifying the VQR

Before merging, run the SQL against DEV and confirm:

1. It returns rows (not empty).
2. The number matches the validation_query in the eval dataset.
3. It does not error on edge cases (empty season, off-season date).

```bash
# Run via snowflake CLI or a Snowsight worksheet:
USE ROLE AM_DEPLOY_ROLE_DEV;
USE DATABASE AM_SKI_RESORT_DEV;
USE SCHEMA SEMANTIC;
<paste your VQR SQL>
```

## Deploying the VQR

Two deploy paths:

1. **Via dbt** (same commit as the SV model change): edit the embedded
   `verified_queries` JSON inside `dbt_ski_resort/models/marts/semantic/<sv>.sql`.
   Deploys with `dbt run` — the canonical path for the SV structure.
2. **Via deploy_svs_yaml.py** (VQR-only changes): edit
   `semantic-views/verified_queries/<sv>.yaml` and run
   `python -m agent_management.deploy_svs_yaml --env <env>`. This is the
   hot-path for iterating on VQRs without redeploying the whole SV.

Keep both files in sync. A future CI check should flag when they diverge.

## Measuring VQR impact

After adding VQRs, re-run the agent eval. Record the delta in
`framework/MEASUREMENT_RESULTS.md`. Expect a larger delta on questions
that previously scored 0.00-0.33 than on questions already scoring 0.67+.
