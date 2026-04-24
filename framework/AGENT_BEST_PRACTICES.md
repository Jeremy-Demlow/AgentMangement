# Agent Best Practices

Condensed, project-specific version of the
[Cortex Agent Best Practices](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents)
guide. Use this as the quick reference; the full upstream doc is the
source of truth for concepts.

## The priority order

1. **Scoping** — fewer tools, sharper focus
2. **Tool descriptions** — the single biggest quality lever
3. **Semantic view design** — VQRs, clear metric names, proper joins
4. **Orchestration instructions** — tool selection logic, workflows
5. **Response instructions** — formatting and tone

Do NOT start with prompt engineering. Fix data and tool descriptions first.

---

## 1. Scoping

- Ask business stakeholders for their **top 20 questions**. That is your
  scope.
- Build narrow, specialized agents. Rule of thumb: **5-10 tools per agent**.
  This repo's `resort_executive` is already at 11 — we tolerate that because
  it covers an intentionally cross-functional role. Most agents should be
  smaller.
- Work backward from questions to SVs to tools.

## 2. Tool descriptions

The single biggest lever. Every tool description follows the exact format
in [TOOL_DESCRIPTION_TEMPLATE.md](TOOL_DESCRIPTION_TEMPLATE.md):

```
PURPOSE: <one line>
DATA: <coverage + refresh>
KEY METRICS: <list>
KEY DIMENSIONS: <list>
USE FOR: <bulleted scenarios>
NOT FOR: <bounded scenarios with alternative tool>
CROSS-REFERENCE WITH: <related tools for multi-tool questions>
```

### The three things good descriptions give you

1. **Tool selection accuracy** — agent picks the right tool.
2. **Parameter correctness** — agent supplies valid filters/values.
3. **Error prevention** — agent avoids misusing a tool for a scenario it
   was not designed for.

### Common mistakes to avoid

- **Vague names**: "DataTool", "Tool1". Use `CustomerConsumptionAnalytics`
  style.
- **Missing "NOT FOR"**: the agent will try to use a tool for anything
  remotely related unless you spell out the boundary.
- **Listing metrics as a paragraph**: the template's bullet structure helps
  the agent pattern-match.
- **Overlapping tools without disambiguation**: if `CustomerAnalytics` and
  `PassholderAnalytics` both mention "customers", you MUST add a
  DISAMBIGUATION line to each.

## 3. Semantic view design

- Every fact table should join to `DIM_DATE` via `DATE_KEY`. If a fact
  doesn't have a DATE_KEY column, add it in dbt (see
  `fact_incidents.sql` for the backfill pattern).
- Expose relationship FK columns as dimensions in both tables of the
  relationship. The Cortex Analyst eval API requires this — see the
  `invalid identifier 'DIM_DATE_KEY'` incident documented in
  [../ENVIRONMENT_PARITY.md](../ENVIRONMENT_PARITY.md).
- Add VQRs for common questions. See
  [VQR_AUTHORING_GUIDE.md](VQR_AUTHORING_GUIDE.md).
- Put data-level instructions (how to query, when to filter) in the SV's
  `module_custom_instructions.sql_generation` — NOT in the agent's
  orchestration prompt. Keep agent instructions about orchestration;
  keep SV instructions about SQL generation.

## 4. Orchestration instructions

Must cover:

- **Agent identity and scope** (one paragraph).
- **Tool routing** — which tool for which domain.
- **Disambiguation rules** for overlapping tools.
- **Time anchor** — resolve "this season", "last season", "today"
  dynamically. Do NOT hardcode season strings like "2024-25".
- **Comparison pattern** — how to handle "compare X vs Y".
- **Drill-down pattern** — how to handle "why".
- **Cross-domain pattern** — how to handle multi-tool questions.
- **Empty-result handling** — confirm with the user, don't silently broaden.
- **Business rules** — project-specific logic.
- **Boundaries** — what the agent is NOT allowed to do.

See [agents/specs/resort_executive.yml](../agents/specs/resort_executive.yml)
for a worked example covering all of the above.

## 5. Response instructions

Must cover:

- **Response structure** — a named pattern (e.g. headline / metrics /
  insight / caveats) so output is consistent.
- **Formatting rules** — currency, percentages, date format, units.
- **Tone** — who the user is, what voice fits. Often: "factual, no
  speculation".

## 6. Testing and iteration

- Every agent has an `agent-evaluation/datasets/<agent>_eval.yaml` with at
  least 10 questions, a validation query, and an answer template.
- Every agent has a `v<N>-<change>/` folder under
  `agent_optimization/<agent>/versions/` with config snapshot and eval
  results.
- Eval thresholds (DEV): answer_correctness >= 0.60, logical_consistency
  >= 0.60. PROD: 0.80 on both.
- Do not ship a change without a measured eval delta.

## 7. Performance

- Slow agents are usually slow SVs. Run the generated SQL in Snowflake
  directly and look for missing clustering, large joins, or expensive
  aggregations.
- VQRs short-circuit the LLM path entirely for common questions and are
  both faster and more accurate.
- Focused agents (fewer tools) are faster than monolithic ones.

## 8. Common pitfalls

| Pitfall | Symptom | Fix |
|---|---|---|
| Hardcoded "current season" string | Agent answers wrong season after April | Resolve via `DIM_DATE` where `full_date = CURRENT_DATE()` |
| Tool without `NOT FOR` | Agent picks the wrong tool for ambiguous questions | Add `NOT FOR` + alternative tool |
| Metric defined in agent prompt | Inconsistent across agents using same SV | Move metric to SV `metrics:` block |
| Silent fallback on empty results | Agent returns wrong/stale data with no warning | Require confirmation in orchestration |
| Manually-deployed SV | eval evaluates different SV than dbt model | Use `dbt run` only; `detect_sv_drift` catches this |
