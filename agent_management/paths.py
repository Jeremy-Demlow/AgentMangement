"""Centralized project resource path resolution.

All modules resolve resource directories through this module
instead of computing paths relative to __file__.

The project root is discovered by searching upward for project.yml.
Can be overridden via AGENT_MGMT_PROJECT_ROOT, or inferred from
AGENT_MGMT_PROJECT_CONFIG, for pip-install scenarios where project config lives
outside the package location.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def project_root() -> Path:
    override = os.environ.get("AGENT_MGMT_PROJECT_ROOT")
    if override:
        root = Path(override).resolve()
        if root.is_dir():
            return root
        raise FileNotFoundError(
            f"AGENT_MGMT_PROJECT_ROOT={override} is not a valid directory"
        )

    config_override = os.environ.get("AGENT_MGMT_PROJECT_CONFIG")
    if config_override:
        config_path = Path(config_override).expanduser().resolve()
        if config_path.is_file():
            return config_path.parent
        raise FileNotFoundError(
            f"AGENT_MGMT_PROJECT_CONFIG={config_override} is not a valid file"
        )

    candidate = Path(__file__).resolve().parent.parent
    for _ in range(5):
        if (candidate / "project.yml").exists():
            return candidate
        candidate = candidate.parent

    raise FileNotFoundError(
        "Cannot find project root (no project.yml found). "
        "Set AGENT_MGMT_PROJECT_ROOT or AGENT_MGMT_PROJECT_CONFIG."
    )


def specs_dir() -> Path:
    return project_root() / "agents" / "specs"


def generated_dir() -> Path:
    return project_root() / "agents" / "generated"


def sv_definitions_dir() -> Path:
    return project_root() / "semantic-views" / "definitions"


def agents_snapshots_dir() -> Path:
    return project_root() / "agents" / "snapshots"


def sv_snapshots_dir() -> Path:
    return project_root() / "semantic-views" / "snapshots"


def sv_verified_queries_dir() -> Path:
    return project_root() / "semantic-views" / "verified_queries"


def eval_dir() -> Path:
    return project_root() / "agent-evaluation"


def environments_dir() -> Path:
    override = os.environ.get("AGENT_MGMT_ENVIRONMENTS_DIR")
    if override:
        return Path(override).expanduser().resolve()
    env_config = os.environ.get("AGENT_MGMT_ENV_CONFIG")
    if env_config:
        return Path(env_config).expanduser().resolve().parent
    return project_root() / "environments"


def project_config_path() -> Path:
    override = os.environ.get("AGENT_MGMT_PROJECT_CONFIG")
    if override:
        return Path(override).expanduser().resolve()
    return project_root() / "project.yml"
