"""Public Cortex Agent lifecycle APIs."""
from __future__ import annotations

from agent_management.agents.deploy import build_spec, deploy_agent, resolve_agent_identity
from agent_management.agents.rollback import rollback_agent
from agent_management.agents.smoke import run_smoke_test
from agent_management.agents.snapshot import diff_snapshots, load_snapshot, snapshot_agent
from agent_management.agents.versioning import (
    add_live_from_last,
    commit_live,
    commit_version,
    get_aliases,
    has_live_draft,
    list_versions,
    modify_live_spec,
    promote_alias,
    set_alias,
    version_exists,
)

__all__ = [
    "add_live_from_last",
    "build_spec",
    "commit_live",
    "commit_version",
    "deploy_agent",
    "diff_snapshots",
    "get_aliases",
    "has_live_draft",
    "list_versions",
    "load_snapshot",
    "modify_live_spec",
    "promote_alias",
    "resolve_agent_identity",
    "rollback_agent",
    "run_smoke_test",
    "set_alias",
    "snapshot_agent",
    "version_exists",
]
