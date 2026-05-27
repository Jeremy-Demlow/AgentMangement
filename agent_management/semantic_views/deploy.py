"""Deploy semantic view YAMLs to Snowflake.

Supports two modes controlled by semantic_views.source in env config:

  dbt  — Semantic views are created by dbt run. This script only verifies
         they exist in the target schema. No YAML files needed.
  yaml — Renders Jinja2 templates with environment config, then deploys via
         SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML.

Usage:
    python -m agent_management.deploy_semantic_views --env dev
    python -m agent_management.deploy_semantic_views --env dev --view sem_revenue
    python -m agent_management.deploy_semantic_views --env dev --dry-run

Implements REQ-002: Semantic View CI/CD Pipeline.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from agent_management import setup_logging
from agent_management.paths import sv_definitions_dir
from agent_management.render_template import render_file
from agent_management.utils.config import get_semantic_schema, get_sv_source, load_env_config
from agent_management.utils.snowflake_client import connect

logger = logging.getLogger(__name__)


def find_sv_files(view: str | None) -> list[Path]:
    if view:
        path = sv_definitions_dir() / f"{view}.yml"
        if not path.exists():
            path = sv_definitions_dir() / f"{view}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Semantic view YAML not found: {view}")
        return [path]
    files = sorted(sv_definitions_dir().glob("sem_*.y*ml"))
    if not files:
        logger.warning("No semantic view YAMLs found in %s", sv_definitions_dir())
        sys.exit(0)
    return files


def deploy_one(cur, schema_fqn: str, yaml_content: str, name: str, dry_run: bool) -> bool:
    if "$$" in yaml_content:
        logger.info("  %s... SKIPPED — YAML contains '$$'", name)
        return False

    if dry_run:
        logger.info("  [DRY RUN] %s — validating...", name)
        try:
            cur.execute(
                f"CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML('{schema_fqn}', $${yaml_content}$$, TRUE)"
            )
            result = cur.fetchone()
            logger.info("  %s... VALID — %s", name, result[0] if result else 'ok')
            return True
        except Exception as e:
            logger.error("  %s... INVALID — %s", name, e)
            return False

    logger.info("  Deploying %s...", name)
    try:
        cur.execute(
            f"CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML('{schema_fqn}', $${yaml_content}$$, FALSE)"
        )
        result = cur.fetchone()
        logger.info("  %s... OK — %s", name, result[0] if result else 'deployed')
        return True
    except Exception as e:
        logger.error("  %s... FAILED — %s", name, e)
        return False


def verify_dbt_views(cur, schema_fqn: str, dry_run: bool) -> tuple[int, int]:
    action = "DRY RUN verify" if dry_run else "Verify"
    logger.info("[dbt mode] %sing semantic views exist in %s...", action, schema_fqn)
    try:
        cur.execute(f"SHOW SEMANTIC VIEWS IN SCHEMA {schema_fqn}")
        rows = cur.fetchall()
    except Exception as e:
        logger.error("Failed to list semantic views in %s: %s", schema_fqn, e)
        return 0, 1

    if not rows:
        logger.error("No semantic views found in %s — dbt may not have created them yet", schema_fqn)
        return 0, 1

    logger.info("Found %d semantic view(s) in %s:", len(rows), schema_fqn)
    for row in rows:
        logger.info("  ✓ %s", row[1])
    return len(rows), 0


def run_yaml_path(config: dict, schema_fqn: str, view: str | None, dry_run: bool) -> int:
    sv_files = find_sv_files(view)
    logger.info("Views: %d", len(sv_files))
    logger.info("=" * 60)

    conn = connect(config, schema=config["deployment"]["semantic_schema"])
    cur = conn.cursor()

    success = 0
    failed = 0
    for path in sv_files:
        name = path.stem
        rendered = render_file(path, config)
        if deploy_one(cur, schema_fqn, rendered, name, dry_run):
            success += 1
        else:
            failed += 1

    logger.info("\n%s", "=" * 60)
    action = "Validated" if dry_run else "Deployed"
    logger.info("%s: %d  Failed: %d  Environment: %s", action, success, failed, config['environment'])

    if not dry_run:
        cur.execute(f"SHOW SEMANTIC VIEWS IN SCHEMA {schema_fqn}")
        rows = cur.fetchall()
        logger.info("\nSemantic views in %s: %d", schema_fqn, len(rows))
        for row in rows:
            logger.info("  - %s", row[1])

    cur.close()
    conn.close()
    return 1 if failed > 0 else 0


def run_dbt_path(config: dict, schema_fqn: str, dry_run: bool) -> int:
    logger.info("=" * 60)
    conn = connect(config, schema=config["deployment"]["semantic_schema"])
    cur = conn.cursor()

    found, failed = verify_dbt_views(cur, schema_fqn, dry_run)

    logger.info("\n%s", "=" * 60)
    action = "Verified" if dry_run else "Verified"
    logger.info("%s: %d  Failed: %d  Environment: %s", action, found, failed, config['environment'])

    cur.close()
    conn.close()
    return 1 if failed > 0 else 0


def main():
    parser = argparse.ArgumentParser(description="Deploy semantic views from YAML")
    parser.add_argument("--env", "-e", help="Environment (dev, qa, prod)")
    parser.add_argument("--view", "-v", help="Deploy single view by name (yaml mode only)")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Validate only, no deploy")
    args = parser.parse_args()

    setup_logging(1)

    config = load_env_config(args.env)
    schema_fqn = get_semantic_schema(config)
    source = get_sv_source(config)

    logger.info("Environment: %s", config['environment'])
    logger.info("Target: %s", schema_fqn)
    logger.info("Semantic view source: %s", source)

    if source == "dbt":
        if args.view:
            logger.warning("--view flag ignored in dbt mode (views are managed by dbt)")
        sys.exit(run_dbt_path(config, schema_fqn, args.dry_run))
    else:
        sys.exit(run_yaml_path(config, schema_fqn, args.view, args.dry_run))


if __name__ == "__main__":
    main()
