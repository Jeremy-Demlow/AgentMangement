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


# ---------------------------------------------------------------------------
# Platform error signature list (broadened beyond "Invocation failed")
# ---------------------------------------------------------------------------


def test_is_platform_error_recognizes_invocation_failed():
    from agent_management.get_sv_eval_scores import is_platform_error
    assert is_platform_error("Invocation failed") is True
    assert is_platform_error("INVOCATION FAILED on attempt 3") is True
    assert is_platform_error("invocation failed; retrying") is True


def test_is_platform_error_recognizes_392700():
    from agent_management.get_sv_eval_scores import is_platform_error
    assert is_platform_error("392700") is True
    assert is_platform_error("Error 392700: ...") is True


def test_is_platform_error_rejects_real_errors():
    from agent_management.get_sv_eval_scores import is_platform_error
    assert is_platform_error("syntax error at line 1") is False
    assert is_platform_error("permission denied") is False


def test_is_platform_error_handles_empty_and_none():
    from agent_management.get_sv_eval_scores import is_platform_error
    assert is_platform_error("") is False
    assert is_platform_error(None) is False


def test_extract_platform_error_code_returns_signature():
    from agent_management.get_sv_eval_scores import extract_platform_error_code
    assert extract_platform_error_code("Invocation failed") == "invocation failed"
    assert extract_platform_error_code("392700") == "392700"
    assert extract_platform_error_code("syntax error") is None
    assert extract_platform_error_code(None) is None


def test_score_results_counts_392700_as_flake():
    rows = [
        {"EVAL_AGG_SCORE": None, "ERROR": "392700", "INPUT": "q1"},
        {"EVAL_AGG_SCORE": None, "ERROR": "Invocation failed", "INPUT": "q2"},
        {"EVAL_AGG_SCORE": 1.0, "ERROR": "", "INPUT": "q3"},
    ]
    metrics = score_results(rows)
    assert metrics["errors"] == 2
    # Both 392700 and "Invocation failed" should now register as flakes
    assert metrics["flake_errors"] == 2


def test_platform_row_surfaces_error_code_in_comment():
    md = render_markdown(
        _payload(
            {
                "SEM_SAFETY_INCIDENTS": {
                    "status": "platform_blocked",
                    "score": 0.0,
                    "scored": 0,
                    "errors": 3,
                    "flake_errors": 3,
                    "platform_error_codes": ["392700"],
                    "run_name": "PR-52-...",
                }
            }
        )
    )
    # The row should call out the error code so reviewers can tell
    # which platform issue is biting at a glance.
    row = next(line for line in md.splitlines() if "SEM_SAFETY" in line and "|" in line)
    assert "392700" in row
    assert "PLATFORM" in row


# ---------------------------------------------------------------------------
# regen_sv_gold helpers (row-equivalence checker)
# ---------------------------------------------------------------------------


def test_regen_strip_request_id_comment():
    from agent_management.regen_sv_gold import strip_request_id_comment
    sql = "SELECT 1 -- Generated by Cortex Analyst (request_id: abc-123) ;"
    assert strip_request_id_comment(sql) == "SELECT 1"
    # Should also handle missing trailing semicolon
    assert strip_request_id_comment("SELECT 2") == "SELECT 2"
    # Empty input
    assert strip_request_id_comment("") == ""
    assert strip_request_id_comment(None) == ""


def test_regen_column_sorted_rows_handles_mixed_types_and_nones():
    from agent_management.regen_sv_gold import _column_sorted_rows
    cols = ["B", "A"]  # intentionally out of order
    rows = [
        ("y", 2),
        ("x", None),
        ("z", 1.0001234567),
    ]
    sorted_rows = _column_sorted_rows(cols, rows)
    # Column-sorted by name (A first, then B) and rows then sorted by str key.
    assert len(sorted_rows) == 3
    # Floats are rounded to 6 decimal places
    for row in sorted_rows:
        for cell in row:
            if isinstance(cell, float):
                assert cell == round(cell, 6)


def test_regen_column_sorted_rows_empty_input():
    from agent_management.regen_sv_gold import _column_sorted_rows
    assert _column_sorted_rows([], []) == []
    assert _column_sorted_rows(["A"], []) == []
