# 12 — Docs integration

## Problem

`framework/` currently holds draft best-practice docs that the user wants hidden (not externally published) until complete. But we don't want to throw away the content.

## Goal

- `framework/` is added to `.gitignore` (content stays on local disks and branches during refinement, does not ship to main)
- The parts that are ready now are folded into existing repo docs:

| framework/* content | destination |
|---------------------|-------------|
| Tool description template (PURPOSE/DATA/KEY METRICS/…)  | `CONTRIBUTING.md` → new "Agent spec style guide" section |
| VQR expansion guidance                                   | `docs/semantic-views/VQR_GUIDE.md` (new) |
| Agent versioning rollout plan                            | `docs/operations/AGENT_VERSIONING.md` (new) |
| Rollback runbook                                         | `docs/operations/ROLLBACK_RUNBOOK.md` (new) |

## `docs/` tree (new files)

```
docs/
  operations/
    AGENT_VERSIONING.md       — what it is, how the flag works, rollout plan
    ROLLBACK_RUNBOOK.md       — steps for on-call to revert prod
  semantic-views/
    VQR_GUIDE.md              — how to write verified queries, SV-specific tips
```

## `CONTRIBUTING.md` diff

Add section:

```
## Agent spec style guide

Every `tools[i].description` must include these sections in order:

  PURPOSE
  DATA
  KEY METRICS
  KEY DIMENSIONS
  USE FOR
  NOT FOR
  CROSS-REFERENCE WITH

Validate locally:

    python -m agent_management.validate_spec_format agents/specs/<spec>.yml
```

## `.gitignore` additions

```
/framework/
/snapshots/
/agent_optimization/      # deleted, but keep entry until the delete is merged
```
