"""Capture pre-deploy snapshots of agents and semantic views.

Saves current state (DESCRIBE AGENT + SYSTEM$READ_YAML_FROM_SEMANTIC_VIEW)
to local files and optionally to a Snowflake CI_CD_SNAPSHOTS table.

Usage:
    python -m agent_management.snapshot_state --env dev
    python -m agent_management.snapshot_state --env dev --target agents
    python -m agent_management.snapshot_state --env dev --target semantic-views

Implements REQ-005: Snapshot and Rollback.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from agent_management import setup_logging
from agent_management.paths import agents_snapshots_dir, sv_snapshots_dir
from agent_management.utils.config import get_agents_schema, get_semantic_schema, load_env_config
from agent_management.utils.snowflake_client import connect

logger = logging.getLogger(__name__)


def snapshot_agents(cur, config: dict, timestamp: str) -> list[dict]:
    schema_fqn = get_agents_schema(config)
    cur.execute(f"SHOW AGENTS IN SCHEMA {schema_fqn}")
    agents = cur.fetchall()
    snapshots = []

    for row in agents:
        agent_name = row[1]
        fqn = f"{schema_fqn}.{agent_name}"
        try:
            cur.execute(f"DESCRIBE AGENT {fqn}")
            columns = [col[0].lower() for col in cur.description]
            desc_row = cur.fetchone()
            desc_data = dict(zip(columns, desc_row)) if desc_row else {}

            snapshot = {
                "object_type": "AGENT",
                "name": agent_name,
                "fqn": fqn,
                "environment": config["environment"],
                "timestamp": timestamp,
                "agent_spec": desc_data.get("agent_spec"),
                "comment": desc_data.get("comment"),
                "profile": desc_data.get("profile"),
            }
            snapshots.append(snapshot)

            out_dir = agents_snapshots_dir() / config["environment"]
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / f"{agent_name}_{timestamp}.json"
            out_file.write_text(json.dumps(snapshot, indent=2) + "\n")
            logger.info("  %s -> %s", agent_name, out_file.name)
        except Exception as e:
            logger.error("  %s — FAILED: %s", agent_name, e)

    return snapshots


def snapshot_semantic_views(cur, config: dict, timestamp: str) -> list[dict]:
    schema_fqn = get_semantic_schema(config)
    cur.execute(f"SHOW SEMANTIC VIEWS IN SCHEMA {schema_fqn}")
    views = cur.fetchall()
    snapshots = []

    for row in views:
        view_name = row[1]
        fqn = f"{schema_fqn}.{view_name}"
        try:
            cur.execute(f"SELECT SYSTEM$READ_YAML_FROM_SEMANTIC_VIEW('{fqn}')")
            result = cur.fetchone()
            yaml_content = result[0] if result else ""

            snapshot = {
                "object_type": "SEMANTIC_VIEW",
                "name": view_name,
                "fqn": fqn,
                "environment": config["environment"],
                "timestamp": timestamp,
                "yaml": yaml_content,
            }
            snapshots.append(snapshot)

            out_dir = sv_snapshots_dir() / config["environment"]
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / f"{view_name}_{timestamp}.yaml"
            out_file.write_text(yaml_content)
            logger.info("  %s -> %s", view_name, out_file.name)
        except Exception as e:
            logger.error("  %s — FAILED: %s", view_name, e)

    return snapshots


def save_to_snowflake(cur, config: dict, snapshots: list[dict]) -> None:
    schema_fqn = get_agents_schema(config)
    table = f"{schema_fqn}.CI_CD_SNAPSHOTS"

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {table} (
            SNAPSHOT_ID VARCHAR DEFAULT UUID_STRING(),
            OBJECT_TYPE VARCHAR,
            OBJECT_NAME VARCHAR,
            OBJECT_FQN VARCHAR,
            ENVIRONMENT VARCHAR,
            SNAPSHOT_TIMESTAMP TIMESTAMP_NTZ,
            CONTENT VARIANT,
            PRIMARY KEY (SNAPSHOT_ID)
        )
    """)

    for s in snapshots:
        content = json.dumps(s)
        cur.execute(
            f"INSERT INTO {table} (OBJECT_TYPE, OBJECT_NAME, OBJECT_FQN, ENVIRONMENT, SNAPSHOT_TIMESTAMP, CONTENT)"
            f" SELECT %s, %s, %s, %s, TO_TIMESTAMP(%s, 'YYYYMMDD_HH24MISS'), PARSE_JSON(%s)",
            (s["object_type"], s["name"], s["fqn"], s["environment"], s["timestamp"], content),
        )


def main():
    parser = argparse.ArgumentParser(description="Snapshot current agent/SV state")
    parser.add_argument("--env", "-e", help="Environment (dev, qa, prod)")
    parser.add_argument("--target", "-t", choices=["agents", "semantic-views", "all"], default="all")
    parser.add_argument("--no-remote", action="store_true", help="Skip saving to Snowflake table")
    args = parser.parse_args()

    setup_logging(1)

    config = load_env_config(args.env)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    logger.info("Environment: %s", config['environment'])
    logger.info("Timestamp: %s", timestamp)
    logger.info("Target: %s", args.target)
    logger.info("=" * 60)

    conn = connect(config)
    cur = conn.cursor()
    all_snapshots = []

    if args.target in ("agents", "all"):
        logger.info("\nAgents:")
        all_snapshots.extend(snapshot_agents(cur, config, timestamp))

    if args.target in ("semantic-views", "all"):
        logger.info("\nSemantic Views:")
        all_snapshots.extend(snapshot_semantic_views(cur, config, timestamp))

    if not args.no_remote and all_snapshots:
        logger.info("\nSaving to Snowflake CI_CD_SNAPSHOTS table...")
        save_to_snowflake(cur, config, all_snapshots)
        logger.info("  %d snapshot(s) saved", len(all_snapshots))

    logger.info("\n%s", "=" * 60)
    logger.info("Snapshots: %d  Environment: %s", len(all_snapshots), config['environment'])

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
