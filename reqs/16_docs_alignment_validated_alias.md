# REQ-016: Documentation Alignment to Validated-Alias Model

**Status:** Done (this PR)
**Owner:** Jeremy Demlow
**Created:** 2026-05-19

## Problem

`AGENTS.md` was corrected previously, but the rest of the contributor-facing documentation still described a 3-environment model (DEV/QA/PROD) and referenced workflows that no longer exist (`promote-qa.yml`, `promote-prod.yml`). This created a high-risk drift: anyone following `README.md` or `CONTRIBUTING.md` would attempt promotions through removed workflows.

## Acceptance Criteria

- `README.md` describes two environments (DEV, PROD) and PROD's `validated` and `production` aliases.
- `README.md` workflow inventory and architecture diagrams reflect the actual workflows in `.github/workflows/`.
- `CONTRIBUTING.md` lifecycle (sections "Merge to dev", "Merge dev to main", "Promote validated -> production") matches the actual workflow names and approval gates.
- `tests/test_cases.md` no longer references removed workflows; replaces those rows with current-flow tests.
- `docs/operations/PIPELINE_HEALTH.md` reflects DCM triggering on both `dev` and `main`.

## Out of Scope

- `AgentMangementThread.md` is gitignored (working scratchpad). Treat as effectively archival; a banner is unnecessary because it does not ship.
- Updating every diagram image under `docs/diagrams/` (they are illustrative, not authoritative).

## Verification

```bash
grep -nE "\bQA\b|promote-qa|promote-prod|qa\.env|AM_SKI_RESORT_QA|RESORT_EXECUTIVE_QA" \
    README.md CONTRIBUTING.md tests/test_cases.md docs/operations/PIPELINE_HEALTH.md
```

Expected: only explanatory matches (e.g., "There is no QA environment.") survive. No workflow references to removed files.

## References

- `README.md`
- `CONTRIBUTING.md`
- `tests/test_cases.md`
- `docs/operations/PIPELINE_HEALTH.md`
- `AgentMangementThread.md`
