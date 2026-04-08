# REQ-004: Evaluation Framework with Gate

## Summary
Automated agent evaluations using golden question sets, Snowflake's native `EXECUTE_AI_EVALUATION`, custom LLM-judge metrics (answer relevance, faithfulness), and derived classical metrics (F1, precision, recall) that gate CI/CD promotions on quality thresholds.

## Implementation Status

The core evaluation framework already exists at `agent-evaluation/`:

| Component | Status | Location |
|-----------|--------|----------|
| `run_eval.py` (775 lines) | EXISTS | `agent-evaluation/scripts/run_eval.py` |
| Dynamic ground truth | EXISTS | `validation_query` + `answer_template` in dataset YAML |
| Golden questions (Resort Executive, 15 Qs) | EXISTS | `agent-evaluation/datasets/resort_executive_eval.yaml` |
| Eval config (Resort Executive) | EXISTS | `agent-evaluation/configs/resort_executive.yaml` |
| Threshold checking + exit codes | EXISTS | Built into `run_eval.py` |
| JSON results export | EXISTS | `agent-evaluation/results/` |
| `compute_metrics.py` (F1/precision/recall) | TO BUILD | `scripts/compute_metrics.py` |
| Golden questions (Ski Ops Assistant) | TO BUILD | `agent-evaluation/datasets/ski_ops_assistant_eval.yaml` |
| Custom metric YAMLs (relevance, faithfulness) | TO BUILD | `agent-evaluation/metrics/` |
| Environment-aware eval configs | TO BUILD | Jinja2 placeholders for agent_name, database |
| `thresholds.yml` | TO BUILD | Per-environment threshold overrides |

## Business Context
Deploying agent changes without measuring their impact is flying blind. A semantic view column rename, a new instruction, or a model upgrade can silently degrade answer quality. The evaluation framework provides objective, repeatable quality measurement at every stage of the pipeline. By computing F1/precision/recall from per-question correctness scores and enforcing minimum thresholds, we turn agent quality into a hard CI/CD gate — not a hope.

## Acceptance Criteria
- [x] Golden question dataset exists for resort_executive (15 questions with dynamic ground truth)
- [ ] Golden question dataset exists for ski_ops_assistant (8-10 questions)
- [x] `run_eval.py` runs `EXECUTE_AI_EVALUATION` with golden questions and polls to completion
- [x] Dynamic ground truth supported via `validation_query` + `answer_template`
- [ ] Custom LLM-judge metrics (answer_relevance, faithfulness) defined as YAML and included in eval runs
- [ ] `compute_metrics.py` derives F1, precision, recall from per-question correctness scores
- [ ] `thresholds.yml` defines minimum scores per metric per environment
- [x] Eval results saved as JSON artifact for GitHub Actions upload
- [ ] Eval configs reference agents and datasets via environment-aware FQNs (Jinja2)

## User Stories
| Story ID | As a... | I want to... | So that... |
|----------|---------|-------------|------------|
| US-009   | QA engineer | golden question sets with known-correct answers | agent quality is measured objectively against ground truth |
| US-010   | QA engineer | F1, precision, and recall metrics | I can quantify agent accuracy beyond LLM-judge averages |
| US-011   | DevOps engineer | eval exit codes (0 = pass, 1 = fail) | CI/CD can automatically gate promotions on quality thresholds |
| US-012   | data analyst | custom metrics like relevance and faithfulness | I measure answer quality dimensions beyond just correctness |

## Dependencies
- REQ-001: Environment Configuration System (for FQN resolution in eval configs)
- REQ-003: Agent CI/CD Pipeline (agents must be deployed before they can be evaluated)

## Out of Scope
- Tool selection accuracy and tool execution accuracy metrics (not GA yet)
- Real-time monitoring or continuous evaluation (batch only)
- A/B testing between agent versions
- Snowsight dashboard for eval results (results are JSON artifacts and queryable via SQL)

## Notes
- **This requirement covers AGENT evaluations only.** Semantic view SQL correctness evaluations are covered by REQ-009.
- Agent eval uses `EXECUTE_AI_EVALUATION` + `GET_AI_EVALUATION_DATA` (object type: `'CORTEX AGENT'`)
- SV eval uses `GET_ANALYST_AI_EVALUATION_DATA` (object type: `'SEMANTIC VIEW'`) — see REQ-009
- In the CI/CD pipeline, SV eval runs AFTER SV deploy but BEFORE agent deploy; agent eval runs AFTER agent deploy
- Existing framework at `agent-evaluation/` — adapted from SnowflakeAgentDevelopmentManagement
- Latest eval results: 92.4% answer_correctness, 87.2% logical_consistency (Resort Executive, v3)
- `EXECUTE_AI_EVALUATION('START', object_construct, stage_path)` is the run mechanism (GA March 2026)
- `GET_AI_EVALUATION_DATA(db, schema, agent, 'CORTEX AGENT', run_name)` retrieves per-question results
- Built-in metrics: `answer_correctness`, `logical_consistency`
- Custom metrics use LLM-judge prompts with `{{input}}`, `{{output}}`, `{{ground_truth}}` placeholders
- F1 computation: score >= threshold -> TP, else -> FN; all golden questions expected answerable
- Stage YAML upload must use `COPY INTO` (not PUT) to avoid nested subdirectory issues
- `source_metadata.type` must be lowercase `"dataset"` (not uppercase)
- `agent_name` in eval YAML must be fully qualified: `DATABASE.SCHEMA.AGENT_NAME`
