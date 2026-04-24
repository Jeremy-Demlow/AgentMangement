"""Capture a pre-deploy pointer snapshot for Cortex Agents.

Versioning-era snapshots are lightweight: the rollback target lives in
Snowflake as VERSION$N, so the snapshot only needs to record which version
each alias pointed at before deploy started. Full-spec captures for audit
live in ``agent_management.snapshot_agent`` (separate module).

Pointer shape::

    {
      "agent_fqn": "...",
      "env": "prod",
      "snapshot_time": "2026-04-24T…",
      "version_before": "VERSION$7",
      "alias_before": {"validated": "VERSION$7", "production": "VERSION$6"},
      "all_versions": ["VERSION$1", …, "VERSION$7"]
    }

Usage::

    python -m agent_management.snapshot_state --env prod
    python -m agent_management.snapshot_state --env prod --agent RESORT_EXECUTIVE

Implements REQ-005: Snapshot and Rollback (pointer-only).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_management import setup_logging
from agent_management.paths import project_root
from agent_management.utils.config import (
    get_agent_fqn,
    get_all_configured_agents,
    get_agents_schema,
    load_env_config,
)
from agent_management.utils.snowflake_client import connect
from agent_management.versioning import get_aliases, list_versions

logger = logging.getLogger(__name__)


@dataclass
class SnapshotPointer:
    agent_fqn: str
    env: str
    snapshot_time: str
    version_before: str | None
    alias_before: dict[str, str]
    all_versions: list[str]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _snapshot_dir(env: str, agent_fqn: str) -> Path:
    safe = agent_fqn.replace(".", "_")
    return project_root() / ".snowflake" / "ci" / "snapshots" / env / safe


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def snapshot_state(
    agent_fqn: str,
    *,
    env: str,
    out_path: Path | None = None,
    connection=None,
) -> SnapshotPointer:
    """Capture the current version + alias state for ``agent_fqn``."""
    config = load_env_config(env)
    close_after = False
    conn = connection
    if conn is None:
        conn = connect(config, schema=config["deployment"]["agents_schema"])
        close_after = True

    try:
        try:
            versions = list_versions(conn, agent_fqn)
        except Exception as exc:  # noqa: BLE001
            # First-time deploys may have no SHOW VERSIONS history yet.
            logger.info("snapshot_state: no versions yet on %s (%s)", agent_fqn, exc)
            versions = []
        try:
            aliases = get_aliases(conn, agent_fqn)
        except Exception as exc:  # noqa: BLE001
            logger.info("snapshot_state: no aliases yet on %s (%s)", agent_fqn, exc)
            aliases = {}
    finally:
        if close_after:
            conn.close()

    pointer = SnapshotPointer(
        agent_fqn=agent_fqn,
        env=env,
        snapshot_time=datetime.now(timezone.utc).isoformat(),
        version_before=versions[-1].name if versions else None,
        alias_before=aliases,
        all_versions=[v.name for v in versions],
    )

    target = out_path or (_snapshot_dir(env, agent_fqn) / f"{_timestamp()}.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(pointer.as_dict(), indent=2))
    logger.info("Wrote snapshot pointer -> %s", target)
    return pointer


def _agents_for_env(config: dict, explicit: str | None) -> list[str]:
    if explicit:
        return [explicit if "." in explicit else get_agent_fqn(config, explicit)]
    return [get_agent_fqn(config, name) for name in get_all_configured_agents()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture pre-deploy snapshot pointers.")
    parser.add_argument("--env", required=True, choices=["dev", "prod"])
    parser.add_argument("--agent", help="Short name or FQN. If omitted, all configured agents.")
    parser.add_argument("-v", "--verbose", action="count", default=1)
    args = parser.parse_args(argv)
    setup_logging(args.verbose)

    config = load_env_config(args.env)
    agents = _agents_for_env(config, args.agent)

    logger.info("Snapshotting %d agent(s) in env=%s", len(agents), args.env)
    failed = 0
    for fqn in agents:
        try:
            snapshot_state(fqn, env=args.env)
        except Exception as exc:  # noqa: BLE001
            logger.error("snapshot FAILED for %s — %s", fqn, exc)
            failed += 1
    return 1 if failed > 0 else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
