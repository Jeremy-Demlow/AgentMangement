# REQ-017: CI Workflow Contract

**Status:** Done (this PR)
**Owner:** Jeremy Demlow
**Created:** 2026-05-19

## Problem

Two recurring sources of contributor confusion:

1. PRs that only change docs or workflows show no eval signal. Contributors interpret "no eval comment" as "evals broken." It is actually the `paths:` filter on `validate-pr.yml` correctly skipping work that has no semantic content to evaluate.
2. PROD validated deploy and the `validated -> production` promotion treat threshold failures as advisory. The deploy or alias flip still completes; threshold signal feeds the human promotion decision. This was implicit in the workflow code but never written down clearly.

`dcm-deploy.yml` also still carried a header comment claiming "DEV (push to main)" even though it now triggers on both `dev` and `main`.

## Acceptance Criteria

- `dcm-deploy.yml` header comment lists actual triggers (PR to dev/main + push to dev/main + workflow_dispatch).
- `CONTRIBUTING.md` adds a "Workflow contract" section that lists the exact `validate-pr.yml` `paths:` filter and the consequence for docs/workflow-only PRs.
- `CONTRIBUTING.md` adds an "Eval semantics by stage" table that says exactly which stage is advisory, which is blocking, and what advisory means in practice (alias has already moved; rollback is one DDL).

## Out of Scope

- Changing eval semantics. The advisory model is intentional because alias-based deploys are cheap to reverse.
- Removing the `paths:` filter on `validate-pr.yml`. The cost would be running a 12-minute SV eval on every README typo.

## Verification

- `validate-pr.yml` does not trigger on a PR that only changes `.github/workflows/**` or top-level docs (already verified in PR #59 and #60).
- A code-path change (e.g. test addition) on a PR triggers `validate-pr.yml` and posts the SV-eval and agent-eval comments.

## References

- `.github/workflows/dcm-deploy.yml`
- `.github/workflows/validate-pr.yml`
- `.github/workflows/deploy-prod-validated.yml`
- `.github/workflows/promote-validated-to-production.yml`
- `CONTRIBUTING.md` (sections "Workflow contract" and "Eval semantics by stage")
