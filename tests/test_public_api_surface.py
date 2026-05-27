"""Public package surface tests.

The library should expose obvious subpackages for agent lifecycle operations,
agent evaluations, semantic-view evaluations, and semantic-view management.
These tests protect the package-first shape while legacy modules are thinned
into compatibility wrappers.
"""
from __future__ import annotations

import tomllib
from pathlib import Path


def test_agent_lifecycle_public_surface_imports():
    from agent_management.agents import deploy_agent, get_aliases, run_smoke_test

    assert callable(deploy_agent)
    assert callable(get_aliases)
    assert callable(run_smoke_test)


def test_eval_public_surfaces_are_distinct():
    from agent_management.evals.agent import classify_eval_outcome, main as agent_eval_main
    from agent_management.evals.semantic_view import main as sv_eval_main, score_results

    assert classify_eval_outcome(0, "", "") == "passed"
    assert callable(agent_eval_main)
    assert callable(score_results)
    assert callable(sv_eval_main)


def test_eval_core_reexports_shared_helpers():
    from agent_management.evals.core import compute_score, is_platform_blocker

    assert compute_score([])["total"] == 0
    assert is_platform_blocker("SYSTEM_AI_OBS_ANALYST_EVAL missing") is True


def test_semantic_view_public_surface_imports():
    from agent_management.semantic_views import check_sv, find_sv_files, sync

    assert callable(check_sv)
    assert callable(find_sv_files)
    assert callable(sync)


def test_console_scripts_point_at_domain_packages():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text())
    scripts = pyproject["project"]["scripts"]

    assert scripts["agent-mgmt-deploy-agents"] == "agent_management.agents.deploy:main"
    assert scripts["agent-mgmt-deploy-svs"] == "agent_management.semantic_views.deploy:main"
    assert scripts["agent-mgmt-snapshot"] == "agent_management.agents.snapshot_state:main"
    assert scripts["agent-mgmt-rollback"] == "agent_management.agents.rollback:main"
    assert scripts["agent-mgmt-eval-agent"] == "agent_management.evals.agent:main"
    assert scripts["agent-mgmt-eval-sv"] == "agent_management.evals.semantic_view:main"
