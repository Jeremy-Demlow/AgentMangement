# CI Approval Cheat-Sheet

A one-page guide to every approval gate in the agent-management pipeline: when
you'll see it, who should click it, and what to check before approving.

## Gate summary

| Gate | Workflow | When | Who approves | What it does |
| :--- | :--- | :--- | :--- | :--- |
| (none) | `validate-pr.yml` | Every PR to `dev` or `main` | — | Auto-runs on PR events. No approval. |
| (none) | `deploy-dev.yml` | Every push to `dev` | — | Auto-deploys to DEV. No approval. Concurrency cancels stale runs. |
| **PROD gate** | `deploy-prod-validated.yml` | Every merge to `main` | PROD reviewer | **Single** approval. After click: snapshot, deploy SVs, deploy agents to `validated` alias, eval. |
| **production-promote gate** | `promote-validated-to-production.yml` | Manual workflow_dispatch | production-promote reviewer | Flips the `production` alias onto whatever currently holds `validated`. This is the customer-traffic change. |
| (none) | `rollback-agents.yml` | Manual workflow_dispatch | — | Operator-only tool. Moves alias to a previous version. See `ROLLBACK_RUNBOOK.md`. |

There are exactly **two** human approvals in the whole main-merge → customer-traffic
pipeline, and they are deliberate:

1. **PROD gate** on main-merge: *"is this change allowed into the prod environment at all?"*
2. **production-promote gate** on alias flip: *"is this change allowed to receive customer traffic?"*

Everything between those two points runs automatically after the first approval.

---

## Gate 1: PROD gate (on main-merge)

**Click when:**
- The PR has a green ✓ on all required checks (validate-pr workflow)
- The PR comment shows Agent Evaluation **PASSED**
- The PR comment shows SV Evaluation — review FAIL rows, decide if acceptable
  (platform-flake failures are auto-retried; real metric regressions are signal)
- The PR comment on "Recent Release Activity" (if present) doesn't show a pattern
  of rollbacks that would warrant a pause

**Don't click if:**
- Agent Eval is FAIL on a metric you care about (not a platform flake)
- Rollback history shows the affected agent was rolled back within the last 24h
  (let the previous change stabilize first)
- Drift detection in dbt-quality-gate is FAIL (block — fix the dbt model first)

**What happens when you click:**
1. `prod-gate` job completes (visible "Approval acknowledged" in the run summary)
2. `snapshot` job captures the pre-deploy state (uploaded as artifact, 90-day retention)
3. `deploy-svs` syncs VQRs into dbt, runs dbt, deploys all semantic views to PROD
4. `deploy-agents` submits a new agent version to PROD, moves `validated` alias onto it, runs smoke tests
5. `agent-eval` runs eval on the new `validated` alias and uploads results

The `production` alias is **NOT** touched by this workflow. Customer traffic is
unaffected until you run Gate 2.

---

## Gate 2: production-promote gate (on alias flip)

**Click when:**
- Gate 1 finished successfully (`validated` alias is on the new version)
- Eval on `validated` alias passed (check the Deploy Prod (validated) run summary)
- You've done whatever manual validation your org requires (smoke with a test
  account, product review, etc.)

**Don't click if:**
- Eval on `validated` showed regression vs the current `production` version
- There's an ongoing incident on the agent
- You're in a change-freeze window

**What happens when you click:**
1. `promote_alias` moves `production` alias from its current version onto whichever
   version currently holds `validated`
2. Audit row appears in `CORTEX_AGENT_VERSION_LOG` with `event_type='promote'`
3. Customer traffic begins landing on the new version

**Rollback after promote:**
Use `rollback-agents.yml` (`workflow_dispatch`) — does not require an approval,
because during incidents you need to move fast. See `ROLLBACK_RUNBOOK.md`.

---

## Reading PR comments

Every PR to `main` gets up to three auto-posted comments:

### `DEV Evaluation Summary`
Agent eval scores on the DEV environment. Posted by `agent-eval` job.
- Review per-agent pass/fail
- Investigate any regressions
- Platform flakes on agent eval are rare but possible; re-run the workflow if unsure

### `Semantic View Evaluation Summary (DEV)`
Per-SV sql_correctness scores. Posted by `sv-eval` job.
- Threshold is typically 80%
- `Invocation failed` on a single SV is auto-retried once — if it still fails,
  it's shown here. That's *platform-level flakiness on Cortex Analyst*, not a
  regression in the SV itself.
- The **blocking** SV gate is `detect_sv_drift --fail-on-drift` in the
  dbt-quality-gate job. This eval comment is advisory.

### `Recent Release Activity`
Last 7 days of rollback + promote events across PROD (and DEV fallback).
- Only appears when there's activity to report (no comment = quiet week)
- Useful signal for reviewers: "this agent was rolled back twice last week, be extra careful"

---

## What's **not** gated

These all run automatically, no approval:

- DEV deploys on every push to `dev`
- PR validation (lint, unit tests, dry-run deploy, drift check, DEV evals)
- Artifact uploads and PR comments
- Rollback operations (operator-initiated, always unblocked)

---

## Who has approval rights

Configured in GitHub → Settings → Environments:

- **PROD**: (see GitHub environment settings for current reviewer list)
- **production-promote**: (see GitHub environment settings)
- **DEV**: not gated (no reviewers configured)

Add/remove reviewers there. Changes to reviewer lists should be rare and
intentional.

---

## Concurrency behavior

| Workflow | Group | Cancel in progress? |
| :--- | :--- | :--- |
| `validate-pr.yml` | per-PR | Yes — new commits cancel stale runs |
| `deploy-dev.yml` | `deploy-dev` | Yes — latest push wins |
| `deploy-prod-validated.yml` | `deploy-prod-validated` | **No** — prod deploys queue, never cancel |

---

## Related docs

- `AGENT_VERSIONING.md` — versioning concepts, DDL reference, alias semantics
- `ROLLBACK_RUNBOOK.md` — on-call steps for rollback
- `CORTEX_AGENT_VERSION_LOG` — audit table reference (schema in `agent_management/version_log.py`)
