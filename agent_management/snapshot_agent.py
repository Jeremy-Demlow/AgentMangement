"""Rich JSON snapshots of a deployed Cortex Agent for audit and diff.

Distinct from ``agent_management.snapshot_state`` — that module captures a
lightweight pointer (version + aliases) that is the input to rollback. This
module writes a full spec snapshot intended for human review and historical
comparison.

Replaces the ad-hoc snapshots that used to live under ``agent_optimization/``.

Usage::

    from agent_management.snapshot_agent import snapshot_agent, diff_snapshots
    path = snapshot_agent(
        agent_fqn="AM_SKI_RESORT.AGENTS.RESORT_EXECUTIVE",
        env="prod",
        alias="production",
    )

CLI::

    python -m agent_management.snapshot_agent --env prod --agent RESORT_EXECUTIVE --alias production
    python -m agent_management.snapshot_agent --diff snapshots/a.json snapshots/b.json
"""
from __future__ import annotations

import argparse
import difflib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from agent_management import setup_logging
from agent_management.paths import project_root
from agent_management.utils.config import load_env_config
from agent_management.utils.snowflake_client import connect

logger = logging.getLogger(__name__)


def _default_out_dir() -> Path:
    # snapshots/ at repo root; gitignored.
    return project_root() / "snapshots"


def _safe_fqn_dir(agent_fqn: str) -> str:
    return agent_fqn.replace(".", "_").replace("!", "_")


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _describe_agent(conn, agent_fqn: str, *, version: str | None, alias: str | None) -> dict[str, Any]:
    """Return the agent's rendered spec plus metadata for the given version/alias."""
    cursor = conn.cursor()
    selector = agent_fqn
    if version:
        selector = f"{agent_fqn}!{version}"
    elif alias:
        selector = f"{agent_fqn}!{alias}"

    cursor.execute(f"DESCRIBE AGENT {selector}")
    desc_rows = cursor.fetchall()
    columns = [c[0] for c in cursor.description]
    desc = [dict(zip(columns, row)) for row in desc_rows]

    spec_yaml = None
    for row in desc:
        # The DESCRIBE output lists a 'specification' row whose value is YAML.
        if str(row.get("property", "")).lower() in {"specification", "spec"}:
            spec_yaml = row.get("value")
            break

    spec_parsed: dict[str, Any] | None = None
    if spec_yaml:
        try:
            spec_parsed = yaml.safe_load(spec_yaml)
        except yaml.YAMLError:
            spec_parsed = None

    # Alias + version list (best-effort — the exact DDL for the Private Preview
    # can vary; callers handle the exception gracefully).
    aliases: dict[str, str] = {}
    versions: list[str] = []
    try:
        cursor.execute(f"SHOW VERSIONS ON AGENT {agent_fqn}")
        for row in cursor.fetchall():
            cols = [c[0].lower() for c in cursor.description]
            record = dict(zip(cols, row))
            versions.append(str(record.get("name") or record.get("version")))
    except Exception as exc:  # noqa: BLE001
        logger.debug("SHOW VERSIONS unavailable: %s", exc)
    try:
        cursor.execute(f"SHOW ALIASES ON AGENT {agent_fqn}")
        for row in cursor.fetchall():
            cols = [c[0].lower() for c in cursor.description]
            record = dict(zip(cols, row))
            alias_name = record.get("alias") or record.get("name")
            version_ref = record.get("version") or record.get("target")
            if alias_name and version_ref:
                aliases[str(alias_name)] = str(version_ref)
    except Exception as exc:  # noqa: BLE001
        logger.debug("SHOW ALIASES unavailable: %s", exc)

    return {
        "selector": selector,
        "spec_yaml": spec_yaml,
        "spec": spec_parsed,
        "describe": desc,
        "aliases": aliases,
        "versions": versions,
    }


def snapshot_agent(
    agent_fqn: str,
    *,
    env: str,
    version: str | None = None,
    alias: str | None = None,
    out_dir: Path | None = None,
    connection=None,
) -> Path:
    """Capture a rich JSON snapshot of an agent and return the file path."""
    out_dir = out_dir or _default_out_dir()
    close_after = False
    conn = connection
    if conn is None:
        config = load_env_config(env)
        conn = connect(config)
        close_after = True

    try:
        described = _describe_agent(conn, agent_fqn, version=version, alias=alias)
    finally:
        if close_after:
            conn.close()

    payload = {
        "agent_fqn": agent_fqn,
        "env": env,
        "snapshot_time": datetime.now(timezone.utc).isoformat(),
        "requested": {"version": version, "alias": alias},
        **described,
    }

    subdir = out_dir / _safe_fqn_dir(agent_fqn)
    subdir.mkdir(parents=True, exist_ok=True)
    label = version or alias or "LIVE"
    out_path = subdir / f"{_timestamp()}_{label}.json"
    out_path.write_text(json.dumps(payload, indent=2, default=str))
    logger.info("Wrote snapshot -> %s", out_path)
    return out_path


def load_snapshot(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def diff_snapshots(a: Path | str, b: Path | str) -> str:
    """Return a unified diff of two snapshot specs (spec_yaml field)."""
    snap_a = load_snapshot(a)
    snap_b = load_snapshot(b)
    a_yaml = (snap_a.get("spec_yaml") or "").splitlines()
    b_yaml = (snap_b.get("spec_yaml") or "").splitlines()
    return "\n".join(
        difflib.unified_diff(
            a_yaml,
            b_yaml,
            fromfile=str(a),
            tofile=str(b),
            lineterm="",
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Snapshot or diff a Cortex Agent.")
    sub = parser.add_subparsers(dest="cmd")

    cap = sub.add_parser("capture", help="Capture a snapshot (default).")
    cap.add_argument("--env", required=True)
    cap.add_argument("--agent", required=True, help="Agent FQN.")
    cap.add_argument("--version", help="Explicit VERSION$N.")
    cap.add_argument("--alias", help="Alias (validated, production, latest).")
    cap.add_argument("--out-dir", type=Path, default=None)

    diff = sub.add_parser("diff", help="Diff two snapshot JSON files.")
    diff.add_argument("a", type=Path)
    diff.add_argument("b", type=Path)

    parser.add_argument("-v", "--verbose", action="count", default=0)
    # legacy invocation: allow `--env ... --agent ...` at top level
    parser.add_argument("--env", help=argparse.SUPPRESS)
    parser.add_argument("--agent", help=argparse.SUPPRESS)
    parser.add_argument("--version", dest="top_version", help=argparse.SUPPRESS)
    parser.add_argument("--alias", help=argparse.SUPPRESS)
    parser.add_argument("--out-dir", dest="top_out_dir", type=Path, help=argparse.SUPPRESS)

    args = parser.parse_args(argv)
    setup_logging(args.verbose)

    if args.cmd == "diff":
        print(diff_snapshots(args.a, args.b))
        return 0

    # Either explicit "capture" subcommand or legacy top-level flags
    env = getattr(args, "env", None)
    agent = getattr(args, "agent", None)
    if env is None or agent is None:
        parser.error("--env and --agent are required (or use a subcommand).")

    snapshot_agent(
        agent_fqn=agent,
        env=env,
        version=args.version if args.cmd == "capture" else args.top_version,
        alias=args.alias,
        out_dir=args.out_dir if args.cmd == "capture" else args.top_out_dir,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
