# REQ-019: Pure-Function Seams for Eval Classification

**Status:** Done (this PR)
**Owner:** Jeremy Demlow
**Created:** 2026-05-19

## Problem

Two of the most failure-prone modules (`run_ci_eval`, `run_sv_eval`) embed classification logic that decides whether a CI eval result is a `pass`, an advisory threshold fail, a hard crash, or a known Snowflake platform blocker. That logic was historically inline and untestable without spinning up a real Snowflake eval, so changes in this area kept introducing regressions (REG-005 swallowed exit codes, alias preflight in REG-006).

## Acceptance Criteria

- `agent_management/run_ci_eval.py` exposes a pure `classify_eval_outcome(returncode, stdout, stderr)` returning one of `passed`, `threshold_fail`, `crashed`. The main loop calls it; behavior is unchanged.
- `agent_management/run_sv_eval.py` already exposes pure helpers `is_platform_blocker`, `compute_score`, and `_is_retryable`. They get explicit unit tests so the classification surface is locked in.
- New tests live in `tests/test_run_ci_eval.py` and `tests/test_run_sv_eval_helpers.py` and run as part of the default suite.

## Out of Scope

- Splitting the modules further (e.g., separate file per concern). The pure-function seams alone are sufficient. A bigger split should land in its own follow-up REQ once we have a second use case.
- Changing exit-code semantics. The taxonomy (0 pass, 1 threshold fail, 2 crash, 3 platform blocker) stays.

## Verification

```bash
uv run python -m pytest tests/test_run_ci_eval.py tests/test_run_sv_eval_helpers.py -q
```

Expected: all green (16 tests).

```bash
uv run python -m pytest tests -q
```

Expected: full suite green (was 150, now 166 with these additions).

## References

- `agent_management/run_ci_eval.py` (`classify_eval_outcome`)
- `agent_management/run_sv_eval.py` (`is_platform_blocker`, `compute_score`, `_is_retryable`)
- `tests/test_run_ci_eval.py`
- `tests/test_run_sv_eval_helpers.py`
- REG-005 (eval truthfulness), REG-006 (alias preflight)
