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
from agent_management.get_sv_eval_scores import run_name_candidates, score_results


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


# ---------------------------------------------------------------------------
# Platform-blocked classification (Cortex Analyst "Invocation failed" flake)
# ---------------------------------------------------------------------------


def test_score_results_counts_flake_errors_separately():
    rows = [
        {"EVAL_AGG_SCORE": None, "ERROR": "Invocation failed", "INPUT": "q1"},
        {"EVAL_AGG_SCORE": None, "ERROR": "INVOCATION FAILED on attempt", "INPUT": "q2"},
        {"EVAL_AGG_SCORE": None, "ERROR": "Some other error", "INPUT": "q3"},
        {"EVAL_AGG_SCORE": 1.0, "ERROR": "", "INPUT": "q4"},
    ]
    metrics = score_results(rows)
    assert metrics["scored"] == 1
    assert metrics["errors"] == 3
    assert metrics["flake_errors"] == 2  # only the two "invocation failed" rows


def test_score_results_no_errors_means_zero_flake():
    rows = [
        {"EVAL_AGG_SCORE": 1.0, "ERROR": "", "INPUT": "q1"},
        {"EVAL_AGG_SCORE": 0.0, "ERROR": "", "INPUT": "q2"},
    ]
    metrics = score_results(rows)
    assert metrics["errors"] == 0
    assert metrics["flake_errors"] == 0


def test_platform_blocked_renders_platform_header_not_failed():
    md = render_markdown(
        _payload(
            {
                "SEM_A": {"status": "PASS", "score": 1.0},
                "SEM_SAFETY": {"status": "platform_blocked", "errors": 3, "flake_errors": 3},
            }
        )
    )
    first = md.splitlines()[0]
    assert "PASSED" not in first
    assert "FAILED" not in first
    assert "PLATFORM_BLOCKED" in first


def test_platform_blocked_alone_does_not_say_passed():
    md = render_markdown(
        _payload(
            {f"SEM_{i}": {"status": "platform_blocked"} for i in range(3)}
        )
    )
    first = md.splitlines()[0]
    assert "PASSED" not in first
    assert "PLATFORM_BLOCKED" in first


def test_platform_blocked_plus_real_fail_still_says_failed():
    # FAIL outranks PLATFORM_BLOCKED -- a real threshold miss is the bigger
    # signal and should win the header.
    md = render_markdown(
        _payload(
            {
                "SEM_A": {"status": "FAIL", "score": 0.4},
                "SEM_B": {"status": "platform_blocked", "errors": 3, "flake_errors": 3},
            }
        )
    )
    first = md.splitlines()[0]
    assert "FAILED" in first
    assert "PLATFORM_BLOCKED" not in first


def test_platform_blocked_plus_real_error_says_errored():
    # ERROR outranks PLATFORM_BLOCKED -- an unhandled lookup failure is more
    # serious than a known platform flake.
    md = render_markdown(
        _payload(
            {
                "SEM_A": {"status": "error", "error": "x"},
                "SEM_B": {"status": "platform_blocked"},
            }
        )
    )
    first = md.splitlines()[0]
    assert "ERRORED" in first


def test_footer_distinguishes_platform_from_fail_and_error():
    md = render_markdown(
        _payload(
            {
                "SEM_A": {"status": "PASS", "score": 1.0},
                "SEM_B": {"status": "FAIL", "score": 0.0},
                "SEM_C": {"status": "error"},
                "SEM_D": {"status": "platform_blocked"},
                "SEM_E": {"status": "no_run"},
                "SEM_F": {"status": "empty"},
            }
        )
    )
    footer = next(line for line in md.splitlines() if line.startswith("Summary:"))
    assert "1 PASS" in footer
    assert "1 FAIL" in footer
    assert "1 ERROR" in footer
    assert "1 PLATFORM" in footer
    assert "1 NO RUN" in footer
    assert "1 NO DATA" in footer
    assert "out of 6 semantic views" in footer


def test_platform_row_renders_as_PLATFORM():
    md = render_markdown(
        _payload(
            {"SEM_SAFETY": {"status": "platform_blocked", "errors": 3, "flake_errors": 3}}
        )
    )
    # Find the row line for SEM_SAFETY
    row = next(line for line in md.splitlines() if "SEM_SAFETY" in line and "|" in line)
    assert "PLATFORM" in row
    # PLATFORM is rendered, not "FAIL" -- no false threshold-miss signal.
    assert "FAIL" not in row.replace("FAILED", "")


def test_classify_header_priority_with_platform():
    # FAIL > ERROR > PLATFORM_BLOCKED > INCOMPLETE
    fail_and_platform = {"A": {"status": "FAIL"}, "B": {"status": "platform_blocked"}}
    assert _classify_header(fail_and_platform, all_passed=False) == "FAILED"

    error_and_platform = {"A": {"status": "error"}, "B": {"status": "platform_blocked"}}
    assert _classify_header(error_and_platform, all_passed=False) == "ERRORED"

    platform_and_no_run = {"A": {"status": "platform_blocked"}, "B": {"status": "no_run"}}
    assert _classify_header(platform_and_no_run, all_passed=False) == "PLATFORM_BLOCKED"


def test_derive_all_passed_blocks_on_platform_blocked():
    # Platform-blocked is NOT a pass; it must block PASSED so a flaky run
    # cannot silently look healthy.
    mixed = {"A": {"status": "PASS"}, "B": {"status": "platform_blocked"}}
    assert _derive_all_passed(mixed) is False
