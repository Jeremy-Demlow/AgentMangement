"""Cortex Agent evaluation API.

The executable implementation currently lives in :mod:`agent_management.run_ci_eval`
and ``agent-evaluation/scripts/run_eval.py``. This facade gives library users a
stable import path while the scripts are thinned into wrappers.
"""
from __future__ import annotations

from agent_management.run_ci_eval import (
    build_cmd,
    classify_eval_outcome,
    extract_run_name,
    find_eval_configs,
    prepare_agent,
    run_single_eval,
)

__all__ = [
    "build_cmd",
    "classify_eval_outcome",
    "extract_run_name",
    "find_eval_configs",
    "prepare_agent",
    "run_single_eval",
]
