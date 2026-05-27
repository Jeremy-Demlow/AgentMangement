"""Semantic View evaluation API.

Semantic View evals use Cortex Analyst and ``GET_ANALYST_AI_EVALUATION_DATA``;
they are intentionally separate from Cortex Agent evals.
"""
from __future__ import annotations

from agent_management.evals.sv_scores import fetch_eval_data_with_fallback, is_platform_error, score_results
from agent_management.evals.sv_runner import (
    compute_score,
    generate_eval_yaml,
    is_platform_blocker,
    main,
    poll_and_collect,
    run_eval_for_sv,
    start_sv_eval,
)

__all__ = [
    "compute_score",
    "fetch_eval_data_with_fallback",
    "generate_eval_yaml",
    "is_platform_blocker",
    "is_platform_error",
    "main",
    "poll_and_collect",
    "run_eval_for_sv",
    "score_results",
    "start_sv_eval",
]
