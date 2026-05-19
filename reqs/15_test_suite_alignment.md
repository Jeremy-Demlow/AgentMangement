# REQ-015: Test Suite Alignment

**Status:** Done (this PR)
**Owner:** Jeremy Demlow
**Created:** 2026-05-19

## Problem

`uv run python -m pytest tests -q` reported `144 passed, 6 failed`. The failures were not in production code; they were stale unit tests that still modeled an older `versioning.get_aliases()` contract.

Background: `get_aliases()` originally read alias columns out of `SHOW VERSIONS`, which Snowflake reports as frequently empty even when aliases exist. The implementation switched to reading the canonical alias JSON object on `DESCRIBE AGENT`. The `FakeCursor` rows in `tests/test_versioning.py` and the `FakeConn` in `tests/test_smoke_test.py` were never updated, so they still produced empty alias maps. The `_preflight_selector` in `agent_management.smoke_test` therefore refused to run with `RuntimeError: alias 'latest' is not set`, and `promote_alias` raised before reaching its no-op logic.

## Acceptance Criteria

- `uv run python -m pytest tests -q` runs to completion with 0 failures.
- `tests/test_versioning.py::test_get_aliases_*` validates `DESCRIBE AGENT` alias JSON parsing.
- `tests/test_versioning.py::test_promote_alias_*` exercises the canonical alias JSON shape.
- `tests/test_smoke_test.py::FakeConn` provides alias metadata via DESCRIBE AGENT so `_preflight_selector` accepts `alias="latest"`.
- Negative cases for missing alias and missing `DEFAULT` remain enforced.

## Out of Scope

- Refactoring `_preflight_selector` itself; behavior is correct.
- Restructuring how the smoke test discovers org/account URL.

## Verification

```bash
uv run python -m pytest tests -q
```

Expected: `150 passed`.

## References

- `agent_management/versioning.py:136-166` (`get_aliases` reads `DESCRIBE AGENT`)
- `agent_management/smoke_test.py` (`_preflight_selector`)
- `tests/test_versioning.py`
- `tests/test_smoke_test.py`
