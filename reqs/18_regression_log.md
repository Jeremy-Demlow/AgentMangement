# REQ-018: Permanent Regression Log

**Status:** Done (this PR)
**Owner:** Jeremy Demlow
**Created:** 2026-05-19

## Problem

`tests/regression.md` was a single-row template. Multiple painful production bugs were fixed in the past two weeks (NULL-bootstrap NUMBER drift, all-or-nothing idempotency, dbt resolver conflict, eval truthfulness, alias preflight, branch drift). None of them were captured as regression knowledge, so the next person to encounter a similar pattern would have to rediscover the root cause.

## Acceptance Criteria

- `tests/regression.md` includes one entry per fixed bug:
  - REG-001: SUBCATEGORY NUMBER drift
  - REG-002: NOTES NUMBER drift on RAW + MARTS
  - REG-003: All-or-nothing idempotency
  - REG-004: dbt-snowflake resolver conflict
  - REG-005: SV eval truthfulness (advisory swallowed exit codes)
  - REG-006: Alias preflight + DEFAULT alias requirement
  - REG-007: `dev` branch drift after main-only hotfixes
- Each entry has root cause, fix summary, regression test or check, fix date, and the linked REQ-ID.

## Out of Scope

- Generating new automated tests for entries that are workflow-driven (e.g. REG-007). The verification field cites the manual check.

## Verification

```bash
grep -nE '^\| REG-' tests/regression.md | wc -l
```

Expected: 7 rows.

## References

- `tests/regression.md`
- `tests/test_data_generation_subcategory.py`
- `tests/test_data_generation_idempotency.py`
- `tests/test_sv_eval_truthfulness.py`
- `tests/test_versioning.py`
- `tests/test_smoke_test.py`
