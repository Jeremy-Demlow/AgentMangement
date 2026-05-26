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


def test_unknown_signature_is_not_retryable():
    """Authoring errors should NOT auto-retry; that masks real signal."""
    assert run_eval.is_retryable_failure("Spec rejected: missing tool description") is False


def test_empty_details_is_not_retryable():
    """No signal == do not retry. Avoids retry-blast on unknown failures."""
    assert run_eval.is_retryable_failure("") is False
    assert run_eval.is_retryable_failure(None) is False
