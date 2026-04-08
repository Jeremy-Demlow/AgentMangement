# Model: Evaluation Dataset

## Purpose
Defines the structure of golden question sets used to evaluate Cortex Agents, including the YAML file format stored in `eval/datasets/`, the Snowflake table schema used by `EXECUTE_AI_EVALUATION`, and the dynamic ground truth mechanism.

## Source(s)
| Source Object | Type | Grain | Notes |
|--------------|------|-------|-------|
| eval/datasets/*.yml | YAML file | One file per agent | Golden questions with ground truth |
| SADM_SKI_RESORT_DB.AGENTS.*_EVAL_DATA | Table | One row per question | Created by run_eval.py |

## Schema — YAML File (eval/datasets/)

| Field | Data Type | Nullable | Description | Business Logic |
|-------|-----------|----------|-------------|----------------|
| questions[].question | STRING | No | Natural language question to ask the agent | |
| questions[].ground_truth | STRING | Yes | Static expected answer | Used when no validation_query provided |
| questions[].validation_query | STRING | Yes | SQL query executed at eval time to generate fresh ground truth | Runs against live data for dynamic answers |
| questions[].answer_template | STRING | Yes | Python format string that formats query results into NL ground truth | Uses `str.format_map()` with query result columns |
| questions[].expected_tools | LIST[STRING] | Yes | Which agent tools should be invoked | For future tool_selection_accuracy metric |
| questions[].category | STRING | Yes | Question domain | revenue, operations, staffing, weather, etc. |
| questions[].tags | LIST[STRING] | Yes | Fine-grained labels | aggregate, time-filter, top-n, comparison, etc. |
| questions[].test_type | STRING | Yes | Type of test | factual, analytical, cross_domain |

## Schema — Snowflake Table

| Column | Data Type | Nullable | Description | Business Logic |
|--------|-----------|----------|-------------|----------------|
| INPUT_QUERY | VARCHAR | No | The question text | Mapped to `query_text` in eval config |
| OUTPUT | VARIANT | No | Ground truth as JSON | `{"ground_truth_output": "answer text"}` via PARSE_JSON |

## Relationships
- Eval dataset -> Agent (evaluated by `EXECUTE_AI_EVALUATION`)
- Eval dataset -> Semantic views (questions test the SVs bound to the agent)
- validation_query -> SADM_SKI_RESORT_DB base tables (SQL runs against live data)

## Business Rules
- If `validation_query` is provided, it is executed at eval time and `answer_template` formats the result into ground_truth; this overrides any static `ground_truth` value
- Dynamic ground truth should use relative time references (e.g., "most recent complete season") not absolute dates
- The OUTPUT column must be VARIANT type with `PARSE_JSON('{"ground_truth_output": "..."}')`
- `source_metadata.type` in the eval config YAML must be lowercase `"dataset"` (not uppercase)
- `agent_name` in eval config must be fully qualified: `DATABASE.SCHEMA.AGENT_NAME`
- Stage YAML upload must use `COPY INTO` (not PUT) to avoid nested subdirectory issues
- `Decimal` types from Snowflake query results must be converted to float before formatting

## Notes
- resort_executive dataset: 15 questions across 11 tool categories
- ski_ops_assistant dataset: 8-10 questions across 4 tool categories (operations, staffing, weather, safety)
- Dynamic ground truth patterns documented in references/dynamic-ground-truth.md
- Built-in metrics: answer_correctness, logical_consistency
- Custom metrics: answer_relevance, faithfulness (LLM-judge YAML in eval/metrics/)
