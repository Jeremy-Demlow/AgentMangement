# Agent Optimization Checklist

Use this as a step-by-step checklist when creating a new agent or
improving an existing one. Every checkbox must be checked before merge.

---

## A. Scope (new agents only)

- [ ] Business stakeholder supplied top 15-20 questions the agent must answer
- [ ] Each question maps to 1-3 existing or planned semantic views
- [ ] Total tool count is between 4 and 10 (hard cap: 11)
- [ ] Every question can be answered by the tool set; no gaps
- [ ] Agent name, scope, and primary users are written down in
      `agents/specs/<agent>.yml -> description`

## B. Tool descriptions

For every tool in `agents/specs/<agent>.yml`:

- [ ] Follows the [TOOL_DESCRIPTION_TEMPLATE.md](TOOL_DESCRIPTION_TEMPLATE.md) format exactly
- [ ] `PURPOSE:` section present — one clear sentence
- [ ] `DATA:` section present — coverage + refresh frequency
- [ ] `KEY METRICS:` section lists all frequently-used metrics
- [ ] `KEY DIMENSIONS:` section lists all frequently-used dimensions
- [ ] `USE FOR:` bullet list with at least 2 scenarios
- [ ] `NOT FOR:` bullet list naming the alternative tool for each bounded case
- [ ] `CROSS-REFERENCE WITH:` mentions the 1-3 most common multi-tool companions
- [ ] `DISAMBIGUATION:` added if another tool has overlapping domain
- [ ] Tool name includes domain AND function (no `Analytics` alone)
- [ ] CI test `tests/test_templates.py::test_tool_description_format` passes

## C. Semantic views backing the agent

For each SV the agent uses:

- [ ] dbt model is the source of truth (not `semantic-views/definitions/`)
- [ ] Every fact table joins to `DIM_DATE` via `DATE_KEY`
- [ ] Relationship FK columns are exposed as dimensions in both tables
- [ ] SV has at least 5 VQRs covering the most common questions
- [ ] SV has `module_custom_instructions.sql_generation` with SV-specific
      SQL generation rules (not in the agent prompt)
- [ ] `detect_sv_drift --env <env>` reports no drift

## D. Orchestration instructions

- [ ] Agent identity in one paragraph
- [ ] Tool routing rules (one line per tool)
- [ ] DISAMBIGUATION RULES for any overlapping tools
- [ ] TIME ANCHOR section — resolves "this season" / "last season"
      dynamically via DIM_DATE, NOT hardcoded strings
- [ ] COMPARISON PATTERN section
- [ ] DRILL-DOWN PATTERN section
- [ ] CROSS-DOMAIN PATTERN section
- [ ] EMPTY-RESULT HANDLING section
- [ ] BUSINESS RULES section (project-specific)
- [ ] BOUNDARIES section — what the agent will NOT do

## E. Response instructions

- [ ] RESPONSE STRUCTURE — named pattern so output is consistent
- [ ] FORMATTING rules — currency, percentages, dates, units
- [ ] TONE — one-paragraph voice guideline
- [ ] No speculation clause — "do not claim causation without data"

## F. Evaluation

- [ ] `agent-evaluation/datasets/<agent>_eval.yaml` has 10+ in_scope questions
- [ ] Every question has a `validation_query` and `answer_template`
- [ ] Multi-row questions use the multi-row answer template pattern
- [ ] At least one out_of_scope question to test boundary behavior
- [ ] Baseline eval captured in
      `agent_optimization/<agent>/versions/v<N>-baseline/`
- [ ] Post-change eval captured in
      `agent_optimization/<agent>/versions/v<N+1>-<change>/`
- [ ] Delta recorded in `framework/MEASUREMENT_RESULTS.md`

## G. Deployment

- [ ] PR targets `main`
- [ ] All PR gates green (lint, validate-specs, dbt-quality-gate x3,
      validate-snowflake, sv-eval, agent-eval)
- [ ] QA auto-deploy green after merge
- [ ] PROD promote run when ready; PROD eval thresholds (0.80 / 0.80) met

---

## Quick sanity-check before opening PR

Answer yes/no:

1. Does every tool description contain `PURPOSE:`, `USE FOR:`, `NOT FOR:`,
   `CROSS-REFERENCE WITH:`? **If no, go back to B.**
2. Is any season string hardcoded in the spec or VQRs?
   `grep -r '2024-2025\|2023-2024' agents/specs/ semantic-views/`
   **If yes, fix it — use dynamic resolution.**
3. Does `dbt compile --target prod` succeed? **If no, fix before PR.**
4. Did you run the eval after your changes? **If no, do that first.**
5. Did you update `MEASUREMENT_RESULTS.md` with the delta?
   **If no, do that before PR.**

If all 5 are yes, you're ready to ship.
