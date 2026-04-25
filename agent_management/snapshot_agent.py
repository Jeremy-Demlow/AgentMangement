"""Rich JSON snapshot of a Cortex Agent for audit and diff.

Captures the agent's full spec (via DESCRIBE AGENT) plus SHOW VERSIONS
metadata. Complements ``agent_management.snapshot_state``:

  snapshot_state  -> lightweight pointer (version + aliases) for rollback
  snapshot_agent  -> rich JSON (full spec + versions + aliases) for audit/diff

IMPORTANT: Cortex Agent Versioning's SQL surface only lets us fetch the spec
of the default version. Per-version and per-alias spec fetches return syntax
errors. If you need the spec of a non-default version, it is immutably stored
in ``VERSION$N`` inside Snowflake — you can compare two agent snapshots
taken at different points in time to see diffs.

Usage::

    from agent_management.snapshot_agent import snapshot_agent, diff_snapshots
    path = snapshot_agent(
        agent_fqn="AM_SKI_RESORT.AGENTS.RESORT_EXECUTIVE",
        env="prod",
    )

CLI::

    python -m agent_management.snapshot_agent capture --env dev --agent AM_SKI_RESORT_DEV.AGENTS.RESORT_EXECUTIVE_DEV
    python -m agent_management.snapshot_agent diff snapshots/a.json snapshots/b.json
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
from agent_management.versioning import get_aliases, list_versions

logger = logging.getLogger(__name__)


def _default_out_dir() -> Path:
    return project_root() / "snapshots"


def _safe_fqn_dir(agent_fqn: str) -> str:
    return agent_fqn.replace(".", "_")


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _describe_agent(conn, agent_fqn: str) -> dict[str, Any]:
    """Return full spec + metadata for the current default version."""
    cursor = conn.cursor()
    cursor.execute(f"DESCRIBE AGENT {agent_fqn}")
    columns = [c[0] for c in cursor.description]
    row = cursor.fetchone()
    desc = dict(zip(columns, row)) if row else {}

    spec_raw = desc.get("agent_spec")
    spec_parsed: Any = None
    if spec_raw:
        try:
            spec_parsed = json.loads(spec_raw) if isinstance(spec_raw, str) else spec_raw
        except json.JSONDecodeError:
            try:
                spec_parsed = yaml.safe_load(spec_raw)
            except Exception:  # noqa: BLE001
                spec_parsed = None

    versions_list = list_versions(conn, agent_fqn)
    aliases = get_aliases(conn, agent_fqn)

    # Merge the default_version_name hint from DESC AGENT if present.
    default_version = desc.get("default_version_name")

    return {
        "agent_fqn": agent_fqn,
        "default_version": default_version,
        "spec": spec_parsed,
        "spec_raw": spec_raw,
        "comment": desc.get("comment"),
        "profile": desc.get("profile"),
        "versions": [v.__dict__ for v in versions_list],
        "aliases": aliases,
    }


def snapshot_agent(
    agent_fqn: str,
    *,
    env: str,
    out_dir: Path | None = None,
    connection=None,
) -> Path:
    """Capture a rich JSON snapshot of the agent's current default version."""
    out_dir = out_dir or _default_out_dir()
    close_after = False
    conn = connection
    if conn is None:
        config = load_env_config(env)
        conn = connect(config)
        close_after = True

    try:
        described = _describe_agent(conn, agent_fqn)
    finally:
        if close_after:
            conn.close()

    payload = {
        "env": env,
        "snapshot_time": datetime.now(timezone.utc).isoformat(),
        **described,
    }

    subdir = out_dir / _safe_fqn_dir(agent_fqn)
    subdir.mkdir(parents=True, exist_ok=True)
    label = described.get("default_version") or "LIVE"
    out_path = subdir / f"{_timestamp()}_{label}.json"
    out_path.write_text(json.dumps(payload, indent=2, default=str))
    logger.info("Wrote snapshot -> %s", out_path)
    return out_path


def load_snapshot(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def diff_snapshots(a: Path | str, b: Path | str) -> str:
    """Return a unified diff of the two snapshots' spec (JSON pretty)."""
    snap_a = load_snapshot(a)
    snap_b = load_snapshot(b)
    a_pretty = json.dumps(snap_a.get("spec") or {}, indent=2, sort_keys=True).splitlines()
    b_pretty = json.dumps(snap_b.get("spec") or {}, indent=2, sort_keys=True).splitlines()
    return "\n".join(
        difflib.unified_diff(
            a_pretty, b_pretty,
            fromfile=str(a),
            tofile=str(b),
            lineterm="",
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Snapshot or diff a Cortex Agent.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    cap = sub.add_parser("capture", help="Capture a snapshot of the current default version.")
    cap.add_argument("--env", required=True)
    cap.add_argument("--agent", required=True, help="Agent FQN.")
    cap.add_argument("--out-dir", type=Path, default=None)

    diff = sub.add_parser("diff", help="Diff two snapshot JSON files.")
    diff.add_argument("a", type=Path)
    diff.add_argument("b", type=Path)

    parser.add_argument("-v", "--verbose", action="count", default=0)
    args = parser.parse_args(argv)
    setup_logging(args.verbose)

    if args.cmd == "diff":
        print(diff_snapshots(args.a, args.b))
        return 0

    snapshot_agent(
        agent_fqn=args.agent,
        env=args.env,
        out_dir=args.out_dir,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
