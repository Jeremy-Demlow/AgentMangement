"""Package layout guardrails.

The product package should expose domain packages, not a flat pile of CLI
wrappers. Legacy wrappers are preserved under old/ for reference, but they must
not ship inside the installable agent_management package.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPO_ROOT / "agent_management"

ALLOWED_ROOT_MODULES = {
    "__init__.py",
    "paths.py",
    "render_template.py",
    "snowflake_config.py",
    "validate_spec_format.py",
    "validate_specs.py",
}

OLD_ROOT_MODULES = {
    "check_qa_recency",
    "check_sv_eval",
    "check_sv_evals",
    "compute_metrics",
    "deploy_agents",
    "deploy_semantic_views",
    "deploy_svs_yaml",
    "detect_drift",
    "detect_sv_drift",
    "format_rollback_history_comment",
    "format_sv_eval_comment",
    "get_sv_eval_scores",
    "regen_sv_gold",
    "render_eval_templates",
    "rollback",
    "run_ci_eval",
    "run_sv_eval",
    "smoke_test",
    "snapshot_agent",
    "snapshot_state",
    "sync_vqrs_to_dbt",
    "version_log",
    "versioning",
}


def test_package_root_contains_only_shared_modules():
    root_modules = {path.name for path in PACKAGE_ROOT.glob("*.py")}

    assert root_modules == ALLOWED_ROOT_MODULES


def test_legacy_wrappers_are_not_shipped_in_package_root():
    root_module_stems = {path.stem for path in PACKAGE_ROOT.glob("*.py")}

    assert not (root_module_stems & OLD_ROOT_MODULES)


def test_workflows_use_product_commands_not_legacy_root_modules():
    workflow_dir = REPO_ROOT / ".github" / "workflows"
    offenders: dict[str, list[str]] = {}

    for workflow in workflow_dir.glob("*.yml"):
        text = workflow.read_text()
        for module in OLD_ROOT_MODULES:
            needle = f"python -m agent_management.{module}"
            if needle in text:
                offenders.setdefault(workflow.name, []).append(needle)

    assert not offenders


def test_legacy_wrappers_are_archived_outside_package():
    old_dir = REPO_ROOT / "old" / "agent_management_wrappers"
    archived = {path.name for path in old_dir.glob("*.py")}
    expected = {f"{module}.py" for module in OLD_ROOT_MODULES}

    assert expected <= archived
