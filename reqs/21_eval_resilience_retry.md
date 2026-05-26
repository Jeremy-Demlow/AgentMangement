# REQ-021: Agent Eval Resilience — STATUS_DETAILS Capture + Retry on Transient Flakes

**Status:** Done (this PR)
**Owner:** Jeremy Demlow
**Created:** 2026-05-19

## Problem

Agent evaluations fail intermittently with `STATUS = FAILED` and the eval framework prints the unhelpful line:

```
Evaluation did not complete: FAILED: FAILED
```

Concrete failure observed in [GH Actions run 26126004888](https://github.com/Jeremy-Demlow/AgentMangement/actions/runs/26126004888):

- `RESORT_EXECUTIVE_DEV` eval polled `CREATED -> INVOCATION_IN_PROGRESS x2 -> FAILED` at attempt 4 (~120s).
- All 15 invocations actually completed (visible in `GET_AI_EVALUATION_DATA` rows 21:53-21:55).
- One invocation took 60s and returned an "authentication issue" apology from the agent itself.
- Orchestrator gave up before metric scoring; `EVAL_AGG_SCORE` is NULL on every row.
- Direct `EXECUTE_AI_EVALUATION('STATUS', ...)` call shows `STATUS_DETAILS = "Invocation failed"` — the same Cortex transient signature we already retry for in `agent_management/run_sv_eval.py`.

The DEV warehouse is already multi-cluster (1-5, STANDARD) per DCM, and Snowflake confirmed the live config matches. So this is **not a warehouse capacity issue**. It is a Cortex platform-level transient that the agent eval path does not currently retry.

## Acceptance Criteria

- `agent-evaluation/scripts/run_eval.py::poll_until_done` returns `(status, status_details)` instead of just `status`. Both are surfaced in the per-attempt log line and in the failure summary.
- `is_retryable_failure(status_details)` is a pure function that returns True when the orchestrator's STATUS_DETAILS matches a known transient: `Invocation failed`, `service is currently unavailable`, `internal error`. Unknown/empty details do NOT retry.
- When `poll_until_done` reports a retryable FAILED, `main` restarts the eval ONCE under a fresh `run_name` (`<original>-r1`) before bailing.
- `tests/test_run_eval_helpers.py` covers the classification surface so future edits do not regress the retry contract.

## Out of Scope

- Bumping warehouse size or cluster counts. DCM already configures multi-cluster (1-5) for both DEV and PROD; the live warehouses match. Investigation showed contention was not the cause.
- Adding retry on TIMEOUT. Timeouts indicate genuine eval engine stuckness, not transient flake; retrying would just timeout again.
- Changing `run_ci_eval.py`'s parallelism. With multi-cluster warehouse and per-run retry, parallel eval starts are safe to keep at the default `max_parallel=10`.

## Verification

```bash
uv run python -m pytest tests/test_run_eval_helpers.py -v
```

Expected: 6 passed.

```bash
uv run python -m pytest tests -q
```

Expected: 181 passed.

Production verification will come from the next eval run. When it succeeds on retry, the per-attempt log will show:

```
  [04] Status: FAILED  (Invocation failed)
  Eval reported transient platform flake (STATUS_DETAILS='Invocation failed'); retrying once as <run_name>-r1...
```

## References

- `agent-evaluation/scripts/run_eval.py` (`poll_until_done`, `is_retryable_failure`, retry block in `main`)
- `tests/test_run_eval_helpers.py`
- `agent_management/run_sv_eval.py:74-91` (existing platform-blocker pattern this mirrors)
- `.github/workflows/deploy-prod-validated.yml:178-201` (existing crash-retry pattern this mirrors)
- REG-005 (eval truthfulness — same root class as this fix)
- DCM `dcm/manifest.yml` lines 44-45 / 62-63 / 82-83 (already-correct multi-cluster config)
