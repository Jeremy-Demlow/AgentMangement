"""Unit tests for agent-evaluation/scripts/run_eval.py classification helpers.

REQ-021: Capture STATUS_DETAILS and retry once on transient Cortex platform
flakes ("Invocation failed", service unavailable, internal error).
"""
from __future__ import annotations

import sys
from pathlib import Path

# agent-evaluation/scripts is not a package; load the module directly.
SCRIPT_PATH = Path(__file__).resolve().parents[1] / "agent-evaluation" / "scripts"
sys.path.insert(0, str(SCRIPT_PATH))

import importlib.util

spec = importlib.util.spec_from_file_location("run_eval", SCRIPT_PATH / "run_eval.py")
run_eval = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_eval)


def test_invocation_failed_is_retryable():
    assert run_eval.is_retryable_failure("Invocation failed") is True


def test_invocation_failed_is_retryable_case_insensitive():
    assert run_eval.is_retryable_failure("INVOCATION FAILED") is True
    assert run_eval.is_retryable_failure("invocation failed: 392700") is True


def test_service_unavailable_is_retryable():
    assert run_eval.is_retryable_failure("Service is currently unavailable") is True


def test_internal_error_is_retryable():
    assert run_eval.is_retryable_failure("Cortex internal error 500") is True


def test_metric_judge_failure_is_NOT_retryable():
    """Metric judge failures happen during COMPUTATION_IN_PROGRESS, by which
    time Cortex has already created its internal
    SYSTEM_AI_OBS_CORTEX_AGENT_DATASET_VERSION_DO_NOT_DELETE object. A retry
    would crash at EXECUTE_AI_EVALUATION('START', ...) with error 210007
    (`Dataset version ... already exists`). So we explicitly do NOT auto-retry
    these and instead surface the real signal.
    """
    assert run_eval.is_retryable_failure(
        "Metric 'logical_consistency' failed"
    ) is False
    assert run_eval.is_retryable_failure(
        "Metric 'answer_correctness' failed; Metric 'logical_consistency' failed"
    ) is False


def test_timeout_is_retryable():
    assert run_eval.is_retryable_failure("Request timed out after 60s") is True
    assert run_eval.is_retryable_failure("Cortex TIMEOUT") is True


def test_rate_limit_is_retryable():
    assert run_eval.is_retryable_failure("Rate limit exceeded") is True


def test_unknown_signature_is_not_retryable():
    """Authoring errors should NOT auto-retry; that masks real signal."""
    assert run_eval.is_retryable_failure("Spec rejected: missing tool description") is False


def test_empty_details_is_not_retryable():
    """No signal == do not retry. Avoids retry-blast on unknown failures."""
    assert run_eval.is_retryable_failure("") is False
    assert run_eval.is_retryable_failure(None) is False


def test_retryable_handles_json_array_status_details():
    """Snowflake returns STATUS_DETAILS as a JSON-encoded array string for
    multi-error cases. is_retryable_failure must transparently parse it.
    Use a still-retryable signature to assert array parsing works.
    """
    raw = '[\n  "Invocation failed"\n]'
    assert run_eval.is_retryable_failure(raw) is True


def test_retryable_handles_python_list_status_details():
    """Some driver paths return STATUS_DETAILS already deserialized."""
    raw = ["Invocation failed", "service is currently unavailable"]
    assert run_eval.is_retryable_failure(raw) is True


def test_array_metric_judge_failure_remains_not_retryable():
    """Even when metric-judge errors arrive as a JSON array, they must not
    auto-retry. Locks the contract that array shape never accidentally flips
    a non-retryable signature into retryable.
    """
    raw = '[\n  "Metric \'logical_consistency\' failed"\n]'
    assert run_eval.is_retryable_failure(raw) is False


def test_flatten_status_details_string_passthrough():
    assert run_eval._flatten_status_details("Invocation failed") == "Invocation failed"


def test_flatten_status_details_json_array_to_joined_string():
    raw = '[\n  "Metric \'logical_consistency\' failed"\n]'
    assert run_eval._flatten_status_details(raw) == "Metric 'logical_consistency' failed"


def test_flatten_status_details_multi_item_array():
    raw = '["err one", "err two"]'
    assert run_eval._flatten_status_details(raw) == "err one; err two"


def test_flatten_status_details_python_list():
    assert run_eval._flatten_status_details(["a", "b"]) == "a; b"


def test_flatten_status_details_empty():
    assert run_eval._flatten_status_details(None) == ""
    assert run_eval._flatten_status_details("") == ""
