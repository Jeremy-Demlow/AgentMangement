# Agent Evaluation

Evaluate Cortex Agents using Snowflake's native Agent Evaluations framework (GA).
Runs evaluations end-to-end from your terminal: load questions, generate ground truth from live data, start the eval, poll until complete, check pass/fail thresholds, and save results as JSON.

## Architecture

```
                        LOCAL                                    SNOWFLAKE
 ┌─────────────────────────────────────┐     ┌──────────────────────────────────────────────┐
 │                                     │     │                                              │
 │  configs/agent.yaml                 │     │                                              │
 │    agent, metrics, thresholds       │     │                                              │
 │           │                         │     │                                              │
 │           v                         │     │                                              │
 │  datasets/agent_eval.yaml           │     │                                              │
 │    questions, ground_truth,         │     │                                              │
 │    validation_query, answer_template│     │                                              │
 │           │                         │     │                                              │
 │           v                         │     │                                              │
 │  ┌─────────────────────────┐        │     │                                              │
 │  │     run_eval.py         │        │     │                                              │
 │  │                         │        │     │                                              │
 │  │  1. Load config + Qs    │        │     │                                              │
 │  │  2. Resolve dynamic GT ─┼────────┼────>│  Execute validation_query SQL                │
 │  │     (validation_query)  │<───────┼─────│  Return live data for answer_template        │
 │  │  3. Load Qs to table ───┼────────┼────>│  CREATE TABLE ... INSERT INTO                │
 │  │  4. Upload eval YAML ───┼────────┼────>│  COPY INTO @stage/eval.yaml                  │
 │  │  5. Start eval ─────────┼────────┼────>│  EXECUTE_AI_EVALUATION('START', ...)          │
 │  │  6. Poll status ────────┼────────┼────>│  EXECUTE_AI_EVALUATION('STATUS', ...)         │
 │  │     (every 30s)         │<───────┼─────│  CREATED -> IN_PROGRESS -> COMPLETED          │
 │  │  7. Fetch results ──────┼────────┼────>│  GET_AI_EVALUATION_DATA(...)                  │
 │  │  8. Fetch errors ───────┼────────┼────>│  GET_AI_OBSERVABILITY_LOGS(...)               │
 │  │  9. Check thresholds    │        │     │                                              │
 │  │ 10. Save JSON ──┐       │        │     │                                              │
 │  │ 11. Print report│       │        │     │      ┌──────────────────────────┐             │
 │  └─────────────────┼───────┘        │     │      │   Cortex Agent           │             │
 │                    v                │     │      │   (under evaluation)     │             │
 │  results/                           │     │      │                          │             │
 │    agent_20260401_173852.json       │     │      │  Semantic Views ──┐      │             │
 │    {summary, thresholds,            │     │      │  Search Services ─┤      │             │
 │     passed, results[]}              │     │      │  Custom Procs ────┘      │             │
 │                                     │     │      └──────────────────────────┘             │
 │  Exit code: 0 (pass) / 1 (fail)    │     │                                              │
 │                                     │     │                                              │
 └─────────────────────────────────────┘     └──────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────────────────────────────────────┐
  │  Optional: --env dev/qa/prod                                                          │
  │  Loads environments/{env}.env.yml to override database, schema, warehouse, role,       │
  │  and version_suffix (e.g. RESORT_EXECUTIVE -> RESORT_EXECUTIVE_DEV)                     │
  └──────────────────────────────────────────────────────────────────────────────────────────┘
```

## Evaluation Dataset Lifecycle

Each evaluation run creates several artifacts in Snowflake. Understanding where they live and how they accumulate is important for debugging and cleanup.

### What gets created per eval run

```
run_eval.py
  │
  ├── 1. EVAL DATA TABLE (overwritten each run)
  │      {DB}.AGENTS.{AGENT_NAME}_EVAL_DATA
  │      Columns: input_query (VARCHAR), output (VARIANT)
  │      Contains questions + resolved ground truth
  │
  ├── 2. EVAL CONFIG YAML (uploaded to stage)
  │      @{DB}.AGENTS.EVAL_CONFIG_STAGE/{agent}_eval_{timestamp}.yaml
  │      Snowflake-format config consumed by EXECUTE_AI_EVALUATION
  │
  └── 3. DATASET OBJECT (one per run — accumulates)
         {DB}.AGENTS.{AGENT_NAME}_EVAL_DS_{timestamp}
         Snowflake DATASET with a system-managed version
         Created by EXECUTE_AI_EVALUATION, never auto-cleaned
```

### Artifact behavior

| Artifact | Created by | Lifecycle | Accumulates? |
|----------|-----------|-----------|--------------|
| `*_EVAL_DATA` table | `run_eval.py` (CREATE OR REPLACE) | **Overwritten** each run — always reflects the latest questions and ground truth | No |
| `@EVAL_CONFIG_STAGE/*.yaml` | `run_eval.py` (PUT) | One file per run, stays on stage | Yes |
| `*_EVAL_DS_*` dataset | `EXECUTE_AI_EVALUATION` | One per run, never deleted automatically | **Yes — grows over time** |

### Querying eval data directly

The eval data table is a regular Snowflake table and fully queryable:

```sql
-- See current questions and ground truth
SELECT
    input_query AS question,
    output:ground_truth_output::STRING AS ground_truth
FROM AM_SKI_RESORT_DEV.AGENTS.RESORT_EXECUTIVE_EVAL_DATA;

-- Count questions per agent
SELECT COUNT(*) FROM AM_SKI_RESORT_DEV.AGENTS.RESORT_EXECUTIVE_EVAL_DATA;   -- 15
SELECT COUNT(*) FROM AM_SKI_RESORT_DEV.AGENTS.SKI_OPS_ASSISTANT_EVAL_DATA;  -- 10
```

Eval **results** (scores, explanations) are queryable via system functions — see [Querying Results via SQL](#querying-results-via-sql).

### Listing eval artifacts

```sql
-- Tables (eval data)
SHOW TABLES LIKE '%EVAL%' IN SCHEMA AM_SKI_RESORT_DEV.AGENTS;

-- Datasets (one per eval run — these accumulate)
SHOW DATASETS IN AM_SKI_RESORT_DEV.AGENTS;

-- Stage files (eval config YAMLs)
LIST @AM_SKI_RESORT_DEV.AGENTS.EVAL_CONFIG_STAGE;
```

### Cleanup

Dataset objects accumulate and are never auto-deleted. After many eval runs you may want to prune old ones:

```sql
-- View all eval datasets
SHOW DATASETS IN AM_SKI_RESORT_DEV.AGENTS;

-- Drop a specific old dataset
DROP DATASET AM_SKI_RESORT_DEV.AGENTS.RESORT_EXECUTIVE_EVAL_DS_20260406_110203;

-- Remove old stage config files
REMOVE @AM_SKI_RESORT_DEV.AGENTS.EVAL_CONFIG_STAGE/resort_executive_eval_20260406_110203.yaml;
```

> **Note:** The `*_EVAL_DATA` tables are safe to overwrite — they are recreated from your YAML dataset every run. Do **not** drop the `EVAL_CONFIG_STAGE` stage itself, only individual files within it.

### Dynamic ground truth flow

When questions use `validation_query` + `answer_template` (recommended for data-driven questions), ground truth is resolved **at eval time** from live Snowflake data:

```
YAML dataset question
  │
  ├── validation_query: SQL executed against current data
  │     SELECT SUM(REVENUE) AS total ...
  │
  ├── answer_template: Python format string
  │     "Total revenue was ${total:,.0f}"
  │
  └── Resolved at runtime → ground_truth
        "Total revenue was $2,619,109"
```

This means the same eval dataset produces different ground truth values as data changes — evaluations are always testing against **current** data, not a frozen snapshot. Questions should use relative time references (e.g., "most recent complete season") rather than hardcoded dates.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- A deployed Cortex Agent in Snowflake
- A Snowflake connection (see [Connection Setup](#connection-setup) below)

### Snowflake Grants

The role running evaluations needs these privileges:

```sql
-- Core eval permissions
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE <your_role>;
GRANT EXECUTE TASK ON ACCOUNT TO ROLE <your_role>;

-- Agent access
GRANT USAGE ON DATABASE <agent_db> TO ROLE <your_role>;
GRANT USAGE ON SCHEMA <agent_db>.<agent_schema> TO ROLE <your_role>;
GRANT USAGE ON AGENT <agent_db>.<agent_schema>.<agent_name> TO ROLE <your_role>;
GRANT MONITOR ON AGENT <agent_db>.<agent_schema>.<agent_name> TO ROLE <your_role>;

-- Eval infrastructure (tables, stages, datasets, file formats)
GRANT CREATE TABLE ON SCHEMA <agent_db>.<agent_schema> TO ROLE <your_role>;
GRANT CREATE STAGE ON SCHEMA <agent_db>.<agent_schema> TO ROLE <your_role>;
GRANT CREATE FILE FORMAT ON SCHEMA <agent_db>.<agent_schema> TO ROLE <your_role>;
GRANT CREATE DATASET ON SCHEMA <agent_db>.<agent_schema> TO ROLE <your_role>;
GRANT CREATE TASK ON SCHEMA <agent_db>.<agent_schema> TO ROLE <your_role>;

-- All tools the agent uses also need access grants for the eval role
```

### Connection Setup

The runner needs a Snowflake connection. Two options:

**Option A: `connections.toml` (recommended)**

Add to `~/.snowflake/connections.toml`:

```toml
[myconnection]
account = "your_account"
user = "YOUR_USER"
authenticator = "SNOWFLAKE_JWT"
private_key_path = "~/.snowflake/keys/your_key.p8"
```

Then use `--connection myconnection`. The runner handles `~` expansion automatically (the native connector does not).

**Option B: Explicit flags**

```bash
--account YOUR_ACCOUNT --user YOUR_USER --private-key-path ~/.snowflake/keys/your_key.p8
```

## Install

```bash
cd agent-evaluation
uv sync
```

## Quick Start

### 1. Copy the example config and questions

```bash
cp configs/resort_executive.yaml configs/<your_agent>.yaml
cp datasets/resort_executive_eval.yaml datasets/<your_agent>_eval.yaml
```

### 2. Edit the config

Update `configs/<your_agent>.yaml` with your agent name, database, schema, and Snowflake objects:

```yaml
agent:
  name: "MY_AGENT"
  database: "MY_DB"
  schema: "MY_SCHEMA"

dataset:
  questions: "datasets/my_agent_eval.yaml"
  snowflake_table: "MY_DB.MY_SCHEMA.MY_AGENT_EVAL_DATA"

snowflake:
  stage: "MY_DB.MY_SCHEMA.eval_config_stage"
  file_format: "MY_DB.MY_SCHEMA.yaml_file_format"
  warehouse: "COMPUTE_WH"

evaluation:
  label: "MY_AGENT evaluation"
  description: "Answer correctness + logical consistency"

thresholds:
  answer_correctness: {{ eval.thresholds.answer_correctness }}
  logical_consistency: {{ eval.thresholds.logical_consistency }}

metrics:
  - "answer_correctness"
  - "logical_consistency"
```

All `snowflake_table`, `stage`, and `file_format` values must be fully qualified (`DB.SCHEMA.OBJECT`).

**Thresholds are templated from environment configs.** The `{{ eval.thresholds.* }}` placeholders resolve from `environments/<env>.env.yml` at render time:

| Environment | `answer_correctness` | `logical_consistency` |
|-------------|---------------------|-----------------------|
| DEV | 0.60 | 0.60 |
| QA | 0.70 | 0.70 |
| PROD | 0.80 | 0.80 |

This lets DEV be more lenient while PROD enforces stricter quality gates. To change thresholds, edit the `eval.thresholds` section in the corresponding `environments/<env>.env.yml` file — not the config templates.

When the runner exits with code 1, a metric fell below its threshold — useful for CI/CD gating.

### 3. Write evaluation questions

Edit `datasets/<your_agent>_eval.yaml`. Each question needs ground truth — either dynamic or static.

**Dynamic ground truth** (recommended for data questions):

The runner executes the `validation_query` SQL at eval time and formats the result into `answer_template`:

```yaml
questions:
  - question: "What was total revenue for the most recent complete quarter?"
    expected_tools: ["RevenueAnalytics"]
    category: revenue
    tags: [quarterly, dynamic]
    test_type: in_scope
    validation_query: |
      SELECT ROUND(SUM(REVENUE), 0) AS total_revenue, COUNT(*) AS order_count
      FROM MY_DB.MY_SCHEMA.SALES
      WHERE QUARTER = (SELECT MAX(QUARTER) FROM MY_DB.MY_SCHEMA.SALES WHERE QUARTER_END < CURRENT_DATE())
    answer_template: "Total revenue was ${total_revenue:,.0f} from {order_count:,} orders."
```

How it works: the query returns columns (`total_revenue`, `order_count`), and the template fills `{column_name}` placeholders with those values. Python format specs like `:,.0f` (comma-separated, no decimals) work in the template.

**Static ground truth** (for boundary tests or stable facts):

```yaml
  - question: "What is the stock price?"
    expected_tools: []
    category: boundary
    test_type: out_of_scope
    ground_truth: "Agent should decline — stock data is outside its domain."
```

**When to use which:**

| Scenario | Approach | Why |
|----------|----------|-----|
| Revenue, counts, metrics | Dynamic (`validation_query` + `answer_template`) | Data changes — ground truth stays fresh |
| Boundary / out-of-scope | Static (`ground_truth`) | Expected behavior doesn't change |
| Dimension lookups (e.g. customer segments) | Either | Static if stable, dynamic if segments change |

**Question fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `question` | Yes | Natural language question to ask the agent |
| `validation_query` | No | SQL executed at eval time to generate fresh ground truth |
| `answer_template` | With `validation_query` | Template with `{column}` placeholders filled from query results |
| `ground_truth` | Without `validation_query` | Static expected answer (used as-is) |
| `expected_tools` | No | Which agent tools should handle this question |
| `category` | No | Group for filtered reporting (`--category revenue`) |
| `tags` | No | Tags for filtering (`--tag quarterly`) |
| `test_type` | No | `in_scope`, `out_of_scope`, or `negative` |

### 4. Preview with dry-run

```bash
uv run python scripts/run_eval.py configs/my_agent.yaml --dry-run
```

This shows the full plan — questions, categories, generated Snowflake YAML — without touching Snowflake. Always do this first.

### 5. Test your ground truth

```bash
uv run python scripts/run_eval.py configs/my_agent.yaml --resolve-only --connection myconnection
```

This connects to Snowflake, runs every `validation_query`, formats every `answer_template`, and prints the resolved ground truth. Fix any query errors before running the full eval.

### 6. Run the evaluation

```bash
uv run python scripts/run_eval.py configs/my_agent.yaml --connection myconnection
```

The runner will:
1. Resolve dynamic ground truth from live Snowflake data
2. Load questions into the eval table
3. Upload the generated Snowflake YAML to the stage
4. Start the evaluation
5. Poll status every 30 seconds until complete (~5-10 min for 15 questions)
6. Print results, check thresholds, and save JSON

**Example output:**

```
=== Evaluating RESORT_EXECUTIVE ===

1. Resolving dynamic ground truth...
  Dynamic ground truth: 15 resolved, 0 failed, 0 static

2. Loading questions into Snowflake...
  Table: SADM_SKI_RESORT_DB.AGENTS.RESORT_EXECUTIVE_EVAL_DATA (15 rows)

3. Setting up stage...
4. Generating and uploading Snowflake YAML...
5. Starting evaluation...
  Run started: resort_executive_eval_20260401_173349

6. Polling every 30s (max 60 attempts)...
  [01] Status: CREATED
  [02] Status: INVOCATION_IN_PROGRESS
  [03] Status: INVOCATION_IN_PROGRESS
  [04] Status: COMPUTATION_IN_PROGRESS
  [07] Status: COMPLETED

7. Fetching results...

============================================================
EVALUATION RESULTS — RESORT_EXECUTIVE
Run: resort_executive_eval_20260401_173349  |  Records: 15
============================================================
  answer_correctness        0.668  (n= 15)
  logical_consistency       0.889  (n= 15)

============================================================
THRESHOLD CHECK
============================================================
  answer_correctness        0.668  (threshold: 0.70)  [FAIL]
  logical_consistency       0.889  (threshold: 0.80)  [PASS]

  Overall: FAILED
  Results saved: agent-evaluation/results/resort_executive_20260401_173852.json

Snowsight: https://app.snowflake.com/org/account/#/agents/database/DB/schema/SCHEMA/agent/AGENT/evaluations/RUN_NAME/records
```

### 7. Iterate

1. Edit `datasets/<agent>_eval.yaml` — add/change questions or refine ground truth
2. Re-run: `uv run python scripts/run_eval.py configs/<agent>.yaml --connection myconnection`

Each run gets a unique timestamped name — previous results are always preserved.

## CLI Reference

```bash
uv run python scripts/run_eval.py <config.yaml> [flags]
```

| Flag | Description |
|------|-------------|
| `--connection NAME` | Snowflake connection from `connections.toml` (handles `~` expansion) |
| `--account` / `--user` / `--private-key-path` | Explicit auth (alternative to `--connection`) |
| `--dry-run` | Show plan without touching Snowflake |
| `--resolve-only` | Run `validation_query` SQL and print ground truth (no eval) |
| `--no-wait` | Start the eval and exit without polling |
| `--poll-interval N` | Seconds between status polls (default: 30) |
| `--env {dev,qa,prod}` | Override db/schema/warehouse/role from `environments/<env>.env.yml` |
| `--status` | Check status of the last run |
| `--results` | Print results of the last run |
| `--run-name NAME` | Override auto-generated run name |
| `--category NAME` | Filter to questions in this category |
| `--tag NAME` | Filter to questions with this tag (repeatable) |

### Using Makefile shortcuts

From the repo root:

```bash
make eval AGENT=resort_executive              # Full eval (polls, thresholds, JSON)
make eval-dry-run AGENT=resort_executive      # Dry run
make eval-status AGENT=resort_executive       # Check status
make eval-results AGENT=resort_executive      # View results
```

The Makefile uses `--connection myconnection` and `--env dev` by default. Override with `ENV=prod`.

## Environment Configs

The `--env` flag loads `environments/<env>.env.yml` and overrides the agent's database, schema, warehouse, role, and name suffix. This lets a single config YAML target dev, qa, or prod:

```bash
# Evaluate RESORT_EXECUTIVE_DEV in dev environment
uv run python scripts/run_eval.py configs/resort_executive.yaml --connection myconnection --env dev

# Evaluate RESORT_EXECUTIVE (no suffix) in prod
uv run python scripts/run_eval.py configs/resort_executive.yaml --connection myconnection --env prod
```

Example env file (`environments/dev.env.yml`):

```yaml
environment: dev
snowflake:
  account: trb65519
  role: AM_DEPLOY_ROLE_DEV
  warehouse: AM_SKI_RESORT_WH_DEV
deployment:
  database: AM_SKI_RESORT_DEV
  semantic_schema: SEMANTIC
  agents_schema: AGENTS
agent:
  name_suffix: _DEV    # RESORT_EXECUTIVE -> RESORT_EXECUTIVE_DEV
eval:
  thresholds:
    answer_correctness: 0.60    # DEV is more lenient
    logical_consistency: 0.60
```

Thresholds are injected into eval config templates via `{{ eval.thresholds.answer_correctness }}` etc. To adjust pass/fail gates, edit the `eval.thresholds` section in the environment config — the template configs and generated configs update automatically.

## Understanding Results

### Scores

| Metric | Scale | What it measures |
|--------|-------|------------------|
| `answer_correctness` | 0.0 – 1.0 | How closely the agent's answer matches ground truth (LLM judge) |
| `logical_consistency` | 0.0 – 1.0 | Internal coherence of reasoning, planning, and tool calls (no ground truth needed) |
| Custom (e.g. `boundary_enforcement`) | 1 – 10 | Your own criteria via LLM-judged prompt |

**Score interpretation for `answer_correctness`:**

| Score | Meaning |
|-------|---------|
| 1.00 | Perfect match to ground truth |
| 0.67 | Partially correct — key facts present but incomplete or imprecise |
| 0.33 | Mostly wrong — some relevance but missing critical information |
| 0.00 | Completely wrong or no useful overlap with ground truth |

**Tips for improving scores:**
- Low `answer_correctness`: Check if the agent is using the right tool. Look at the `expected_tools` vs what the agent actually called. Tighten ground truth to focus on key facts only.
- Low `logical_consistency`: Check agent instructions for contradictions. Simplify orchestration prompts.
- Scores vary ~5-10% between runs due to LLM non-determinism. Look at trends across runs, not single scores.

### JSON Results File

Every run saves to `results/<agent>_<timestamp>.json`:

```json
{
  "agent": "RESORT_EXECUTIVE",
  "run_name": "resort_executive_eval_20260401_173349",
  "timestamp": "20260401_173852",
  "passed": false,
  "thresholds": {"answer_correctness": 0.60, "logical_consistency": 0.60},
  "summary": {
    "answer_correctness": {"avg": 0.668, "n": 15},
    "logical_consistency": {"avg": 0.889, "n": 15}
  },
  "total_records": 30,
  "results": [ ... ]   // per-record scores with question, output, ground_truth, explanation
}
```

Use these for historical comparison, CI reporting, or dashboarding.

### Snowsight UI

The runner prints a Snowsight URL at the end. Open it to see the visual evaluation dashboard with per-question drilldowns, agent traces, and score distributions.

## Querying Results via SQL

### Summary scores
```sql
SELECT
    METRIC_NAME,
    ROUND(AVG(EVAL_AGG_SCORE), 4) AS avg_score,
    COUNT(*) AS record_count,
    SUM(CASE WHEN EVAL_AGG_SCORE >= 0.8 THEN 1 ELSE 0 END) AS high_accuracy,
    SUM(CASE WHEN EVAL_AGG_SCORE < 0.3 THEN 1 ELSE 0 END) AS low_accuracy
FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(
    '<DB>', '<SCHEMA>', '<AGENT>', 'CORTEX AGENT', '<RUN_NAME>'
))
GROUP BY METRIC_NAME;
```

### Per-question breakdown
```sql
SELECT
    LEFT(INPUT, 80) AS question,
    METRIC_NAME,
    ROUND(EVAL_AGG_SCORE, 2) AS score,
    LEFT(METRIC_CALLS[0]:explanation::STRING, 300) AS explanation
FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(
    '<DB>', '<SCHEMA>', '<AGENT>', 'CORTEX AGENT', '<RUN_NAME>'
))
ORDER BY METRIC_NAME, EVAL_AGG_SCORE ASC;
```

### Trace a single record
```sql
SELECT * FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_RECORD_TRACE(
    '<DB>', '<SCHEMA>', '<AGENT>', 'CORTEX AGENT', '<RECORD_ID>'
));
```

### Errors and warnings
```sql
SELECT * FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_OBSERVABILITY_LOGS(
    '<DB>', '<SCHEMA>', '<AGENT>', 'CORTEX AGENT')
)
WHERE record_attributes:"snow.ai.observability.run.name" = '<RUN_NAME>'
AND record:"severity_text" IN ('ERROR', 'WARN');
```

## Custom Metrics

Add to the `metrics` section of your config YAML. The prompt can reference `{{input}}`, `{{output}}`, `{{ground_truth}}`, `{{tool_info}}`, `{{duration}}`, `{{status}}`, and `{{error}}`.

```yaml
metrics:
  - "answer_correctness"
  - "logical_consistency"
  - name: "boundary_enforcement"
    score_ranges:
      min_score: [1, 3]
      median_score: [4, 6]
      max_score: [7, 10]
    prompt: |
      Evaluate whether the agent correctly enforced its scope boundaries.
      For OUT-OF-SCOPE questions: score 1 if agent answers anyway.
      For IN-SCOPE questions: score 1 if agent declines.
      Rate 1-10. Input: {{input}} Output: {{output}} Expected: {{ground_truth}}
```

See `configs/resort_executive.yaml` for the full `boundary_enforcement` prompt.

## File Structure

```
agent-evaluation/
  README.md                              # This file
  SKILL.md                               # Cortex Code assistant workflow
  pyproject.toml                         # Dependencies (uv sync)
  configs/                               # One config per agent
    resort_executive.yaml                #   Agent + dataset + metrics + thresholds
    resort_executive_eval_config.yaml    #   Snowflake-format template with {PLACEHOLDERS}
  datasets/                              # One questions file per agent
    resort_executive_eval.yaml           #   Questions + ground truth (YAML, dynamic)
    resort_executive_eval_20260401.md    #   Run review notes
  results/                               # JSON results from runs
    resort_executive_20260401_173852.json #  Summary + thresholds + per-record scores
  references/
    dynamic-ground-truth.md              #   Patterns for validation_query + answer_template
  scripts/
    run_eval.py                          #   End-to-end runner
    load_eval_dataset.py                 #   Standalone CSV → Snowflake loader
    convert_eval_dataset.py              #   Convert existing table to eval format
    invoke_agent.py                      #   Test single question via REST API
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `answer_correctness` scores all 0% | Ground truth not linked. Use `run_eval.py` — it handles column mapping automatically (Approach A). Do not pre-create datasets with `SYSTEM$CREATE_EVALUATION_DATASET`. |
| `validation_query` errors during `--resolve-only` | Check SQL syntax against your actual tables. Columns in the query must match `{placeholders}` in `answer_template`. |
| `connection_name` fails with key error | The connector doesn't expand `~` in `private_key_path`. Use `--connection` with this runner (it handles expansion) or use explicit `--account`/`--user`/`--private-key-path` flags. |
| `Invalid source_metadata type: Unknown type: DATASET` | The type must be lowercase `"dataset"`. `run_eval.py` handles this correctly. |
| `Object name AGENT format should be 'database.schema.object'` | Agent name must be fully qualified. Check your config `agent.database`, `agent.schema`, and `agent.name`. |
| YAML corrupted after stage upload | Stage file format must use `FIELD_DELIMITER = NONE` and `ESCAPE_UNENCLOSED_FIELD = NONE`. `run_eval.py` creates this automatically. |
| Eval stuck in `INVOCATION_IN_PROGRESS` for >15 min | Complex agents with many tools take longer. Default max wait is 30 min (60 polls × 30s). Check Snowflake query history for errors. |
| Scores vary between runs | Normal — LLM judge has ~5-10% variance. Compare trends across multiple runs using the JSON files in `results/`. |
| `--env` produces wrong agent name | The suffix is appended only if not already present. Check `environments/<env>.env.yml` has the correct `name_suffix` under `agent:`. |

## Example: RESORT_EXECUTIVE

15 questions, all dynamic ground truth, run against `AM_SKI_RESORT.AGENTS.RESORT_EXECUTIVE`:

| Metric | Avg Score | Count | High (>=0.8) | Low (<0.3) | Threshold | Gate |
|--------|-----------|-------|--------------|------------|-----------|------|
| answer_correctness | **66.8%** | 15 | 5 | 2 | 60% (DEV) | PASS |
| logical_consistency | **88.9%** | 15 | 12 | 0 | 60% (DEV) | PASS |

Full results: `results/resort_executive_20260401_173852.json`

## CI/CD Integration

In GitHub Actions, agent evaluations run as the final step of each deploy workflow:

1. **DEV** (`deploy-dev.yml`): Eval runs with `continue-on-error: true` — failures warn but don't block
2. **QA** (`promote-qa.yml`): Eval is a **gate** — failure blocks the promotion
3. **PROD** (`promote-prod.yml`): Eval is a **gate** — failure triggers auto-rollback from snapshot

The eval step uses GitHub environment variables (`environment: DEV/QA/PROD`) so `SNOWFLAKE_DATABASE`, `SNOWFLAKE_ROLE`, and `SNOWFLAKE_WAREHOUSE` resolve to the correct values per environment. These are stored as `vars` (not `secrets`) so they appear unmasked in CI logs — important for clickable Snowsight URLs. Authentication uses RSA key-pair (JWT) secrets — no passwords.
