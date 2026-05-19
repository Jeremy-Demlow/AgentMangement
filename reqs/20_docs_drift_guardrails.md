# REQ-020: Documentation and Workflow Drift Guardrails

**Status:** Done (this PR)
**Owner:** Jeremy Demlow
**Created:** 2026-05-19

## Problem

The grooming work in REQ-016 and REQ-017 cleaned up stale references to removed workflows (`promote-qa.yml`, `promote-prod.yml`) and the dead QA environment. Without an automated guardrail, the same drift will return the next time someone documents a future-state plan inline. Doc drift is a slow leak, and the cost shows up as contributors following a flow that no longer exists.

## Acceptance Criteria

- A new test module `tests/test_docs_drift_guardrails.py` runs in the default suite (`uv run python -m pytest tests -q`).
- It fails when any active doc references a removed workflow name (`promote-qa.yml`, `promote-prod.yml`).
- It fails when an active doc references a workflow file that does not exist under `.github/workflows/`.
- It fails when `project.yml`'s `environments:` keys do not match the files under `environments/*.env.yml`.
- It fails when a workflow declares a GitHub `environment:` value that is not in the legal set (`DEV`, `PROD`, `production-promote`).
- Archival docs are excluded via an explicit `ARCHIVAL_DOCS` set so the scan stays honest without lying about what's current.

## Out of Scope

- Linting workflow YAML for syntax (handled by GitHub Actions itself).
- Validating that workflow `paths:` filters are correct. That's a future REQ if it becomes a recurring problem.
- Generating docs from code. Drift guardrails catch divergence; full doc generation is a bigger undertaking that would also lose human-written context.

## Verification

```bash
uv run python -m pytest tests/test_docs_drift_guardrails.py -v
```

Expected: 9 passed.

```bash
uv run python -m pytest tests -q
```

Expected: full suite green (175 with these additions).

## References

- `tests/test_docs_drift_guardrails.py`
- REQ-016 (docs alignment that this guardrail protects)
- REQ-017 (CI workflow contract that this guardrail protects)
- REG-007 (branch drift; this guardrail does not catch git drift but flags doc drift caused by it)
