"""Rollback agents and/or semantic views to a previous snapshot.

Reads local snapshot files (JSON for agents, YAML for SVs) and re-deploys
them using ALTER AGENT or SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML.

Usage:
    python -m agent_management.rollback --env prod --timestamp 20260402_030209
    python -m agent_management.rollback --env prod --timestamp 20260402_030209 --target agents
    python -m agent_management.rollback --env prod --timestamp 20260402_030209 --dry-run

Implements REQ-005: Snapshot and Rollback.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from agent_management import setup_logging
from agent_management.paths import agents_snapshots_dir, sv_snapshots_dir
from agent_management.utils.config import get_agents_schema, get_semantic_schema, load_env_config
from agent_management.utils.snowflake_client import connect

logger = logging.getLogger(__name__)


def find_snapshots(base_dir: Path, env: str, timestamp: str, ext: str) -> list[Path]:
    snap_dir = base_dir / env
    if not snap_dir.exists():
        return []
    return sorted(snap_dir.glob(f"*_{timestamp}.{ext}"))


def rollback_agents(cur, config: dict, timestamp: str, dry_run: bool) -> tuple[int, int]:
    files = find_snapshots(agents_snapshots_dir(), config["environment"], timestamp, "json")
    if not files:
        logger.info("  No agent snapshots found for this timestamp")
        return 0, 0

    success = 0
    failed = 0
    for path in files:
        snapshot = json.loads(path.read_text())
        agent_name = snapshot["name"]
        fqn = snapshot["fqn"]
        spec_raw = snapshot.get("agent_spec")

        if not spec_raw:
            logger.info("  %s — SKIPPED (no agent_spec in snapshot)", agent_name)
            continue

        try:
            spec_json = spec_raw if isinstance(spec_raw, str) else json.dumps(spec_raw)
        except Exception:
            spec_json = str(spec_raw)

        if "$$" in spec_json:
            logger.info("  %s — SKIPPED (spec contains $$)", agent_name)
            continue

        sql = (
            f"ALTER AGENT {fqn}\n"
            f"MODIFY LIVE VERSION SET SPECIFICATION =\n"
            f"$$\n{spec_json}\n$$"
        )

        if dry_run:
            logger.info("  [DRY RUN] %s — would ALTER from %s", agent_name, path.name)
            success += 1
        else:
            logger.info("  %s...", agent_name)
            try:
                cur.execute(sql)
                logger.info("  %s... OK", agent_name)
                success += 1
            except Exception as e:
                logger.error("  %s... FAILED — %s", agent_name, e)
                failed += 1

    return success, failed


def rollback_semantic_views(cur, config: dict, timestamp: str, dry_run: bool) -> tuple[int, int]:
    files = find_snapshots(sv_snapshots_dir(), config["environment"], timestamp, "yaml")
    if not files:
        logger.info("  No SV snapshots found for this timestamp")
        return 0, 0

    schema_fqn = get_semantic_schema(config)
    success = 0
    failed = 0
    for path in files:
        sv_name = path.stem.rsplit("_", 2)[0]
        yaml_content = path.read_text()

        if "$$" in yaml_content:
            logger.info("  %s — SKIPPED (YAML contains $$)", sv_name)
            continue

        if dry_run:
            logger.info("  [DRY RUN] %s — would restore from %s", sv_name, path.name)
            success += 1
        else:
            logger.info("  %s...", sv_name)
            try:
                cur.execute(
                    f"CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML('{schema_fqn}', $${yaml_content}$$, FALSE)"
                )
                logger.info("  %s... OK", sv_name)
                success += 1
            except Exception as e:
                logger.error("  %s... FAILED — %s", sv_name, e)
                failed += 1

    return success, failed


def list_available_timestamps(env: str) -> list[str]:
    timestamps = set()
    for base_dir in (agents_snapshots_dir(), sv_snapshots_dir()):
        snap_dir = base_dir / env
        if snap_dir.exists():
            for f in snap_dir.iterdir():
                parts = f.stem.rsplit("_", 2)
                if len(parts) >= 3:
                    timestamps.add(f"{parts[-2]}_{parts[-1]}")
    return sorted(timestamps, reverse=True)


def main():
    parser = argparse.ArgumentParser(description="Rollback to a previous snapshot")
    parser.add_argument("--env", "-e", help="Environment (dev, qa, prod)")
    parser.add_argument("--timestamp", "-ts", help="Snapshot timestamp (YYYYMMDD_HHMMSS)")
    parser.add_argument("--target", "-t", choices=["agents", "semantic-views", "all"], default="all")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Show what would be restored")
    parser.add_argument("--list", action="store_true", help="List available snapshots")
    args = parser.parse_args()

    setup_logging(1)

    config = load_env_config(args.env)

    if args.list:
        ts_list = list_available_timestamps(config["environment"])
        logger.info("Available snapshots for %s:", config['environment'])
        for ts in ts_list:
            logger.info("  %s", ts)
        sys.exit(0)

    if not args.timestamp:
        logger.error("ERROR: --timestamp is required (use --list to see available)")
        sys.exit(1)

    logger.info("Environment: %s", config['environment'])
    logger.info("Timestamp: %s", args.timestamp)
    logger.info("Target: %s", args.target)
    logger.info("Mode: %s", 'DRY RUN' if args.dry_run else 'LIVE')
    logger.info("=" * 60)

    conn = connect(config)
    cur = conn.cursor()

    total_success = 0
    total_failed = 0

    if args.target in ("agents", "all"):
        logger.info("\nAgents:")
        s, f = rollback_agents(cur, config, args.timestamp, args.dry_run)
        total_success += s
        total_failed += f

    if args.target in ("semantic-views", "all"):
        logger.info("\nSemantic Views:")
        s, f = rollback_semantic_views(cur, config, args.timestamp, args.dry_run)
        total_success += s
        total_failed += f

    logger.info("\n%s", "=" * 60)
    logger.info("Restored: %d  Failed: %d  Environment: %s", total_success, total_failed, config['environment'])

    cur.close()
    conn.close()
    sys.exit(1 if total_failed > 0 else 0)


if __name__ == "__main__":
    main()
