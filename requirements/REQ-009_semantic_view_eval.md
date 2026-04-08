# REQ-009: Semantic View Evaluations

## Summary
Evaluate Cortex Analyst SQL generation accuracy against verified queries for each semantic view, providing a second quality gate that catches SV regressions before they cascade into agent failures. Uses `GET_ANALYST_AI_EVALUATION_DATA` to retrieve per-query results programmatically and compute pass/fail for CI gating.

## Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| `GET_ANALYST_AI_EVALUATION_DATA()` | AVAILABLE | Retrieves per-query results from completed eval runs |
| Programmatic eval trigger API | NOT AVAILABLE | Runs can only be triggered via Snowsight UI today |
| `check_sv_eval.py` | TO BUILD | Reads results, computes regression count + correctness %, gates CI |
| `run_sv_eval.py` | FUTURE | Trigger + poll when programmatic API becomes available |
| Verified queries in Git | TO BUILD | Track verified queries alongside SV YAML definitions |

## Business Context
Semantic views are the foundation that agents build on. A column rename, a join change, or a new dimension can break SQL generation for queries that previously worked. The Cortex Analyst evaluation system tests SQL correctness by running the generated SQL and comparing results against verified queries. By gating on regression count (queries that were correct but now fail), we catch SV-level issues before they propagate to agent evaluations — where the root cause is harder to diagnose.

## Dual Eval Gate Architecture

```
  Deploy SVs
       |
       v
  SV Eval (SQL correctness via verified queries)
       |
  +----+-----+
  |          |
Pass       Fail ---> Block agent deploy, investigate SV regression
  |
  v
  Deploy Agents
       |
       v
  Agent Eval (answer quality via golden questions)
       |
  +----+-----+
  |          |
Pass       Fail ---> Rollback agent + SV from snapshot
  |
  v
  Promote to next env
```

## GET_ANALYST_AI_EVALUATION_DATA Reference

```sql
SELECT * FROM TABLE(SNOWFLAKE.LOCAL.GET_ANALYST_AI_EVALUATION_DATA(
    '<DATABASE>',
    '<SCHEMA>',
    '<SEMANTIC_VIEW_NAME>',
    'SEMANTIC VIEW',
    '<RUN_NAME>'
));
```

### Columns Returned

| Column | Data Type | Description |
|--------|-----------|-------------|
| RECORD_ID | VARCHAR | Unique identifier for this evaluation record |
| INPUT_ID | VARCHAR | Unique identifier for this evaluation input |
| REQUEST_ID | VARCHAR | Unique identifier for this request |
| TIMESTAMP | TIMESTAMP | Time the request was made |
| DURATION_MS | INT | Time in milliseconds for Analyst to return a response |
| INPUT | VARCHAR | The query string used as input |
| OUTPUT | VARCHAR | The response returned by Cortex Analyst |
| ERROR | VARCHAR | Error information if any occurred |
| GROUND_TRUTH | VARCHAR | The verified query SQL used as ground truth |
| METRIC_NAME | VARCHAR | Name of the metric evaluated |
| EVAL_AGG_SCORE | NUMBER | Evaluation score for this record |
| METRIC_TYPE | VARCHAR | `system` for built-in, `custom` for custom metrics |
| METRIC_STATUS | VARCHAR | Status of the metric evaluation |
| METRIC_CALLS | VARCHAR | Metric call details |

### Key Differences from Agent Eval

| Aspect | Agent Eval (REQ-004) | SV Eval (REQ-009) |
|--------|---------------------|-------------------|
| Function | `GET_AI_EVALUATION_DATA` | `GET_ANALYST_AI_EVALUATION_DATA` |
| Object type | `'CORTEX AGENT'` | `'SEMANTIC VIEW'` |
| Trigger | `EXECUTE_AI_EVALUATION` (programmatic) | Snowsight UI only (today) |
| Ground truth | Golden questions with expected answers | Verified queries (SQL correctness) |
| Measures | Answer correctness, logical consistency, custom metrics | SQL correctness, regression count, latency |
| No LLM stat columns | Has LLM stat columns | Does NOT have LLM stat columns |

## Acceptance Criteria

- [ ] `check_sv_eval.py` retrieves results via `GET_ANALYST_AI_EVALUATION_DATA`
- [ ] Script computes regression count (queries correct in prior run but failing now)
- [ ] Script computes overall SQL correctness percentage from EVAL_AGG_SCORE
- [ ] Script exits 0 (pass) or 1 (fail) based on configurable thresholds
- [ ] CI/CD pipeline includes SV eval check step between SV deploy and agent deploy
- [ ] Verified queries documented alongside SV YAML definitions in `semantic-views/verified_queries/`
- [ ] Documentation covers the manual trigger workflow (Snowsight UI) until API is available
- [ ] When programmatic trigger API becomes available, `run_sv_eval.py` triggers + polls + gates

## User Stories

| Story ID | As a... | I want to... | So that... |
|----------|---------|-------------|------------|
| US-024   | data engineer | SQL correctness checks on my semantic views after each deploy | I catch SV regressions before they cascade into agent failures |
| US-025   | DevOps engineer | a CI gate based on SV eval regression count | broken semantic views never reach agent deployment |

## Dependencies
- REQ-001: Environment Configuration System (database/schema for GET_ANALYST_AI_EVALUATION_DATA call)
- REQ-002: Semantic View CI/CD Pipeline (SVs must be deployed before they can be evaluated)

## Out of Scope
- Custom Cortex Analyst metrics (only built-in SQL correctness and regression for now)
- Programmatic eval trigger (blocked on Snowflake API availability)
- Automated verified query generation (verified queries are human-curated)
- Cortex Analyst evaluations for semantic model files (only semantic views supported)

## Notes
- The user is building SV evaluation examples in another repo — implementation details may be refined
- Verified queries are the ground truth: they define "correct SQL" for a given natural language question
- Regression is the key metric: a query that was correct before but fails after a change is a high-severity signal
- Latency (DURATION_MS) is tracked but not gated on — useful for performance monitoring
- The manual Snowsight trigger workflow: deploy SV -> open Snowsight -> run eval -> `check_sv_eval.py` reads results
- Future workflow: deploy SV -> `run_sv_eval.py` triggers + polls -> automatic gate
- Required privileges: CORTEX_USER database role, AI_OBSERVABILITY_EVENTS_LOOKUP, EXECUTE TASK, CREATE TASK, CREATE DATASET, SELECT + MONITOR on SV
