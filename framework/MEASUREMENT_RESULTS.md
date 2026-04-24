# Framework Measurement Results

Running record of eval deltas per framework version. Every material change
to the framework or an agent spec should append a row here.

## Baseline: v0 (pre-framework)

Source: pipeline run 24863881412 (post PR #17), main@8979658, 2026-04-23

| Agent | answer_correctness | logical_consistency |
|---|---|---|
| resort_executive | 0.777 | 0.867 |
| ski_ops_assistant | 0.734 | 0.866 |

SV eval: 11/11 PASS.

### Weakest answer_correctness questions at v0

**resort_executive** (scoring 0.00 - 0.33):
- "How did ski school perform last season in terms of lessons and revenue" (0.00)
- "What was the average staffing coverage ratio last season" (0.00)
- "How many season passes were sold for last season" (0.33)
- "What are the largest customer segments" (0.33)
- "How does the current season's ticket revenue compare" (0.33)
- "What was the average lift wait time last season" (0.33)
- "How many safety incidents occurred last season" (0.33)
- "What was our average NPS score and customer rating" (0.33)
- "How did food and beverage revenue perform last season" (0.33)

**ski_ops_assistant** (scoring 0.00 - 0.33):
- "Which departments had the most understaffed shifts" (0.00)
- "What were the most common incident types" (0.00)
- "What were the wind conditions like last season" (0.33)
- "Give me a daily operations summary" (0.33)
- "How many safety incidents occurred last season" (0.33)
- "How much total snowfall did we get" (0.33)

## v1 — Framework best practices applied

Changes:
- All 15 tool descriptions (11 resort_executive + 4 ski_ops_assistant)
  rewritten using the standardized `PURPOSE / DATA / KEY METRICS / KEY
  DIMENSIONS / USE FOR / NOT FOR / CROSS-REFERENCE WITH` template.
- Orchestration instructions extended with: dynamic TIME ANCHOR,
  DISAMBIGUATION RULES, COMPARISON PATTERN, DRILL-DOWN PATTERN,
  CROSS-DOMAIN PATTERN, EMPTY-RESULT HANDLING, explicit BOUNDARIES.
- Response instructions extended with: RESPONSE STRUCTURE pattern,
  FORMATTING rules, TONE (no speculation clause).
- VQR expansion targeting the weakest questions:
  - SEM_LESSONS_ANALYTICS: +2 VQRs (ski school last season, monthly)
  - SEM_STAFFING_ANALYTICS: +2 VQRs (coverage last season, most understaffed)
  - SEM_SAFETY_INCIDENTS: +2 VQRs (incidents last season, top incident types)
  - SEM_REVENUE: +3 VQRs (ticket revenue last season, F&B last season, current vs last STD)
- Framework docs: best practices, tool description template, VQR authoring
  guide, optimization checklist, new agent template.
- CI test enforcing tool description format compliance.

| Agent | answer_correctness | logical_consistency | delta (answer_correctness) |
|---|---|---|---|
| resort_executive | TBD (agent eval skipped due to SV eval gate failure) | TBD | TBD |
| ski_ops_assistant | TBD (agent eval skipped due to SV eval gate failure) | TBD | TBD |

### Pipeline status: run 24908357211

- All new PR gates green: Lint, Validate Specs, dbt Quality Gate (dev/qa/prod), Validate Against Snowflake
- SV Evaluation: 10/11 pass. SEM_SAFETY_INCIDENTS continues to return "Invocation failed" on first poll — this is a pre-existing Cortex Analyst eval API issue that does not affect direct SV queries (the SV works when queried manually).
- Agent Evaluation: skipped because SV eval gate failed.

### Next steps to get v1 measurement

Option A: retry eval on a subsequent run (Cortex Analyst eval API is occasionally flaky).
Option B: post-merge eval run against QA deployment.
Option C: local eval via test_agents_live.py for a smoke check.

Results will be filled in after a successful agent eval run completes.
