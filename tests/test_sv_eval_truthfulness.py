"""CI truthfulness regression tests for SV eval reporting.

These pin the contract enforced by Phase 1 of the truthfulness work:

* The PR comment header may say PASSED only when every recorded view is PASS.
* ERROR / NO_RUN / NO_DATA / FAIL each independently block PASSED.
* The footer reports each outcome class distinctly (no collapsing into
  "no-data") so reviewers can tell platform flakes from threshold misses.
* An upstream ``all_passed: true`` value is overruled by the actual rows.
* Threshold defaulting accepts an explicit ``0.0`` instead of silently
  swapping it for the 0.80 default via a falsy ``or``.
* The score collector's helpers behave as designed, in particular
  ``run_name_candidates`` produces the per-SV suffix form so the lookup
  finds events written by ``run_sv_eval``.
"""
from __future__ import annotations

from agent_management.format_sv_eval_comment import (
    _classify_header,
    _coalesce_threshold,
    _derive_all_passed,
    render_markdown,
)
from agent_management.get_sv_eval_scores import run_name_candidates


# ---------------------------------------------------------------------------
# Header / classification truthfulness
# ---------------------------------------------------------------------------


def _payload(views: dict, *, all_passed: bool | None = None) -> dict:
    payload: dict = {
        "environment": "dev",
        "threshold": 0.80,
        "views": views,
    }
    if all_passed is not None:
        payload["all_passed"] = all_passed
    return payload


def test_all_pass_renders_passed_header():
    md = render_markdown(_payload({"SEM_A": {"status": "PASS", "score": 1.0}}))
    assert "PASSED" in md.splitlines()[0]


def test_any_fail_renders_failed_header_not_passed():
    md = render_markdown(
        _payload(
            {
                "SEM_A": {"status": "PASS", "score": 1.0},
                "SEM_B": {"status": "FAIL", "score": 0.5},
            }
        )
    )
    first = md.splitlines()[0]
    assert "PASSED" not in first
    assert "FAILED" in first


def test_any_error_blocks_passed_header():
    md = render_markdown(
        _payload(
            {
                "SEM_A": {"status": "PASS", "score": 1.0},
                "SEM_B": {"status": "error", "error": "Invocation failed"},
            }
        )
    )
    first = md.splitlines()[0]
    assert "PASSED" not in first
    assert "ERRORED" in first


def test_no_run_blocks_passed_header():
    md = render_markdown(
        _payload(
            {
                "SEM_A": {"status": "PASS", "score": 1.0},
                "SEM_B": {"status": "no_run"},
            }
        )
    )
    first = md.splitlines()[0]
    assert "PASSED" not in first
    assert "INCOMPLETE" in first


def test_empty_blocks_passed_header():
    md = render_markdown(
        _payload(
            {
                "SEM_A": {"status": "PASS", "score": 1.0},
                "SEM_B": {"status": "empty"},
            }
        )
    )
    first = md.splitlines()[0]
    assert "PASSED" not in first
    assert "INCOMPLETE" in first


def test_all_error_does_not_say_passed_even_if_upstream_lies():
    md = render_markdown(
        _payload(
            {f"SEM_{i}": {"status": "error", "error": "x"} for i in range(11)},
            all_passed=True,  # upstream gaslighting
        )
    )
    first = md.splitlines()[0]
    assert "PASSED" not in first
    assert "ERRORED" in first


def test_no_views_renders_no_data_header():
    md = render_markdown({"environment": "dev", "threshold": 0.80, "views": {}})
    assert "NO DATA" in md.splitlines()[0]


# ---------------------------------------------------------------------------
# Footer counts: every outcome class shows up distinctly
# ---------------------------------------------------------------------------


def test_footer_distinguishes_pass_fail_error_no_run_no_data():
    md = render_markdown(
        _payload(
            {
                "SEM_A": {"status": "PASS", "score": 1.0},
                "SEM_B": {"status": "FAIL", "score": 0.0},
                "SEM_C": {"status": "error", "error": "x"},
                "SEM_D": {"status": "no_run"},
                "SEM_E": {"status": "empty"},
            }
        )
    )
    footer = next(line for line in md.splitlines() if line.startswith("Summary:"))
    assert "1 PASS" in footer
    assert "1 FAIL" in footer
    assert "1 ERROR" in footer
    assert "1 NO RUN" in footer
    assert "1 NO DATA" in footer
    assert "out of 5 semantic views" in footer


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_derive_all_passed_truthful_under_partial_failure():
    assert _derive_all_passed({"SEM_A": {"status": "PASS"}}) is True
    assert _derive_all_passed(
        {"SEM_A": {"status": "PASS"}, "SEM_B": {"status": "error"}}
    ) is False
    assert _derive_all_passed({}) is False


def test_classify_header_priority_fail_over_error_over_incomplete():
    fail_and_error = {"A": {"status": "FAIL"}, "B": {"status": "error"}}
    assert _classify_header(fail_and_error, all_passed=False) == "FAILED"

    error_and_no_run = {"A": {"status": "error"}, "B": {"status": "no_run"}}
    assert _classify_header(error_and_no_run, all_passed=False) == "ERRORED"

    just_no_run = {"A": {"status": "no_run"}}
    assert _classify_header(just_no_run, all_passed=False) == "INCOMPLETE"


def test_coalesce_threshold_keeps_explicit_zero():
    assert _coalesce_threshold(0.0) == 0.0
    assert _coalesce_threshold(0.6) == 0.6
    assert _coalesce_threshold(None) == 0.80
    assert _coalesce_threshold("not a number") == 0.80


def test_run_name_candidates_includes_per_sv_suffix():
    cands = run_name_candidates("PR-51-25457687951", "SEM_STAFFING_ANALYTICS")
    assert cands[0] == "PR-51-25457687951"
    assert "PR-51-25457687951_sem_staffing_analytics" in cands


def test_run_name_candidates_handles_already_suffixed_input():
    base = "PR-51-25457687951_sem_staffing_analytics"
    cands = run_name_candidates(base, "SEM_STAFFING_ANALYTICS")
    # No duplicate, but still resolves
    assert cands[0] == base
    # Suffixed-on-suffix is OK; we'd just try it second and miss harmlessly.
    assert all(isinstance(c, str) for c in cands)


def test_run_name_candidates_empty_input_returns_empty_list():
    assert run_name_candidates("", "SEM_X") == []
