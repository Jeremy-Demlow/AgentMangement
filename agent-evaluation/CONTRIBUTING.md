# Agent Evaluation — Contributing

How to modify, extend, and debug the evaluation framework.

For usage instructions (running evals, CLI flags, interpreting results), see [README.md](README.md).

## Directory Layout

```
agent-evaluation/
  configs/                          # One eval config per agent (Jinja2 templates)
    resort_executive.yaml
    ski_ops_assistant.yaml
  datasets/                         # One question set per agent
    resort_executive_eval.yaml      #   Questions + ground truth (dynamic and static)
    ski_ops_assistant_eval.yaml
  scripts/                          # Eval runner and utilities
    run_eval.py                     #   End-to-end runner (the main engine)
    eval_summary.py                 #   CI: queries latest results, posts PR comment
    load_eval_dataset.py            #   Standalone CSV → Snowflake loader
    convert_eval_dataset.py         #   Convert existing table to eval format
    invoke_agent.py                 #   Test single question via REST API
  results/                          # JSON output from runs (gitignored)
  references/
    dynamic-ground-truth.md         # Patterns for validation_query + answer_template
  README.md                         # Full usage guide
  SKILL.md                          # Cortex Code assistant workflow
  CONTRIBUTING.md                   # This file
```

## What Happens When an Eval Runs

Understanding the execution flow is critical before making changes:

```
run_ci_eval.py (CI entrypoint)
  │
  ├── 1. Loads environments/<env>.env.yml
  ├── 2. Renders config + dataset templates (Jinja2 → concrete values)
  ├── 3. Calls run_eval.py with rendered config
  │
  └── run_eval.py (per agent)
        │
        ├── 1. Load questions from dataset YAML
        ├── 2. Connect to Snowflake
        ├── 3. Execute every validation_query against LIVE data
        │      └── Format results into answer_template → ground_truth
        ├── 4. CREATE OR REPLACE the eval data table (fresh every run)
        ├── 5. INSERT each question + resolved ground_truth
        ├── 6. Generate Snowflake eval YAML config
        ├── 7. Upload YAML to @EVAL_CONFIG_STAGE
        ├── 8. EXECUTE_AI_EVALUATION('START', ...)
        ├── 9. Poll STATUS every 30s until COMPLETED
        ├── 10. Fetch results via GET_AI_EVALUATION_DATA
        ├── 11. Check thresholds → exit 0 (pass) or 1 (fail)
        └── 12. Save JSON to results/
```

Key implication: **the dataset is rebuilt from scratch every run**. Ground truth is resolved at eval time from live data, not cached. This means eval results depend on what's currently in the tables.

## Adding Questions to an Existing Agent

1. Edit `datasets/<agent>_eval.yaml`.

2. For data-driven questions, use dynamic ground truth:

   ```yaml
   - question: "What was average lift wait time last week?"
     expected_tools: ["OperationsAnalytics"]
     category: operations
     tags: [lifts, weekly]
     test_type: in_scope
     validation_query: |
       SELECT ROUND(AVG(WAIT_MINUTES), 1) AS avg_wait
       FROM {{ eval.source_database }}.MARTS.FACT_LIFT_SCANS
       WHERE DATE_KEY >= (SELECT MAX(DATE_KEY) - 7 FROM {{ eval.source_database }}.MARTS.FACT_LIFT_SCANS)
     answer_template: "Average lift wait time was {avg_wait} minutes."
   ```

3. For boundary/scope tests, use static ground truth:

   ```yaml
   - question: "What is the stock price of Vail Resorts?"
     expected_tools: []
     category: boundary
     test_type: out_of_scope
     ground_truth: "Agent should decline — stock data is outside its domain."
   ```

4. Test your ground truth resolves correctly:

   ```bash
   python scripts/run_eval.py configs/<agent>.yaml --resolve-only --connection myconnection
   ```

5. Dry-run to verify the full plan:

   ```bash
   python scripts/run_eval.py configs/<agent>.yaml --dry-run
   ```

## Adding a New Agent to Evaluation

1. Create `configs/<agent_name>.yaml` — copy an existing config as a template.

2. Update these fields:

   ```yaml
   agent:
     name: "MY_NEW_AGENT"
     database: "{{ eval.source_database }}"
     schema: "{{ eval.agents_schema }}"

   dataset:
     questions: "datasets/<agent_name>_eval.yaml"
     snowflake_table: "{{ eval.source_database }}.{{ eval.agents_schema }}.MY_NEW_AGENT_EVAL_DATA"
   ```

3. Create `datasets/<agent_name>_eval.yaml` with at least 5-10 questions covering the agent's key tools.

4. The CI pipeline auto-discovers configs — any `*.yaml` in `configs/` (not prefixed with `_`) gets evaluated. No workflow changes needed.

5. Validate locally before pushing:

   ```bash
   python scripts/run_eval.py configs/<agent_name>.yaml --dry-run
   python scripts/run_eval.py configs/<agent_name>.yaml --resolve-only --connection myconnection
   ```

## Writing Good Validation Queries

Validation queries generate ground truth at eval time. Bad queries are the #1 cause of misleading eval scores.

### Do

- **Use relative time references**: `MAX(DATE_KEY)`, "most recent day with data", "last complete quarter"
- **Handle empty results**: Use `COALESCE`, `IFNULL`, or ensure data always exists for the time window
- **Match agent tool granularity**: If the agent's semantic view aggregates by month, your query should too
- **Use `{{ eval.source_database }}`**: Never hardcode database names — templates resolve per environment
- **Test with `--resolve-only`** before running the full eval

### Don't

- **Use "yesterday" or "today"**: Data may not exist for those dates (weekends, holidays, pipeline delays)
- **Return NULL columns**: `answer_template` format specs like `{total:,.0f}` crash on None — use `COALESCE`
- **Write queries that return zero rows**: The template produces garbled output and scores 0%
- **Assume column names are uppercase**: Use lowercase in `answer_template` placeholders — the runner lowercases all column names from `cursor.description`

### Example: Before and After

```yaml
# BAD — fails on days with no data
validation_query: |
  SELECT SUM(REVENUE) AS total
  FROM {{ eval.source_database }}.MARTS.FACT_TICKET_SALES
  WHERE DATE_KEY = (SELECT DATE_KEY FROM {{ eval.source_database }}.MARTS.DIM_DATE WHERE FULL_DATE = CURRENT_DATE() - 1)

# GOOD — always finds data
validation_query: |
  WITH latest AS (
    SELECT MAX(d.FULL_DATE) AS dt
    FROM {{ eval.source_database }}.MARTS.FACT_TICKET_SALES ts
    JOIN {{ eval.source_database }}.MARTS.DIM_DATE d ON ts.DATE_KEY = d.DATE_KEY
  )
  SELECT COALESCE(SUM(ts.REVENUE), 0) AS total
  FROM {{ eval.source_database }}.MARTS.FACT_TICKET_SALES ts
  JOIN {{ eval.source_database }}.MARTS.DIM_DATE d ON ts.DATE_KEY = d.DATE_KEY
  WHERE d.FULL_DATE = (SELECT dt FROM latest)
```

## Modifying the Eval Runner (run_eval.py)

Changes to `run_eval.py` affect every agent evaluation. Test carefully.

### Key functions and what they do

| Function | Purpose | Gotchas |
|----------|---------|---------|
| `resolve_dynamic_ground_truth()` | Runs validation_query SQL, formats answer_template | Decimal values must be cast to float; None values must be handled |
| `load_questions_to_snowflake()` | CREATE OR REPLACE table + INSERT rows | Single quotes in questions/ground_truth must be escaped |
| `generate_snowflake_yaml()` | Builds the YAML consumed by EXECUTE_AI_EVALUATION | `source_metadata.type` must be lowercase `"dataset"` |
| `poll_until_done()` | STATUS polling loop | Status field position varies — code handles both named and positional |
| `check_thresholds()` | Compares avg scores against env thresholds | Missing metrics are skipped, not failed |

### Common pitfalls

- **Format specifiers on None**: Python's `f"{val:>6}"` raises `TypeError` if `val` is None. Always use `(val or 0)` or `(val or "N/A")` fallback.
- **SQL args count**: `GET_AI_EVALUATION_DATA` takes 5 args (database, schema, agent, object_type, run_name). `GET_AI_OBSERVABILITY_LOGS` takes 4 (no run_name).
- **Stage YAML corruption**: The stage file format must use `FIELD_DELIMITER = NONE` and `ESCAPE_UNENCLOSED_FIELD = NONE`. The runner creates this correctly — don't change it.

## Modifying eval_summary.py (CI PR Comments)

`eval_summary.py` runs after evals in the Validate PR workflow. It:

1. Queries `GET_AI_OBSERVABILITY_LOGS` to find the latest eval `run_name`
2. Queries `GET_AI_EVALUATION_DATA` with that run_name for scores
3. Writes markdown to `/tmp/eval_summary.md`
4. The workflow step reads the file and posts it as a PR comment

### Why it writes to a file (not GITHUB_OUTPUT)

Multiline markdown with backticks breaks when interpolated into JavaScript template literals via `${{ }}`. The file-based approach avoids this entirely:

```yaml
# In the workflow:
- name: Comment PR
  uses: actions/github-script@v7
  with:
    script: |
      const fs = require('fs');
      const body = fs.readFileSync('/tmp/eval_summary.md', 'utf8');
      // ... post as PR comment
```

## CI Integration Details

### Where evals run in CI

| Workflow | Trigger | Eval behavior | On failure |
|----------|---------|---------------|------------|
| `validate-pr.yml` (→ dev) | PR to dev | `continue-on-error: true` — advisory | Logged, not blocking |
| `validate-pr.yml` (→ main) | PR to main | `continue-on-error: false` — hard gate | PR cannot merge |
| `deploy-dev.yml` | Push to dev | `continue-on-error: true` — advisory | Logged, not blocking |
| `promote-qa.yml` | Manual dispatch | Hard failure | Deploy blocked |
| `promote-prod.yml` | Manual dispatch | Hard failure | Auto-rollback |

The `continue-on-error` expression `${{ github.base_ref == 'dev' }}` dynamically makes the eval job advisory for dev PRs and a hard gate for main PRs.

### Required GitHub Actions permissions

```yaml
permissions:
  contents: read
  pull-requests: write    # Required for PR comment posting
```

Without `pull-requests: write`, the eval summary comment step fails with `Resource not accessible by integration`.

### Workflow path triggers

Evals only run when source files change. The `paths` filter includes:

```yaml
paths:
  - 'agents/specs/**'
  - 'semantic-views/definitions/**'
  - 'agent_management/**'
  - 'agent-evaluation/**'
  - 'environments/**'
  - 'tests/**'
  - 'dbt_ski_resort/**'
```

Changes to `.github/workflows/` alone do **not** trigger evals (by design — workflow-only PRs don't need Snowflake validation).

## Thresholds

Thresholds are defined in environment configs, not in eval config templates:

| Environment | answer_correctness | logical_consistency | Behavior |
|-------------|-------------------|--------------------|----|
| DEV | 0.60 | 0.60 | Lenient — iterate freely |
| QA | 0.70 | 0.70 | Moderate — quality gate |
| PROD | 0.80 | 0.80 | Strict — failure triggers rollback |

To change: edit `eval.thresholds` in `environments/<env>.env.yml`. The config templates use `{{ eval.thresholds.answer_correctness }}` — never hardcode values.

## Conventions

- **File naming**: `configs/<agent_name>.yaml` and `datasets/<agent_name>_eval.yaml` — names must match the agent spec in `agents/specs/`.
- **Jinja2 placeholders**: Use `{{ eval.* }}` for eval-specific values (source_database, stage, thresholds). Use `{{ env.* }}` for environment values (database, warehouse).
- **Categories**: Group questions by domain (`revenue`, `operations`, `boundary`). Categories enable filtered reporting with `--category`.
- **Tags**: Use tags for cross-cutting concerns (`weekly`, `dynamic`, `regression`). Tags enable filtered runs with `--tag`.
- **test_type**: `in_scope` (agent should answer), `out_of_scope` (agent should decline), `negative` (invalid input — agent should handle gracefully).

## What Not to Edit

- `results/` — Auto-generated JSON output. Gitignored. Each run creates a new timestamped file.
- `generated/` — Rendered eval configs. Overwritten by `render_eval_templates.py`.
- `scripts/run_eval.py` internal SQL — The `EXECUTE_AI_EVALUATION` calls, stage setup, and file format creation follow exact Snowflake API requirements. Changes here break evals silently.

## Debugging Failed Evals

### Question scored 0% unexpectedly

1. Run `--resolve-only` to check ground truth:
   ```bash
   python scripts/run_eval.py configs/<agent>.yaml --resolve-only --connection myconnection
   ```
2. If ground truth is empty or garbled → fix the `validation_query` (likely returned NULL or zero rows)
3. If ground truth looks correct → the agent gave a wrong answer. Check the Snowsight eval UI for the agent's actual response and trace.

### All questions scored 0% on answer_correctness

Ground truth is not linked. This usually means the dataset was created outside of `run_eval.py` (e.g., via `SYSTEM$CREATE_EVALUATION_DATASET`). Always use `run_eval.py` — it handles column mapping correctly.

### Eval stuck in INVOCATION_IN_PROGRESS

The agent is taking too long. Check:
- Agent budget limits in env config (`orchestration.budget.seconds`)
- Snowflake query history for long-running queries from the agent
- Agent tool count — agents with many tools take longer per question

### Score variance between runs

Normal. LLM-based evaluation has ~5-10% variance. Look at trends across multiple runs, not single scores. The JSON results in `results/` enable historical comparison.

## Related Commands

```bash
# Run eval for one agent
python scripts/run_eval.py configs/<agent>.yaml --connection myconnection

# Dry-run (show plan, no Snowflake)
python scripts/run_eval.py configs/<agent>.yaml --dry-run

# Resolve ground truth only (verify queries work)
python scripts/run_eval.py configs/<agent>.yaml --resolve-only --connection myconnection

# CI entrypoint (renders templates, runs all agents)
agent-mgmt-eval-agent --env dev

# View latest results
python scripts/run_eval.py configs/<agent>.yaml --results --connection myconnection

# Check status of running eval
python scripts/run_eval.py configs/<agent>.yaml --status --connection myconnection

# Filter by category
python scripts/run_eval.py configs/<agent>.yaml --category revenue --connection myconnection
```
