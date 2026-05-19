"""Unit tests for agent_management.run_ci_eval.classify_eval_outcome.

REQ-019: Pure-function seam for crash-vs-threshold classification.
"""
from __future__ import annotations

from agent_management.run_ci_eval import classify_eval_outcome, extract_run_name


def test_classify_passed_on_zero_returncode():
    assert classify_eval_outcome(0, "any stdout", "any stderr") == "passed"


def test_classify_threshold_fail_when_eval_ran_to_completion():
    stdout = "EVALUATION RESULTS\n  THRESHOLD CHECK\n    answer_correctness 0.50 [FAIL]"
    stderr = ""
    assert classify_eval_outcome(1, stdout, stderr) == "threshold_fail"


def test_classify_crashed_when_threshold_check_section_missing():
    stdout = "Some early progress before exception"
    stderr = ""
    assert classify_eval_outcome(2, stdout, stderr) == "crashed"


def test_classify_crashed_on_python_traceback_even_with_threshold_section():
    """A Traceback in stderr always wins over a THRESHOLD CHECK in stdout.

    Real example: eval gets to the threshold section then crashes during
    result fetching. The presence of the section does not prove a clean
    eval cycle.
    """
    stdout = "EVALUATION RESULTS\n  THRESHOLD CHECK\n    answer_correctness 0.95 [PASS]"
    stderr = "Traceback (most recent call last):\n  File ..."
    assert classify_eval_outcome(2, stdout, stderr) == "crashed"


def test_classify_handles_none_streams():
    """Subprocess streams may be None on early failures."""
    assert classify_eval_outcome(1, None, None) == "crashed"


def test_extract_run_name_finds_token():
    stdout = "Some preamble\nRun started:    eval_2026_05_19_abc123\nmore output"
    assert extract_run_name(stdout) == "eval_2026_05_19_abc123"


def test_extract_run_name_returns_none_when_absent():
    assert extract_run_name("no run started line here") is None
