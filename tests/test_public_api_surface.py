"""Public package surface tests.

The library should expose obvious subpackages for agent lifecycle operations,
agent evaluations, semantic-view evaluations, and semantic-view management.
These tests protect the package-first shape while legacy modules are thinned
into compatibility wrappers.
"""
from __future__ import annotations


def test_agent_lifecycle_public_surface_imports():
    from agent_management.agents import deploy_agent, get_aliases, run_smoke_test

    assert callable(deploy_agent)
    assert callable(get_aliases)
    assert callable(run_smoke_test)


def test_eval_public_surfaces_are_distinct():
    from agent_management.evals.agent import classify_eval_outcome
    from agent_management.evals.semantic_view import score_results

    assert classify_eval_outcome(0, "", "") == "passed"
    assert callable(score_results)


def test_eval_core_reexports_shared_helpers():
    from agent_management.evals.core import compute_score, is_platform_blocker

    assert compute_score([])["total"] == 0
    assert is_platform_blocker("SYSTEM_AI_OBS_ANALYST_EVAL missing") is True


def test_semantic_view_public_surface_imports():
    from agent_management.semantic_views import check_sv, find_sv_files, sync

    assert callable(check_sv)
    assert callable(find_sv_files)
    assert callable(sync)
