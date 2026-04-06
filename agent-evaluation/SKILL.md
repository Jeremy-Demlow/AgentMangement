---
name: agent-evaluation
description: "Evaluate Cortex Agents using native Snowflake Agent Evaluations (GA). Use when: running agent evaluations, testing agent accuracy, measuring answer correctness, checking logical consistency. Triggers: evaluate agent, run agent evaluation, test agent accuracy, agent metrics."
---

# Agent Evaluation

Evaluate Cortex Agents using the native Snowflake Agent Evaluations feature (GA — no longer in preview).

**Available Metrics:**
| Metric | API Name | Requires Ground Truth | Description |
|--------|----------|----------------------|-------------|
| Answer Correctness | `answer_correctness` | Yes | How closely the agent's answer matches expected output |
| Logical Consistency | `logical_consistency` | No | Consistency across agent instructions, planning, and tool calls (reference-free) |
| Custom | user-defined | Optional | LLM-judged metric with custom prompt and score ranges |

**Models Used for Judging:**
Evaluations use `claude-4-sonnet` or `claude-3-5-sonnet` via cross-region inference. Snowflake selects automatically based on account settings.

## Prerequisites

**Access Control Setup:**
```sql
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE <role>;
GRANT EXECUTE TASK ON ACCOUNT TO ROLE <role>;
GRANT USAGE ON DATABASE <agent_db> TO ROLE <role>;
GRANT USAGE ON SCHEMA <agent_schema> TO ROLE <role>;
GRANT CREATE FILE FORMAT ON SCHEMA <agent_schema> TO ROLE <role>;
GRANT CREATE TASK ON SCHEMA <agent_schema> TO ROLE <role>;
GRANT EXECUTE TASK ON SCHEMA <agent_schema> TO ROLE <role>;
GRANT USAGE ON DATABASE <eval_data_db> TO ROLE <role>;
GRANT USAGE ON SCHEMA <eval_data_schema> TO ROLE <role>;
GRANT EXECUTE TASK ON SCHEMA <eval_data_schema> TO ROLE <role>;
-- If creating a dataset from an input table:
GRANT CREATE DATASET ON SCHEMA <eval_data_schema> TO ROLE <role>;
GRANT USAGE ON AGENT <database>.<schema>.<agent> TO ROLE <role>;
GRANT MONITOR ON AGENT <database>.<schema>.<agent> TO ROLE <role>;
-- If using a config file on a stage:
GRANT READ ON STAGE <config_stage> TO ROLE <role>;
-- All tools the agent uses also need access grants
```

## Workflow

**⚠️ FIRST: Present plan and confirm with user before taking any action.**

```
I'll help you evaluate your Cortex Agent. Here's the workflow:

1. Identify Agent - Confirm which agent to evaluate
2. Choose Metrics - Select evaluation metrics (answer_correctness, logical_consistency, custom)
3. Dataset Setup - Use existing dataset or create new one
4. Build Config - Create YAML evaluation config and upload to stage
5. Run Evaluation - Execute evaluation against the agent
6. View Results - Review scores in Snowsight or via SQL

Ready to proceed?
```

**⚠️ STOP**: Wait for user confirmation before proceeding to Step 1.

---

### Step 1: Identify Agent and Gather Info

**Ask user:**
```
Which agent do you want to evaluate?
- Agent name (fully qualified: DATABASE.SCHEMA.AGENT_NAME)
- Connection to use
```

**⚠️ CRITICAL: If the agent name is ambiguous or unclear, DO NOT ASSUME.**

List available agents and ask the user to confirm:
```sql
SHOW AGENTS IN SCHEMA <DATABASE>.<SCHEMA>;
-- Or search across databases:
SHOW AGENTS IN ACCOUNT;
```

**Extract agent configuration:**
```sql
DESC AGENT <DATABASE>.<SCHEMA>.<AGENT_NAME>;
```

The `agent_spec` column contains a JSON object with the full agent configuration.

**Parse tools from agent spec (recommended — run immediately after DESC):**
```sql
DESC AGENT <DATABASE>.<SCHEMA>.<AGENT_NAME>;

SELECT
    f.value:tool_spec:name::STRING AS tool_name,
    f.value:tool_spec:type::STRING AS tool_type,
    LEFT(f.value:tool_spec:description::STRING, 250) AS tool_desc
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID())) t,
LATERAL FLATTEN(input => PARSE_JSON(t."agent_spec"):tools) f;
```

**Column reference:**
| Index | Column | Description |
|-------|--------|-------------|
| 0 | name | Agent name |
| 1 | database_name | Database |
| 2 | schema_name | Schema |
| 3 | owner | Owner role |
| 4 | comment | Agent comment |
| 5 | profile | Profile (usually NULL) |
| 6 | agent_spec | **JSON spec with tools & instructions** |
| 7 | created_on | Creation timestamp |

**Key fields in agent_spec:**
| Field | Description |
|-------|-------------|
| `tools[]` | Array of tools with `tool_spec` (type, name, description) |
| `instructions.orchestration` | Agent's routing/behavior instructions |
| `instructions.response` | Response formatting guidelines |
| `tool_resources` | Tool configurations (semantic views, search services, etc.) |

**Tool types:**
| Type | Description |
|------|-------------|
| `cortex_analyst_text_to_sql` | Semantic view queries |
| `cortex_search` | Search service queries |
| `generic` | Custom procedures/functions |

**Present to user:**
```
Agent: DATABASE.SCHEMA.AGENT_NAME
Tools found:
1. revenue_analyst (cortex_analyst_text_to_sql) - Revenue and sales data
2. policy_search (cortex_search) - Company policies
3. get_weather (generic) - Weather lookups

I'll help you create an evaluation dataset for this agent.
```

**⚠️ STOP**: Confirm agent details before proceeding.

---

### Step 2: Choose Evaluation Metrics

**Ask user:**
```
Which metrics do you want to evaluate?

1. [ ] answer_correctness - Does the agent give correct answers?
       Requires: ground_truth_output for each question

2. [ ] logical_consistency - Measures consistency across agent instructions, planning, and tool calls
       Requires: nothing (reference-free)

3. [ ] custom - Define your own LLM-judged metric with a prompt and score ranges
       Requires: depends on your prompt definition

Select metrics (e.g., "1,2" or "all" or "just logical_consistency"):
```

**Based on selection, determine dataset requirements:**

| If user selects... | Dataset needs... |
|-------------------|------------------|
| Only `logical_consistency` | Just `input_query` column |
| `answer_correctness` | `input_query` + `output` VARIANT with `ground_truth_output` |
| Custom metric | Depends on prompt — can reference `{{output}}`, `{{ground_truth}}`, etc. |

**⚠️ STOP**: Confirm metrics selection before proceeding.

**If ONLY `logical_consistency` selected → Skip to Step 3 Option C** (simplified flow, no ground truth needed)

**If `answer_correctness` or custom metric selected:**
- Use **concise factual statements** for `ground_truth_output` (1-2 sentences max)
- Example: `"Back to School has highest ROI at 203%, followed by Spring Fashion at 188%."`
- Do NOT use verbose multi-paragraph responses — they reduce LLM judge accuracy

---

### Step 3: Create Evaluation Dataset

**Option A: Use existing evaluation dataset or table**

First, check for existing datasets:
```sql
SHOW DATASETS IN SCHEMA <DATABASE>.<SCHEMA>;
```

Present any existing datasets to the user:
```
I found the following existing evaluation datasets:
1. AGENT_NAME_EVAL_DS_20260101 (created 2026-01-01)
2. AGENT_NAME_EVAL_DS_20251215 (created 2025-12-15)

Would you like to use one of these, or create a new one?
```

If user selects an existing dataset, query agent logs (Step 3.1) to check for new question patterns. Present findings, then offer to add new questions.

If user has an existing table not yet registered → Skip to Step 3.6 to format and register it.

If no existing dataset or table → Proceed to Option B.

**Option B: Build dataset with assistant**

The assistant proposes a complete evaluation dataset based on the agent's tools and persona.

**Target: 10-20 queries** depending on agent complexity:
- Simple agent (1-2 tools): 10-12 queries
- Medium agent (3-4 tools): 12-16 queries
- Complex agent (5+ tools): 16-20 queries

#### Step 3.1: Query Agent Logs for Existing Questions

Before creating new questions, check observability logs for real user questions.

```sql
SELECT DISTINCT
    RECORD_ATTRIBUTES:"ai.observability.record_root.input"::STRING AS user_question,
    RECORD_ATTRIBUTES:"ai.observability.record_root.output"::STRING AS agent_response,
    RECORD_ATTRIBUTES:"ai.observability.record_id"::STRING AS request_id
FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_OBSERVABILITY_EVENTS(
    '<DATABASE>',
    '<SCHEMA>',
    '<AGENT_NAME>',
    'CORTEX AGENT'))
WHERE RECORD_ATTRIBUTES:"ai.observability.span_type" = 'record_root'
AND user_question IS NOT NULL
LIMIT 50;
```

**⚠️ NOTE**: If no logs exist or access is denied, proceed with questions based on agent spec.

#### Step 3.2: Review Agent Instructions First

**CRITICAL: Before creating questions, understand what the agent is designed to do.**

Check `DESCRIBE AGENT` for guardrails, persona, and sample questions. Creating analytics questions for a customer-service agent (or vice versa) causes 0% accuracy scores.

#### Step 3.3: Time-Anchor Questions

Questions can use **static** or **dynamic** time anchoring. Prefer dynamic for data questions so ground truth stays fresh.

**Option A: Static Time Anchoring** (pinned to specific date — simpler, but ground truth goes stale)

| ❌ Bad (non-reproducible) | ✅ Good (reproducible) |
|---------------------------|------------------------|
| What's the most popular product? | What's the most popular product as of December 31, 2025? |
| Show me revenue this month | Show me revenue for December 2025 |

**Option B: Dynamic Time Anchoring** (relative references + `validation_query` — **recommended**)

| Static (goes stale) | Dynamic (stays fresh) |
|---------------------|-----------------------|
| What was ticket revenue for the 2024-2025 season? | What was our total ticket revenue for the most recent complete season? |
| How did December 2025 compare to December 2024? | How does the current season compare to last season so far? |

Dynamic questions use `validation_query` to generate ground truth at eval time. See **`references/dynamic-ground-truth.md`** for patterns and examples.

**Determine data range from underlying tables:**
```sql
SELECT
    MIN(timestamp_column) AS earliest_data,
    MAX(timestamp_column) AS latest_data,
    COUNT(*) AS total_records
FROM <DATABASE>.<SCHEMA>.<TABLE>;
```

#### Step 3.4: Generate Ground Truth

Two approaches — choose based on whether data changes between eval runs.

**Approach 1: Dynamic Ground Truth via `validation_query` (Recommended)**

Use `validation_query` + `answer_template` so ground truth is generated from live data at eval time. The runner (`run_eval.py`) executes the SQL query, then formats the results into the `answer_template`.

```yaml
- question: "What was our total ticket revenue for the most recent complete season?"
  validation_query: |
    SELECT d.SKI_SEASON AS season, ROUND(SUM(t.PURCHASE_AMOUNT), 2) AS total_revenue
    FROM FACT_TICKET_SALES t JOIN DIM_DATE d ON t.PURCHASE_DATE_KEY = d.DATE_KEY
    WHERE d.SKI_SEASON = (SELECT MAX(SKI_SEASON) FROM DIM_DATE WHERE FULL_DATE < CURRENT_DATE())
    GROUP BY d.SKI_SEASON
  answer_template: "Total ticket revenue for the {season} season was approximately ${total_revenue:,.0f}."
```

See **`references/dynamic-ground-truth.md`** for full patterns: current-season totals, YoY comparisons, top-N rankings.

**Approach 2: Static Ground Truth** (for dimension/boundary questions that don't change)

```yaml
- question: "What are the largest customer segments?"
  ground_truth: "vacation_family (2,400), weekend_warrior (2,000), day_tripper (1,600)."
```

**DO NOT run the agent to capture ground truth.** Generate expected answers based on:
- The agent's tools and their purposes
- The semantic model / search corpus the tools access
- The agent's instructions and persona

**Guidelines:**
- 1-2 sentences with key facts
- Focus on the most important data points the answer should include
- Use natural language — the judge understands semantic equivalence
- Include `validation_query` for any question where the answer depends on data that may change

#### Step 3.5: Present Full Dataset for Review

Present the complete proposed dataset to the user in a table format:

```
| # | Question | Ground Truth |
|---|----------|--------------|
| 1 | What's the most popular product as of Dec 31, 2025? | Strawberry Frosted was the top seller with 1,240 units sold. |
| 2 | What was total revenue for Q4 2025? | Total Q4 2025 revenue was $2.4M. |
| ... | ... | ... |
```

**⚠️ STOP**: Get user approval on the full dataset before creating the table.

#### Step 3.5b: Save Dataset Review File Locally

After user approves the dataset, save a local markdown file for review and version control:

**File location:** `agent-evaluation/datasets/<agent_name>_eval_<YYYYMMDD>.md`

```markdown
# <AGENT_NAME> Evaluation Dataset
# Agent: <DATABASE>.<SCHEMA>.<AGENT_NAME>
# Anchor: <time period used>
# Metrics: <selected metrics>
# Created: <date>

## Questions and Ground Truth

| # | Target Tool | Question | Ground Truth |
|---|-------------|----------|--------------|
| 1 | ToolName | Question text | Expected answer |
| ... | ... | ... | ... |

## Snowflake Objects
- **Table:** `<DATABASE>.<SCHEMA>.<AGENT_NAME>_EVAL_DATA`
- **Dataset:** `<DATABASE>.<SCHEMA>.<AGENT_NAME>_EVAL_DS`
- **Config:** `@<DATABASE>.<SCHEMA>.eval_config_stage/<config_file>.yaml`
- **Run:** `<run_name>`
```

This file serves as:
- A **reviewable artifact** for team members to inspect before/after runs
- A **version-controlled record** of what was tested
- A **diffable baseline** when updating questions for future evaluations
- **Traceability** linking questions → tools → ground truth → Snowflake objects

#### Step 3.5c: Save Questions as YAML (Self-Service Artifact)

**ALWAYS generate this file.** This is the editable source of truth that lets users re-run evaluations without the skill.

**File location:** `agent-evaluation/datasets/<agent_name>_eval.yaml`

```yaml
# <AGENT_NAME> - Agent Evaluation Questions
#
# Test questions for <DATABASE>.<SCHEMA>.<AGENT_NAME>
# Tools: <comma-separated list of agent tools>
#
# Fields:
#   - question: Natural language question to ask the agent
#   - expected_tools: List of tools the agent should use
#   - category: Question category for reporting
#   - tags: Optional tags for filtering
#   - test_type: in_scope | out_of_scope | negative
#   - validation_query: SQL to get actual answer (optional, keeps ground truth fresh)
#   - ground_truth: Static ground truth (used when no validation_query)

questions:
  - question: "What was total revenue for the most recent complete season?"
    expected_tools: ["RevenueAnalytics"]
    category: revenue
    tags: [quarterly, total, dynamic]
    test_type: in_scope
    validation_query: |
      SELECT SKI_SEASON AS season, ROUND(SUM(REVENUE), 0) AS total_revenue
      FROM FACT_SALES JOIN DIM_DATE USING (DATE_KEY)
      WHERE SKI_SEASON = (SELECT MAX(SKI_SEASON) FROM DIM_DATE WHERE FULL_DATE < CURRENT_DATE())
      GROUP BY SKI_SEASON
    answer_template: "Total revenue for {season} was ${total_revenue:,.0f}."

  - question: "What is the stock price?"
    expected_tools: []
    category: boundary
    tags: [out_of_scope]
    test_type: out_of_scope
    ground_truth: "Agent should decline — stock data is outside its domain."
```

**Rules for generating this file:**
- One entry per question from the approved dataset
- `expected_tools` should list the agent tool(s) that handle this question (from Step 1 analysis)
- `category` should group related questions (e.g., `revenue`, `operations`, `boundary`)
- `test_type` must be `in_scope`, `out_of_scope`, or `negative`
- **Prefer `validation_query` + `answer_template`** for data questions — generates ground truth from live data at eval time (see `references/dynamic-ground-truth.md`)
- Use static `ground_truth` only for boundary tests or questions where the answer doesn't depend on data
- Out-of-scope and negative test questions should be commented out initially (user can uncomment when ready)

**Tell the user:** "I've saved the questions to `datasets/<agent>_eval.yaml`. You can edit this file to add/remove/change questions, then re-run without the skill."

**Option C: Reference-free evaluation only (logical_consistency)**

Simplified flow — just questions, no ground truth needed.

**Step C.1: Propose test questions covering all tools**

```
| # | Question |
|---|----------|
| 1 | What is the most popular product? |
| 2 | Show me sales trends for last month |
```

**Step C.2: Create and populate table**

```sql
CREATE OR REPLACE TABLE <DATABASE>.<SCHEMA>.<AGENT_NAME>_EVAL (
    input_query VARCHAR
);

INSERT INTO <DATABASE>.<SCHEMA>.<AGENT_NAME>_EVAL (input_query)
VALUES
    ('What is the most popular product?'),
    ('Show me sales trends for last month');
```

**Step C.3: Build YAML config and run evaluation (→ Skip to Step 4)**

#### Step 3.6: Create the Evaluation Table

The table for `answer_correctness` needs two columns:
- `input_query` — VARCHAR — the question
- `output` — VARIANT — `{"ground_truth_output": "..."}`

**CRITICAL: The `output` column must be type VARIANT.** Use `PARSE_JSON` to insert data.

```sql
CREATE OR REPLACE TABLE <DATABASE>.<SCHEMA>.<AGENT_NAME>_EVAL_DATA (
    input_query VARCHAR,
    output VARIANT
);
```

#### Step 3.7: Insert Ground Truth Data

```sql
INSERT INTO <DATABASE>.<SCHEMA>.<AGENT_NAME>_EVAL_DATA (input_query, output)
SELECT
    'What is the top campaign by ROI as of December 31, 2025?',
    PARSE_JSON('{"ground_truth_output": "Back to School Campaign has the highest ROI at 203%."}');

INSERT INTO <DATABASE>.<SCHEMA>.<AGENT_NAME>_EVAL_DATA (input_query, output)
SELECT
    'What was total revenue for Q4 2025?',
    PARSE_JSON('{"ground_truth_output": "Total Q4 2025 revenue was $2.4M, up 12% from Q3."}');
```

**Key requirements:**
- Column type: `VARIANT` (not VARCHAR)
- Use `PARSE_JSON` or `TO_VARIANT` — **not** `OBJECT_CONSTRUCT` or `ARRAY_CONSTRUCT` (they don't return VARIANT)
- JSON key must be `ground_truth_output`
- Value should be a concise factual statement

**Verify your table:**
```sql
SELECT input_query, output FROM <DATABASE>.<SCHEMA>.<AGENT_NAME>_EVAL_DATA LIMIT 3;
-- output column should show: {"ground_truth_output": "..."}
```

**⚠️ STOP**: Review dataset with user. Confirm questions and ground truth are correct.

---

### Step 4: Build Config File, Upload to Stage, and Run Evaluation

Agent evaluations use a YAML configuration file uploaded to a Snowflake stage.

#### Step 4.1: Set Up Stage

```sql
CREATE OR REPLACE FILE FORMAT <DATABASE>.<SCHEMA>.yaml_file_format
  TYPE = 'CSV'
  FIELD_DELIMITER = NONE
  RECORD_DELIMITER = '\n'
  SKIP_HEADER = 0
  FIELD_OPTIONALLY_ENCLOSED_BY = NONE
  ESCAPE_UNENCLOSED_FIELD = NONE;

CREATE OR REPLACE STAGE <DATABASE>.<SCHEMA>.eval_config_stage
  FILE_FORMAT = <DATABASE>.<SCHEMA>.yaml_file_format;
```

#### Step 4.2: Build YAML Configuration

Create the YAML config file locally. Adapt based on user's selected metrics.

**⚠️ CRITICAL YAML REQUIREMENTS (learned from real runs):**
- `agent_name` MUST be fully qualified: `DATABASE.SCHEMA.AGENT_NAME`
- `source_metadata.type` MUST be lowercase: `"dataset"` (not `"DATASET"`)
- Do NOT include `dataset_version` — it is not a recognized field
- The `dataset` section creates a NEW dataset from a table. If using `SYSTEM$CREATE_EVALUATION_DATASET` first, omit the `dataset` section and reference the existing dataset in `source_metadata`.

**Approach A: YAML creates the dataset (all-in-one):**

```yaml
dataset:
  dataset_type: "CORTEX AGENT"
  table_name: "<DATABASE>.<SCHEMA>.<AGENT_NAME>_EVAL_DATA"
  dataset_name: "<AGENT_NAME>_EVAL_DS"
  column_mapping:
    query_text: "INPUT_QUERY"
    ground_truth: "OUTPUT"

evaluation:
  agent_params:
    agent_name: "<DATABASE>.<SCHEMA>.<AGENT_NAME>"
    agent_type: "CORTEX AGENT"
  run_params:
    label: "<AGENT_NAME> evaluation"
    description: "Evaluation run"
  source_metadata:
    type: "dataset"
    dataset_name: "<DATABASE>.<SCHEMA>.<AGENT_NAME>_EVAL_DS"

metrics:
  - "answer_correctness"
  - "logical_consistency"
```

**Approach B: Pre-create dataset via SQL, then reference it:**

First register the dataset:
```sql
USE DATABASE <DATABASE>;
USE SCHEMA <SCHEMA>;

CALL SYSTEM$CREATE_EVALUATION_DATASET(
    'Cortex Agent',
    '<DATABASE>.<SCHEMA>.<AGENT_NAME>_EVAL_DATA',
    '<AGENT_NAME>_EVAL_DS',
    OBJECT_CONSTRUCT(
        'query_text', 'INPUT_QUERY',
        'ground_truth', 'OUTPUT'
    )
);
```

Then use a simpler YAML (no `dataset` section):
```yaml
evaluation:
  agent_params:
    agent_name: "<DATABASE>.<SCHEMA>.<AGENT_NAME>"
    agent_type: "CORTEX AGENT"
  run_params:
    label: "<AGENT_NAME> evaluation"
    description: "Evaluation run"
  source_metadata:
    type: "dataset"
    dataset_name: "<DATABASE>.<SCHEMA>.<AGENT_NAME>_EVAL_DS"

metrics:
  - "answer_correctness"
  - "logical_consistency"
```

**For `logical_consistency` only (no ground truth needed):**

```yaml
dataset:
  dataset_type: "CORTEX AGENT"
  table_name: "<DATABASE>.<SCHEMA>.<AGENT_NAME>_EVAL"
  dataset_name: "<AGENT_NAME>_EVAL_DS"
  column_mapping:
    query_text: "INPUT_QUERY"

evaluation:
  agent_params:
    agent_name: "<DATABASE>.<SCHEMA>.<AGENT_NAME>"
    agent_type: "CORTEX AGENT"
  run_params:
    label: "<AGENT_NAME> logical consistency evaluation"
  source_metadata:
    type: "dataset"
    dataset_name: "<DATABASE>.<SCHEMA>.<AGENT_NAME>_EVAL_DS"

metrics:
  - "logical_consistency"
```

**Recommended: `boundary_enforcement` custom metric**

Every agent with scope boundaries should include this metric. It catches agents answering out-of-scope questions OR declining in-scope ones.

```yaml
  - name: "boundary_enforcement"
    score_ranges:
      min_score: [1, 3]
      median_score: [4, 6]
      max_score: [7, 10]
    prompt: |
      Evaluate whether the agent correctly enforced its scope boundaries.

      For OUT-OF-SCOPE questions: the agent MUST politely decline and explain
      that the topic is outside its domain. Redirecting to another agent is ideal.
      Score 1 if the agent attempts to answer out-of-scope questions.

      For IN-SCOPE questions: the agent MUST attempt to answer using its tools.
      Score 1 if the agent declines an in-scope question.

      For NEGATIVE tests (invalid input, injection attempts): the agent MUST
      handle gracefully — no crash, no unhandled exception, no dangerous SQL.

      Compare {{output}} with {{ground_truth}} to determine the expected behavior.

      Rate 1-10 where:
      1  = Wrong behavior (answered out-of-scope OR declined in-scope)
      4  = Partially correct (vague decline, or answered but with caveats)
      7  = Correct behavior, clear explanation
      10 = Perfect — correct behavior, helpful redirect or thorough answer

      Input: {{input}}
      Agent output: {{output}}
      Expected behavior: {{ground_truth}}
```

To use `boundary_enforcement`, include boundary test cases in your dataset:

| Type | Example Question | Ground Truth |
|------|------------------|--------------|
| IN-SCOPE | What was Q4 revenue? | Total Q4 revenue was $2.4M... |
| OUT-OF-SCOPE | What's the stock price? | Agent should decline — stock data is outside its domain. |
| NEGATIVE | `'; DROP TABLE users; --` | Agent should handle gracefully with no SQL injection. |

**Custom metric replacement strings available:**

| String | Data |
|--------|------|
| `{{input}}` | Input query |
| `{{output}}` | Agent output |
| `{{ground_truth}}` | Ground truth |
| `{{tool_info}}` | Tool invocation details |
| `{{duration}}` | Response duration (ms) |
| `{{status}}` | HTTP status |
| `{{error}}` | Error info |

#### Step 4.2b: Save Templated Config for Reuse

**ALWAYS save the YAML config as a templated file** with `{PLACEHOLDERS}` for runtime substitution. This enables automated CI/CD evaluation runs.

Save to: `agent-evaluation/configs/<agent_name>_eval_config.yaml`

```yaml
# Eval config template for <AGENT_DESCRIPTION>
# Used by evaluations — {PLACEHOLDERS} are substituted at runtime.
#
# Metrics:
#   answer_correctness  — compares agent answer to NL ground truth (QA pairs)
#   logical_consistency — reference-free; checks planning coherence (all test types)
#   boundary_enforcement — custom; validates in-scope vs out-of-scope handling

dataset:
  dataset_type: "CORTEX AGENT"
  table_name: "{DATABASE}.{SCHEMA}.{AGENT_NAME}_EVAL_DATA"
  dataset_name: "{DATASET_NAME}"
  column_mapping:
    query_text: "INPUT_QUERY"
    ground_truth: "OUTPUT"

evaluation:
  agent_params:
    agent_name: "{DATABASE}.{SCHEMA}.{AGENT_NAME}"
    agent_type: "CORTEX AGENT"
  run_params:
    label: "{ENV} eval run"
    description: "Automated evaluation — {AGENT_NAME}"
  source_metadata:
    type: "dataset"
    dataset_name: "{DATASET_NAME}"

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

      For OUT-OF-SCOPE questions: the agent MUST politely decline and explain
      that the topic is outside its domain. Redirecting to another agent is ideal.
      Score 1 if the agent attempts to answer out-of-scope questions.

      For IN-SCOPE questions: the agent MUST attempt to answer using its tools.
      Score 1 if the agent declines an in-scope question.

      For NEGATIVE tests (invalid input, injection attempts): the agent MUST
      handle gracefully — no crash, no unhandled exception, no dangerous SQL.

      Compare {{output}} with {{ground_truth}} to determine the expected behavior.

      Rate 1-10 where:
      1  = Wrong behavior (answered out-of-scope OR declined in-scope)
      4  = Partially correct (vague decline, or answered but with caveats)
      7  = Correct behavior, clear explanation
      10 = Perfect — correct behavior, helpful redirect or thorough answer

      Input: {{input}}
      Agent output: {{output}}
      Expected behavior: {{ground_truth}}
```

**Runtime substitution (Python example):**
```python
import re
from pathlib import Path

template = Path("agent-evaluation/configs/agent_eval_config.yaml").read_text()
config = template.format(
    DATABASE="SADM_SKI_RESORT_DB",
    SCHEMA="AGENTS",
    AGENT_NAME="RESORT_EXECUTIVE",
    DATASET_NAME="SADM_SKI_RESORT_DB.AGENTS.RESORT_EXECUTIVE_EVAL_DS",
    ENV="dev"
)
Path("/tmp/eval_config.yaml").write_text(config)
```

**Then upload and run:**
```sql
PUT file:///tmp/eval_config.yaml @DB.SCHEMA.eval_config_stage AUTO_COMPRESS=FALSE OVERWRITE=TRUE;

CALL EXECUTE_AI_EVALUATION(
  'START',
  OBJECT_CONSTRUCT('run_name', 'agent_eval_20260401'),
  '@DB.SCHEMA.eval_config_stage/eval_config.yaml'
);
```

#### Step 4.2c: Save Self-Service Config (Runner Config)

**ALWAYS generate this file.** This is the config that `run_eval.py` reads to run evaluations without the skill.

**File location:** `agent-evaluation/configs/<agent_name>.yaml`

```yaml
agent:
  name: "<AGENT_NAME>"
  database: "<DATABASE>"
  schema: "<SCHEMA>"

dataset:
  questions: "datasets/<agent_name>_eval.yaml"
  snowflake_table: "<DATABASE>.<SCHEMA>.<AGENT_NAME>_EVAL_DATA"

snowflake:
  stage: "<DATABASE>.<SCHEMA>.eval_config_stage"
  file_format: "<DATABASE>.<SCHEMA>.yaml_file_format"
  warehouse: "<WAREHOUSE>"

evaluation:
  label: "<AGENT_NAME> evaluation"
  description: "<description of what is being evaluated>"

metrics:
  - "answer_correctness"
  - "logical_consistency"
  # Add boundary_enforcement if out_of_scope/negative questions exist:
  # - name: "boundary_enforcement"
  #   score_ranges: ...
  #   prompt: ...
```

**Rules:**
- `dataset.questions` must point to the YAML questions file from Step 3.5c
- `snowflake_table`, `stage`, `file_format` must use fully qualified names
- Include the same metrics the user selected in Step 2
- If `boundary_enforcement` was selected, include the full custom metric definition (from Step 4.2)

**Tell the user:** "I've saved the runner config to `configs/<agent>.yaml`. To re-run later: `uv run python scripts/run_eval.py configs/<agent>.yaml --connection <conn>`"

#### Step 4.3: Upload Config to Stage

**Option 1 — COPY INTO (recommended, works from any SQL client):**
```sql
COPY INTO @<DATABASE>.<SCHEMA>.eval_config_stage/agent_eval_config.yaml
FROM (
  SELECT '<paste YAML content here>'
)
FILE_FORMAT = (TYPE = 'CSV' FIELD_DELIMITER = NONE RECORD_DELIMITER = NONE COMPRESSION = NONE)
SINGLE = TRUE
OVERWRITE = TRUE;
```

**⚠️ CRITICAL:** Use `RECORD_DELIMITER = NONE` — using `'\n'` adds backslash escaping that corrupts the YAML.

**Option 2 — PUT (requires Python connector or SnowSQL, not available in Snowsight):**
```sql
PUT file:///path/to/agent_eval_config.yaml @<DATABASE>.<SCHEMA>.eval_config_stage
  AUTO_COMPRESS=FALSE
  OVERWRITE=TRUE;
```

**Option 3 — From Snowflake Workspace:**
```sql
COPY FILES INTO @<DATABASE>.<SCHEMA>.eval_config_stage
  FROM 'snow://workspace/USER$.PUBLIC.DEFAULT$/versions/live'
  FILES=('agent_eval_config.yaml');
```

**Verify upload:**
```sql
LIST @<DATABASE>.<SCHEMA>.eval_config_stage;
SELECT $1 FROM @<DATABASE>.<SCHEMA>.eval_config_stage/agent_eval_config.yaml
  (FILE_FORMAT => '<DATABASE>.<SCHEMA>.yaml_file_format');
```

#### Step 4.4: Start the Evaluation

**⚠️ CRITICAL: Set database/schema context first.** `EXECUTE_AI_EVALUATION` resolves object names against the session context, not the YAML. Without this, the agent name may resolve to the wrong database.

```sql
USE DATABASE <DATABASE>;
USE SCHEMA <SCHEMA>;

CALL EXECUTE_AI_EVALUATION(
  'START',
  OBJECT_CONSTRUCT('run_name', '<AGENT_NAME>_eval_<YYYYMMDD_HHMMSS>'),
  '@<DATABASE>.<SCHEMA>.eval_config_stage/agent_eval_config.yaml'
);
```

**Check status:**
```sql
CALL EXECUTE_AI_EVALUATION(
  'STATUS',
  OBJECT_CONSTRUCT('run_name', '<AGENT_NAME>_eval_<YYYYMMDD_HHMMSS>'),
  '@<DATABASE>.<SCHEMA>.eval_config_stage/agent_eval_config.yaml'
);
```

**Tip:** You can wrap `EXECUTE_AI_EVALUATION` in a Task to schedule recurring evaluations or status polling.

---

### Step 5: View Results

**Generate Snowsight link:**

```sql
SELECT LOWER(CURRENT_ORGANIZATION_NAME()), LOWER(CURRENT_ACCOUNT_NAME());
```

URL format:
```
https://app.snowflake.com/<org>/<account>/#/agents/database/<DATABASE>/schema/<SCHEMA>/agent/<AGENT_NAME>/evaluations/<RUN_NAME>/records
```

**⚠️ CRITICAL: URL Format**
- Snowsight URLs: keep underscores in account name (e.g., `sfdevrel_enterprise`)
- REST API URLs: replace underscores with hyphens

Open directly:
```bash
open "https://app.snowflake.com/<org>/<account>/#/agents/database/<DATABASE>/schema/<SCHEMA>/agent/<AGENT_NAME>/evaluations/<RUN_NAME>/records"
```

#### Step 5.1: Query Results via SQL

**Get full evaluation data:**
```sql
SELECT * FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(
  '<DATABASE>',
  '<SCHEMA>',
  '<AGENT_NAME>',
  'CORTEX AGENT',
  '<RUN_NAME>'
));
```

**Key columns returned:**

| Column | Description |
|--------|-------------|
| `RECORD_ID` | Unique ID per evaluation record |
| `INPUT` | The query string |
| `OUTPUT` | Agent's response |
| `GROUND_TRUTH` | Ground truth provided |
| `METRIC_NAME` | Name of the metric |
| `EVAL_AGG_SCORE` | Score for this record |
| `METRIC_TYPE` | `system` or `custom` |
| `METRIC_CALLS` | Array with criteria, explanation, and metadata |
| `ERROR` | Any errors during execution |

**Get per-question scores:**
```sql
SELECT
    INPUT,
    OUTPUT,
    METRIC_NAME,
    EVAL_AGG_SCORE,
    METRIC_CALLS[0]:explanation::STRING AS explanation
FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(
    '<DATABASE>', '<SCHEMA>', '<AGENT_NAME>', 'CORTEX AGENT', '<RUN_NAME>'
))
ORDER BY EVAL_AGG_SCORE ASC;
```

**Get trace for a single record:**
```sql
SELECT * FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_RECORD_TRACE(
  '<DATABASE>',
  '<SCHEMA>',
  '<AGENT_NAME>',
  'CORTEX AGENT',
  '<RECORD_ID>'
));
```

**Get errors and warnings for a run:**
```sql
SELECT * FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_OBSERVABILITY_LOGS(
  '<DATABASE>',
  '<SCHEMA>',
  '<AGENT_NAME>',
  'CORTEX AGENT')
)
WHERE TRUE
  AND (record:"severity_text" = 'ERROR' OR record:"severity_text" = 'WARN')
  AND record_attributes:"snow.ai.observability.run.name" = '<RUN_NAME>';
```

**Average scores summary:**
```sql
SELECT
    METRIC_NAME,
    AVG(EVAL_AGG_SCORE) AS avg_score,
    COUNT(*) AS record_count,
    SUM(CASE WHEN EVAL_AGG_SCORE >= 0.8 THEN 1 ELSE 0 END) AS high_accuracy_count,
    SUM(CASE WHEN EVAL_AGG_SCORE < 0.3 THEN 1 ELSE 0 END) AS low_accuracy_count
FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(
    '<DATABASE>', '<SCHEMA>', '<AGENT_NAME>', 'CORTEX AGENT', '<RUN_NAME>'
))
GROUP BY METRIC_NAME;
```

**⚠️ STOP**: Review results with user. Discuss findings and next steps.

---

## Known Limitations

### Prefer ALTER AGENT Over CREATE OR REPLACE AGENT

`ALTER AGENT <name> MODIFY LIVE VERSION SET SPECIFICATION = $$ ... $$` updates the agent spec in-place, preserving evaluation history, Snowflake Intelligence bindings, and other metadata. `CREATE OR REPLACE AGENT` deletes the agent and creates a new one, **breaking the link to all previous evaluation runs**.

**Best practices:**
- Use `ALTER AGENT ... MODIFY LIVE VERSION SET SPECIFICATION` for spec updates
- Use `CREATE AGENT IF NOT EXISTS` only for first-time creation
- Only use `CREATE OR REPLACE AGENT` when you explicitly want a clean slate
- Note: ALTER completely replaces the spec — omitted fields are removed

### Ground Truth Staleness

Input queries that reference relative time periods (this week, this month) produce drift. Always use absolute date ranges in evaluation questions.

### Evaluation Throughput

Long-running evaluations may experience timeouts. Split large datasets by tool invocation pattern, or break custom metric prompts into smaller focused prompts.

---

## Troubleshooting

### Agent Refuses to Use Tools (Low Scores, No Errors)

Check `DESCRIBE AGENT` for guardrails. Questions must match the agent's persona. Use the `sample_questions` from agent spec as a guide.

### Output Column Must Be VARIANT

```sql
-- Wrong - returns OBJECT not VARIANT
OBJECT_CONSTRUCT('ground_truth_output', 'answer')

-- Correct - returns VARIANT
PARSE_JSON('{"ground_truth_output": "answer"}')
TO_VARIANT(OBJECT_CONSTRUCT('ground_truth_output', 'answer'))
```

### Dataset Name Must Be Unique Per Schema

Dataset names must be unique among schema-level objects. Use a timestamp suffix: `<AGENT_NAME>_EVAL_DS_<YYYYMMDD>`.

### YAML Indentation Errors

The `run_params` and `source_metadata` keys must be indented under `evaluation`, not at the top level. The `metrics` key is top-level.

```yaml
evaluation:            # top-level
  agent_params:        # under evaluation
    agent_name: "DB.SCHEMA.AGENT"   # MUST be fully qualified
  run_params:          # under evaluation
    label: "..."
  source_metadata:     # under evaluation
    type: "dataset"                  # MUST be lowercase
    dataset_name: "DB.SCHEMA.DS"     # MUST be fully qualified

metrics:               # top-level (NOT under evaluation)
  - "answer_correctness"
```

### Config File Format

The stage file format must have `FIELD_DELIMITER = NONE` and `ESCAPE_UNENCLOSED_FIELD = NONE`. Standard CSV file format will corrupt the YAML. Always use the yaml_file_format created in Step 4.1.

### Querying Errors From a Run

Use `GET_AI_OBSERVABILITY_LOGS` (not `GET_AI_EVALUATION_DATA`) for warning/error details:

```sql
SELECT * FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_OBSERVABILITY_LOGS(
    '<DATABASE>', '<SCHEMA>', '<AGENT_NAME>', 'CORTEX AGENT')
)
WHERE record_attributes:"snow.ai.observability.run.name" = '<RUN_NAME>'
AND record:"severity_text" IN ('ERROR', 'WARN');
```

### Error: "Invalid source_metadata type: Unknown type: DATASET"

The `source_metadata.type` field is case-sensitive. Use lowercase `"dataset"`:
```yaml
# ❌ Wrong
source_metadata:
  type: "DATASET"

# ✅ Correct
source_metadata:
  type: "dataset"
```

### Error: "Unrecognized field: dataset_version"

The `dataset_version` field is not supported in the GA API. Remove it entirely from your YAML:
```yaml
# ❌ Wrong
source_metadata:
  type: "dataset"
  dataset_name: "MY_DS"
  dataset_version: "1"

# ✅ Correct
source_metadata:
  type: "dataset"
  dataset_name: "DB.SCHEMA.MY_DS"
```

### Error: "Object name AGENT format should be 'database.schema.object'"

The `agent_name` in the YAML config must be fully qualified with database and schema:
```yaml
# ❌ Wrong
agent_params:
  agent_name: "RESORT_EXECUTIVE"

# ✅ Correct
agent_params:
  agent_name: "SADM_SKI_RESORT_DB.AGENTS.RESORT_EXECUTIVE"
```

### Error: "Cortex Agent 'WRONG_DB.WRONG_SCHEMA.AGENT' does not exist"

`EXECUTE_AI_EVALUATION` resolves agent names against the session context. Always set the correct database/schema before calling:
```sql
USE DATABASE <AGENT_DATABASE>;
USE SCHEMA <AGENT_SCHEMA>;
CALL EXECUTE_AI_EVALUATION(...);
```

### COPY INTO Stage Produces Corrupted YAML (Backslash at End of Lines)

When using `COPY INTO @stage` to upload YAML, you MUST use `RECORD_DELIMITER = NONE`:
```sql
-- ❌ Wrong — adds backslash escaping
COPY INTO @stage/file.yaml FROM (SELECT '...')
FILE_FORMAT = (TYPE = 'CSV' FIELD_DELIMITER = NONE COMPRESSION = NONE) SINGLE = TRUE;

-- ✅ Correct — preserves YAML formatting
COPY INTO @stage/file.yaml FROM (SELECT '...')
FILE_FORMAT = (TYPE = 'CSV' FIELD_DELIMITER = NONE RECORD_DELIMITER = NONE COMPRESSION = NONE) SINGLE = TRUE;
```

### Hybrid Dataset Approach

**Approach A (YAML `dataset` section) is RECOMMENDED for `answer_correctness`.** When using Approach B (pre-create via `SYSTEM$CREATE_EVALUATION_DATASET`), the ground truth column mapping may silently fail, resulting in `"Missing ground truth: ground_truth_output not found or empty"` and 0% scores. Approach A includes the column mapping inline and correctly links the ground truth.

If you must use Approach B, verify ground truth is linked by running a quick `logical_consistency`-only test first, then checking that `GROUND_TRUTH` is populated in `GET_AI_EVALUATION_DATA` results.

---

## Self-Service Framework (No Skill Required)

Users can run evaluations without this skill using the config-driven framework.

### How It Works

Two files per agent:

1. **Config YAML** (`configs/<agent>.yaml`) — agent, Snowflake targets, metrics, thresholds
2. **Questions YAML** (`datasets/<agent>_eval.yaml`) — questions, ground truth, metadata

The runner script (`scripts/run_eval.py`) reads both, loads questions into Snowflake, generates the Snowflake evaluation YAML, uploads it, starts the run, polls until complete, checks thresholds, fetches errors, and saves JSON results.

### Questions File Format (YAML — recommended)

```yaml
questions:
  - question: "What was total revenue for the most recent complete season?"
    expected_tools: ["RevenueAnalytics"]
    category: revenue
    tags: [quarterly, total, dynamic]
    test_type: in_scope
    validation_query: |
      SELECT SKI_SEASON AS season, ROUND(SUM(REVENUE), 0) AS total_revenue
      FROM DB.SCHEMA.SALES JOIN DB.SCHEMA.DIM_DATE USING (DATE_KEY)
      WHERE SKI_SEASON = (SELECT MAX(SKI_SEASON) FROM DB.SCHEMA.DIM_DATE WHERE FULL_DATE < CURRENT_DATE())
      GROUP BY SKI_SEASON
    answer_template: "Total revenue for {season} was ${total_revenue:,.0f}."

  - question: "What is the stock price?"
    expected_tools: []
    category: boundary
    tags: [out_of_scope]
    test_type: out_of_scope
    ground_truth: "Agent should decline — stock data is outside its domain."
```

**Fields:** `question` (required), `ground_truth` (required if no `validation_query`), `expected_tools`, `category`, `tags`, `test_type`, `validation_query`, `answer_template`

CSV files are also supported as a simpler alternative.

### Config File Format

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
  answer_correctness: 0.70
  logical_consistency: 0.80
  # boundary_enforcement: 7.0

metrics:
  - "answer_correctness"
  - "logical_consistency"
```

The `thresholds` section defines pass/fail gates per metric. When thresholds are configured, the runner exits with code 1 on failure (CI-friendly).

### Running

```bash
cd agent-evaluation && uv sync

# Preview
uv run python scripts/run_eval.py configs/my_agent.yaml --dry-run

# Run (polls until complete by default)
uv run python scripts/run_eval.py configs/my_agent.yaml --connection MY_CONNECTION

# Start without waiting
uv run python scripts/run_eval.py configs/my_agent.yaml --connection MY_CONNECTION --no-wait

# Custom poll interval (seconds)
uv run python scripts/run_eval.py configs/my_agent.yaml --connection MY_CONNECTION --poll-interval 15

# Use environment config (overrides agent database/schema/warehouse from agents/environments/<env>.yml)
uv run python scripts/run_eval.py configs/my_agent.yaml --connection MY_CONNECTION --env dev

# Filter by category or tag
uv run python scripts/run_eval.py configs/my_agent.yaml --category revenue --connection MY_CONNECTION

# Check status / view results
uv run python scripts/run_eval.py configs/my_agent.yaml --status --connection MY_CONNECTION
uv run python scripts/run_eval.py configs/my_agent.yaml --results --connection MY_CONNECTION

# Resolve dynamic ground truth only (no eval run)
uv run python scripts/run_eval.py configs/my_agent.yaml --resolve-only --connection MY_CONNECTION
```

### CLI Flags

| Flag | Description |
|------|-------------|
| `--dry-run` | Show plan without executing |
| `--no-wait` | Start evaluation and exit without polling |
| `--poll-interval N` | Seconds between status polls (default: 30) |
| `--env {dev,staging,prod}` | Load environment config from `agents/environments/<env>.yml` |
| `--connection NAME` | Snowflake connection name (from connections.toml, with tilde expansion) |
| `--status` | Check status of last run |
| `--results` | Show results of last run |
| `--resolve-only` | Resolve dynamic ground truth and print (no eval) |
| `--category NAME` | Filter questions by category |
| `--tag NAME` | Filter questions by tag (repeatable) |
| `--run-name NAME` | Override run name |

### What Happens When You Run

1. Loads config + questions YAML
2. Resolves dynamic ground truth (validation_query + answer_template)
3. Loads questions into Snowflake table
4. Creates stage and uploads Snowflake evaluation YAML
5. Starts EXECUTE_AI_EVALUATION
6. Polls STATUS every N seconds until COMPLETED/FAILED/TIMEOUT
7. Fetches results via GET_AI_EVALUATION_DATA
8. Fetches errors/warnings via GET_AI_OBSERVABILITY_LOGS
9. Checks thresholds (if configured) — exits 0 (pass) or 1 (fail)
10. Saves full JSON results to `results/<agent>_<timestamp>.json`
11. Prints Snowsight URL for visual review

### Environment Configs

The `--env` flag loads `agents/environments/<env>.yml` and overrides agent database/schema/warehouse/role. This lets the same config YAML target dev, staging, or prod:

```yaml
# agents/environments/dev.yml
environment: dev
snowflake:
  role: ACCOUNTADMIN
deployment:
  database: SADM_SKI_RESORT_DB
  schema: AGENTS
  warehouse: COMPUTE_WH
settings:
  version_suffix: _DEV
```

### JSON Results Export

Every run saves a full JSON file to `results/` with:
- `summary`: per-metric averages
- `thresholds`: configured thresholds
- `passed`: overall pass/fail boolean
- `results`: raw per-record evaluation data

Useful for historical comparison, CI reporting, and trend analysis.

### Connection Tilde Expansion

The `--connection` flag reads `~/.snowflake/connections.toml` and expands `~` in `private_key_path` (which `snowflake.connector.connect(connection_name=)` does not do). This means `--connection myconnection` works even when the TOML has `private_key_path = "~/.snowflake/keys/key.p8"`.

### When Using This Skill

When assisting a user with an evaluation, the skill workflow (Steps 1-5 above) **MUST produce the self-service artifacts**:

- **Step 3.5c**: Save questions YAML to `datasets/<agent>_eval.yaml` — this is the editable source of truth
- **Step 4.2c**: Save runner config to `configs/<agent>.yaml` — this drives `run_eval.py`
- **After Step 5**: Tell the user they can re-run evaluations without the skill:
  ```
  To re-run this evaluation later:
    1. Edit datasets/<agent>_eval.yaml (add/change questions)
    2. Add thresholds to configs/<agent>.yaml if desired
    3. Run: uv run python scripts/run_eval.py configs/<agent>.yaml --connection <conn>
    4. Results saved to results/<agent>_<timestamp>.json
  ```

---

## Stopping Points

- ✋ Step 1: Agent identified and tools analyzed
- ✋ Step 2: Metrics selected by user
- ✋ Step 3: Dataset reviewed and approved
- ✋ Step 4: Config uploaded and evaluation started
- ✋ Step 5: Results presented to user

## Output

- **Questions file:** `agent-evaluation/datasets/<agent_name>_eval.yaml`
- **Config file:** `agent-evaluation/configs/<agent_name>.yaml`
- **Local review file:** `agent-evaluation/datasets/<agent_name>_eval_<YYYYMMDD>.md`
- **JSON results:** `agent-evaluation/results/<agent_name>_<YYYYMMDD_HHMMSS>.json`
- **Evaluation data table:** `<DATABASE>.<SCHEMA>.<AGENT_NAME>_EVAL_DATA`
- **Stage with config:** `<DATABASE>.<SCHEMA>.eval_config_stage`
- **Registered dataset:** `<DATABASE>.<SCHEMA>.<AGENT_NAME>_EVAL_DS`
- **Evaluation run:** `<AGENT_NAME>_eval_<YYYYMMDD_HHMMSS>`
- **Results:** Snowsight Evaluations UI or `GET_AI_EVALUATION_DATA`

## File Structure

```
agent-evaluation/
  SKILL.md                              # This file — workflow instructions
  README.md                             # Self-service documentation
  pyproject.toml                        # Python dependencies (uv sync)
  scripts/
    run_eval.py                         # End-to-end runner (config → Snowflake → eval → poll → results)
    load_eval_dataset.py                # CSV → Snowflake loader (standalone)
    convert_eval_dataset.py             # Convert existing tables to eval format
    invoke_agent.py                     # Invoke agent via REST API (debugging)
  configs/                              # One config per agent
    <agent_name>.yaml                   # Agent + dataset + metrics + thresholds + Snowflake targets
    <agent_name>_eval_config.yaml       # Snowflake-format template with {PLACEHOLDERS}
  datasets/                             # One questions file per agent
    <agent_name>_eval.yaml              # Questions + ground truth + metadata (YAML)
    <agent_name>_eval.csv               # Questions + ground truth (CSV alternative)
    <agent_name>_eval_<YYYYMMDD>.md     # Run results (reference)
  results/                              # JSON results from evaluation runs
    <agent_name>_<YYYYMMDD_HHMMSS>.json # Full results + summary + thresholds + pass/fail
  references/
    dynamic-ground-truth.md             # Patterns for validation_query + answer_template
```
