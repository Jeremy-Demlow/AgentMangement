# Verified Query Representations (VQRs)

VQRs are hand-authored question/SQL pairs attached to a semantic view. They
serve two purposes:

1. **Grounding** — Cortex Analyst uses VQRs as few-shot examples when
   translating natural language to SQL.
2. **Regression evals** — `agent_management.run_sv_eval` runs each VQR through
   the SV's text-to-SQL API and compares the generated SQL against the
   verified SQL; regressions block PRs.

VQRs live in `semantic-views/verified_queries/<sv_name>.yaml`. They are
synced into dbt SV models by `agent_management.sync_vqrs_to_dbt` so the VQR
list travels with the SV definition through dbt's materialization.

## Anatomy of a VQR

```yaml
- question: "Which lift had the most scans last week?"
  sql: |
    SELECT * FROM SEMANTIC_VIEW(
      {{ env.semantic_schema }}.SEM_OPERATIONS
      DIMENSIONS LIFT_SCANS.DIM_LIFT.LIFT_NAME
      METRICS LIFT_SCANS.FACT_LIFT_SCANS.TOTAL_SCANS
      WHERE DIM_DATE.DATE_KEY BETWEEN …
      ORDER BY TOTAL_SCANS DESC
      LIMIT 1
    );
  tags: [lifts, ops]
  notes: "Baseline for the ops overview dashboard."
```

Minimum required fields: `question`, `sql`. Optional but strongly recommended:
`tags` (used by eval filters) and `notes`.

## When to add a VQR

Add one when:

- You add a new metric or dimension to the SV and want to anchor Analyst on
  its phrasing.
- Eval exposes a question pattern that Analyst routinely mis-translates.
- A stakeholder asks a recurring question; capture it verbatim.

Avoid VQRs for one-off exploratory questions — they cost runtime on every
eval.

## Guidelines

1. **Use rendered FQNs, not shortcuts.** The file is Jinja-rendered; write
   `{{ env.semantic_schema }}.SEM_REVENUE` so dev/prod get correct references.
2. **Mirror the production SQL shape.** Use `SEMANTIC_VIEW(...)` exactly as
   the SV exposes it. Dimensions go under DIMENSIONS, metrics under METRICS.
3. **Keep questions natural.** "Which lifts had the highest wait times in
   December?" beats "Top 5 LIFT_NAME by AVG_WAIT_SECONDS where MONTH = 12".
4. **Pair adds with tests.** Run `python -m agent_management.run_sv_eval
   --env dev --sv sem_operations` after adding.
5. **Don't hard-code seasons or years.** Use DIM_DATE filters driven by
   `CURRENT_DATE()` or a `season` dimension so VQRs stay valid year over year.

## Tagging conventions

| Tag | Used for |
|-----|----------|
| `smoke` | Baseline sanity checks run on every PR |
| `regression` | Known-flaky questions tracked specifically |
| one per subject area (e.g. `lifts`, `revenue`, `safety`) | Eval filters |

Keep tag vocabulary small; expand only when a new filter is genuinely useful.

## Related

- [docs/operations/AGENT_VERSIONING.md](../operations/AGENT_VERSIONING.md) — agent side of the flow
- [reqs/13_test_matrix.md](../../reqs/13_test_matrix.md) — eval matrix
