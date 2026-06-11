"""Package layout guardrails.

The product package should expose domain packages, not a flat pile of CLI
wrappers. Legacy wrappers may exist locally under old/, but they must not ship
inside the installable agent_management package.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPO_ROOT / "agent_management"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
COMPOSITE_ACTION = REPO_ROOT / ".github" / "actions" / "snowflake-setup" / "action.yml"

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


def test_workflow_files_use_product_commands_not_legacy_root_modules():
    workflow_paths = list((REPO_ROOT / ".github" / "workflows").glob("*.yml"))
    workflow_paths.extend((REPO_ROOT / ".github" / "scripts").glob("*.sh"))
    workflow_paths.extend([
        REPO_ROOT / "Makefile",
        REPO_ROOT / "README.md",
        REPO_ROOT / "CONTRIBUTING.md",
        REPO_ROOT / "ENVIRONMENT_PARITY.md",
        REPO_ROOT / "agent-evaluation" / "CONTRIBUTING.md",
        REPO_ROOT / "agents" / "CONTRIBUTING.md",
        REPO_ROOT / "semantic-views" / "CONTRIBUTING.md",
        REPO_ROOT / "environments" / "CONTRIBUTING.md",
    ])
    offenders: dict[str, list[str]] = {}

    for workflow in workflow_paths:
        text = workflow.read_text()
        for module in OLD_ROOT_MODULES:
            for needle in (
                f"python -m agent_management.{module}",
                f"agent_management.{module}",
            ):
                if needle in text:
                    offenders.setdefault(workflow.name, []).append(needle)

    assert not offenders


def test_old_archive_is_not_tracked_package_content():
    gitignore = (REPO_ROOT / ".gitignore").read_text()

    assert "/old/" in gitignore


def test_composite_action_installs_the_package():
    """The shared snowflake-setup action must install the package so the
    agent-mgmt-* console scripts land on PATH. Without this, every workflow
    step that calls an agent-mgmt-* command fails with "command not found"."""
    text = COMPOSITE_ACTION.read_text()

    assert ("pip install ." in text) or ("pip install -e" in text)


def _job_step_text(job: dict) -> str:
    return yaml.safe_dump(job.get("steps", []) or [])


def test_every_agent_mgmt_job_installs_the_package():
    """Any workflow job that invokes an agent-mgmt-* command must either use
    the snowflake-setup composite action (which installs the package) or run
    its own `pip install .` / `pip install -e`. This prevents the
    console-script regression where jobs call commands that are never
    installed."""
    offenders: list[str] = []

    for workflow in sorted(WORKFLOWS_DIR.glob("*.yml")):
        doc = yaml.safe_load(workflow.read_text()) or {}
        for job_name, job in (doc.get("jobs") or {}).items():
            steps_text = _job_step_text(job)
            if "agent-mgmt-" not in steps_text:
                continue
            uses_setup = "snowflake-setup" in steps_text
            installs_pkg = ("pip install ." in steps_text) or ("pip install -e" in steps_text)
            if not (uses_setup or installs_pkg):
                offenders.append(f"{workflow.name}::{job_name}")

    assert not offenders, (
        "Jobs call agent-mgmt-* commands without installing the package "
        f"(add snowflake-setup or `pip install .`): {offenders}"
    )
