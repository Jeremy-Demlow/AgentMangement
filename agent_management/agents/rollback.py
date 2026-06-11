"""Rollback a Cortex Agent by reassigning an alias to a prior version.

With Cortex Agent Versioning, rollback becomes a single DDL statement::

    ALTER AGENT <fqn> MODIFY VERSION <target_version> SET ALIAS = <alias>

The target version is read from the most recent snapshot pointer (see
agent_management.agents.snapshot_state). There is no fallback to spec re-apply —
if the SQL fails, the operator fixes the cause and re-runs.

Usage::

    agent-mgmt-rollback --env prod --agent RESORT_EXECUTIVE --alias production
    agent-mgmt-rollback --env prod --agent RESORT_EXECUTIVE --alias production --to VERSION$5

Implements REQ-005: Snapshot and Rollback (versioning era).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from agent_management import setup_logging
from agent_management.paths import project_root
from agent_management.utils.config import get_agent_fqn, load_env_config
from agent_management.utils.snowflake_client import connect
from agent_management.agents.versioning import (
    get_aliases,
    set_alias,
    version_exists,
)
from agent_management.agents.version_log import discover_identity, record_deploy

logger = logging.getLogger(__name__)


@dataclass
class RollbackResult:
    agent_fqn: str
    env: str
    alias: str
    target_version: str
    previous_version: str | None
    snapshot_path: Path | None


def _snapshot_dir(env: str, agent_fqn: str) -> Path:
    safe = agent_fqn.replace(".", "_")
    return project_root() / ".snowflake" / "ci" / "snapshots" / env / safe


def _latest_snapshot(env: str, agent_fqn: str) -> Path | None:
    """Return the most recent snapshot pointer file for (env, agent)."""
    d = _snapshot_dir(env, agent_fqn)
    if not d.exists():
        return None
    files = sorted(d.glob("*.json"))
    return files[-1] if files else None


def _resolve_target_from_snapshot(
    snapshot_path: Path,
    *,
    alias: str,
) -> str:
    payload = json.loads(snapshot_path.read_text())
    alias_before = payload.get("alias_before") or {}
    target = alias_before.get(alias)
    if not target:
        target = payload.get("version_before")
    if not target:
        raise RuntimeError(
            f"Snapshot {snapshot_path} has no version_before or "
            f"alias_before[{alias!r}]; cannot determine rollback target."
        )
    return str(target)


def rollback_agent(
    agent_fqn: str,
    *,
    env: str,
    alias: str,
    target_version: str | None = None,
    snapshot_path: Path | None = None,
    connection=None,
) -> RollbackResult:
    """Roll back the given alias to a prior version on the agent.

    Args:
        agent_fqn: Agent FQN.
        env: Environment name (dev/prod).
        alias: Alias to move (e.g. ``production``).
        target_version: Explicit ``VERSION$N`` to reassign to. If omitted the
            library reads the most recent snapshot pointer and uses
            ``alias_before[alias]``.
        snapshot_path: Explicit snapshot file; defaults to the latest for
            (env, agent).
        connection: Optional pre-opened Snowflake connection (tests).

    Raises:
        RuntimeError when target_version cannot be resolved or does not exist,
        or when the alias is already at target (no-op guard).
    """
    config = load_env_config(env)
    close_after = False
    conn = connection
    if conn is None:
        conn = connect(config, schema=config["deployment"]["agents_schema"])
        close_after = True

    try:
        snap_path = snapshot_path
        if target_version is None:
            snap_path = snap_path or _latest_snapshot(env, agent_fqn)
            if snap_path is None:
                raise RuntimeError(
                    f"No snapshot pointer found for {env}/{agent_fqn}; "
                    "pass --to VERSION$N explicitly."
                )
            target_version = _resolve_target_from_snapshot(snap_path, alias=alias)

        if not version_exists(conn, agent_fqn, target_version):
            raise RuntimeError(
                f"Version {target_version} not found on {agent_fqn}; cannot rollback."
            )

        current = get_aliases(conn, agent_fqn)
        # Snowflake stores aliases uppercase; normalize lookup.
        previous_version = current.get(alias.upper())
        if previous_version and previous_version.upper() == target_version.upper():
            raise RuntimeError(
                f"Alias {alias!r} is already at {target_version}; nothing to do."
            )

        set_alias(conn, agent_fqn, target_version, alias)
        logger.info(
            "rollback OK: %s alias=%s %s -> %s",
            agent_fqn, alias, previous_version or "<unset>", target_version,
        )

        # Best-effort audit log append so the rollback is visible in
        # `agent_management.agents.versioning log`.
        try:
            identity = discover_identity(env)
            record_deploy(
                conn,
                database=config["deployment"]["database"],
                schema=config["deployment"]["agents_schema"],
                agent_fqn=agent_fqn,
                version_name=target_version,
                alias_set=alias,
                identity=identity,
                first_deploy=False,
                version_before=previous_version,
                spec_summary=f"ROLLBACK: {alias} -> {target_version}",
                extra={"event_type": "rollback"},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("rollback audit append failed (non-fatal): %s", exc)

        return RollbackResult(
            agent_fqn=agent_fqn,
            env=env,
            alias=alias,
            target_version=target_version,
            previous_version=previous_version,
            snapshot_path=snap_path,
        )
    finally:
        if close_after:
            conn.close()


def _resolve_fqn(config: dict, agent_arg: str) -> str:
    if "." in agent_arg:
        return agent_arg
    return get_agent_fqn(config, agent_arg)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rollback a Cortex Agent via alias reassignment.")
    parser.add_argument("--env", required=True, choices=["dev", "prod"])
    parser.add_argument("--agent", required=True, help="Agent FQN or short name (resort_executive).")
    parser.add_argument("--alias", required=True, help="Alias to move back (validated, production, latest).")
    parser.add_argument("--to", dest="target_version", help="Explicit VERSION$N target.")
    parser.add_argument("--snapshot", type=Path, help="Explicit snapshot pointer file.")
    parser.add_argument("-v", "--verbose", action="count", default=1)
    args = parser.parse_args(argv)
    setup_logging(args.verbose)

    config = load_env_config(args.env)
    fqn = _resolve_fqn(config, args.agent)
    try:
        result = rollback_agent(
            agent_fqn=fqn,
            env=args.env,
            alias=args.alias,
            target_version=args.target_version,
            snapshot_path=args.snapshot,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("rollback FAILED: %s", exc)
        return 1

    print(json.dumps(result.__dict__, default=str, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
