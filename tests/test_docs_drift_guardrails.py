"""Process guardrails: prevent doc/workflow drift from re-emerging.

Implements REQ-020 acceptance criteria. These tests are intentionally cheap
and run in the default suite so contributors get fast feedback when:

- a removed workflow name (promote-qa.yml, promote-prod.yml, ...) re-enters
  active documentation
- a workflow referenced from active docs does not actually exist on disk
- environments/*.env.yml drifts away from the env keys in project.yml

If a doc is intentionally archival (e.g. a historical conversation log),
add it to ARCHIVAL_DOCS so the scan does not flag it.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

# Active contributor-facing docs. Updates here flow through to scans below.
ACTIVE_DOCS = [
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "README.md",
    REPO_ROOT / "CONTRIBUTING.md",
    REPO_ROOT / "ENVIRONMENT_PARITY.md",
    REPO_ROOT / "tests" / "test_cases.md",
    REPO_ROOT / "tests" / "regression.md",
]

# Docs that are intentionally historical and excluded from drift scans.
# These should ideally be moved to docs/archive/, but until then we exclude
# them explicitly so the scan stays honest.
ARCHIVAL_DOCS = {
    REPO_ROOT / "AgentMangementThread.md",
}

# Workflow file names that have been removed and must NOT reappear in
# active docs.
REMOVED_WORKFLOWS = (
    "promote-qa.yml",
    "promote-prod.yml",
)


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


@pytest.mark.parametrize("doc", [p for p in ACTIVE_DOCS if p not in ARCHIVAL_DOCS])
def test_active_docs_do_not_reference_removed_workflows(doc):
    """REQ-020: active docs must not name workflows that no longer exist."""
    if not doc.exists():
        pytest.skip(f"{doc.name} not present")
    text = _read(doc)
    for removed in REMOVED_WORKFLOWS:
        assert removed not in text, (
            f"{doc.relative_to(REPO_ROOT)} references removed workflow "
            f"{removed!r}. Update the doc or move it to ARCHIVAL_DOCS if it "
            "is intentionally historical."
        )


def _workflow_name_pattern() -> re.Pattern:
    # Match strings like "deploy-dev.yml" / "validate-pr.yml" /
    # "promote-validated-to-production.yml" but NOT bare ".yml".
    return re.compile(r"\b([a-z][a-z0-9_\-]*\.yml)\b")


def test_active_docs_only_reference_existing_workflows():
    """REQ-020: every workflow file name mentioned in active docs must exist
    under .github/workflows/.

    Catches typos like 'depoly-dev.yml' and stale links to removed workflows.
    """
    workflow_dir = REPO_ROOT / ".github" / "workflows"
    existing = {p.name for p in workflow_dir.glob("*.yml")}
    pattern = _workflow_name_pattern()

    missing: dict[str, set[str]] = {}
    for doc in ACTIVE_DOCS:
        if doc in ARCHIVAL_DOCS or not doc.exists():
            continue
        text = _read(doc)
        for match in pattern.findall(text):
            # Skip non-workflow yml files referenced in docs (env configs,
            # manifests, semantic view definitions, eval configs, etc.).
            if any(token in match for token in (
                ".env.yml", "manifest.yml", "project.yml", "dbt_project.yml",
                "_eval.yml", "package.yml", "schema.yml", "profiles.yml",
            )):
                continue
            # Workflow files always live under .github/workflows/. If the
            # match looks workflow-shaped (kebab-case with no env/manifest
            # token) but is missing from disk, flag it.
            if "-" in match and match not in existing:
                missing.setdefault(str(doc.relative_to(REPO_ROOT)), set()).add(match)

    assert not missing, (
        f"Active docs reference workflow files that do not exist: {missing}. "
        f"Existing workflows: {sorted(existing)}"
    )


def test_environments_match_project_yml():
    """REQ-020: project.yml's `environments:` keys must match the files in
    environments/.

    Catches drift like 'project.yml says dev/qa/prod but only dev.env.yml
    and prod.env.yml exist'.
    """
    project_yml = REPO_ROOT / "project.yml"
    env_dir = REPO_ROOT / "environments"
    if not project_yml.exists() or not env_dir.exists():
        pytest.skip("project.yml or environments/ missing")

    project = yaml.safe_load(project_yml.read_text())
    declared = set((project.get("environments") or {}).keys())
    on_disk = {p.stem.replace(".env", "") for p in env_dir.glob("*.env.yml")}

    assert declared == on_disk, (
        f"project.yml environments {sorted(declared)} do not match "
        f"environments/*.env.yml on disk {sorted(on_disk)}"
    )


def test_active_workflows_reference_only_existing_envs():
    """REQ-020: every `environment:` key in workflow YAML must map to a
    GitHub environment we actually use.

    The legal set is: DEV, PROD, production-promote. (production-promote is
    a separate GH environment for the alias-flip approval gate.) Anything
    else likely indicates QA or another removed environment leaking back in.
    """
    legal = {"DEV", "PROD", "production-promote"}
    workflow_dir = REPO_ROOT / ".github" / "workflows"

    bad: dict[str, set[str]] = {}
    for wf in workflow_dir.glob("*.yml"):
        try:
            doc = yaml.safe_load(wf.read_text())
        except yaml.YAMLError:
            # Workflows occasionally include GitHub Actions expression syntax
            # that PyYAML chokes on. Skip — drift is best caught structurally.
            continue
        for _job_name, job in (doc.get("jobs") or {}).items():
            if not isinstance(job, dict):
                continue
            env = job.get("environment")
            if env is None:
                continue
            # YAML may give us a string OR a dict ({name: ..., url: ...}).
            if isinstance(env, dict):
                env = env.get("name")
            if not isinstance(env, str):
                continue
            # Skip GH-Actions expressions like ${{ inputs.environment }} or
            # the `>- ${{ ... }}` folded form that resolves at runtime.
            if "${{" in env:
                continue
            if env in legal:
                continue
            bad.setdefault(wf.name, set()).add(env)

    assert not bad, (
        f"Workflows reference unknown GitHub environments {bad}. "
        f"Legal environments: {sorted(legal)}"
    )
