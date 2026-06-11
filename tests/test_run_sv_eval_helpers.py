"""Unit tests for pure helpers in agent_management.evals.sv_runner.

REQ-019 followup: lock down platform-blocker classification and score
computation so future refactors stay safe.
"""
from __future__ import annotations

from agent_management.evals.sv_runner import compute_score, _is_retryable, is_platform_blocker


def test_is_platform_blocker_matches_known_pupr_signature():
    err = (
        "100071: Semantic View Optimization "
        "'AM_SKI_RESORT_DEV.SEMANTIC.SYSTEM_AI_OBS_ANALYST_EVAL_SEM_REVENUE' "
        "does not exist or not authorized."
    )
    assert is_platform_blocker(err) is True


def test_is_platform_blocker_matches_lowercase_phrase():
    assert is_platform_blocker("system_ai_obs_analyst_eval missing") is True


def test_is_platform_blocker_returns_false_for_real_threshold_fail():
    assert is_platform_blocker("score below threshold") is False


def test_is_platform_blocker_handles_none():
    assert is_platform_blocker(None) is False


def test_compute_score_empty_results():
    assert compute_score([]) == {
        "total": 0,
        "scored": 0,
        "sum_score": 0.0,
        "score": 0.0,
        "errors": 0,
        "flake_errors": 0,
    }


def test_compute_score_mixed_results():
    rows = [
        {"EVAL_AGG_SCORE": 1.0},
        {"EVAL_AGG_SCORE": 0.5},
        {"EVAL_AGG_SCORE": 0.0},
        {"EVAL_AGG_SCORE": None, "ERROR": "Invocation failed"},
        {"EVAL_AGG_SCORE": None, "ERROR": "Schema does not exist"},
    ]
    out = compute_score(rows)
    assert out["total"] == 5
    assert out["scored"] == 3
    assert out["sum_score"] == 1.5
    assert out["score"] == 0.5
    assert out["errors"] == 2
    assert out["flake_errors"] == 1


def test_is_retryable_true_when_only_flake_errors():
    metrics = {"errors": 2, "flake_errors": 2}
    assert _is_retryable(metrics) is True


def test_is_retryable_false_when_real_error_present():
    metrics = {"errors": 3, "flake_errors": 1}
    assert _is_retryable(metrics) is False


def test_is_retryable_false_when_no_errors():
    metrics = {"errors": 0, "flake_errors": 0}
    assert _is_retryable(metrics) is False
