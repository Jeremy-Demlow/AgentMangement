"""Deploy semantic view YAMLs to Snowflake.

Renders Jinja2 templates with environment config, then deploys via
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
from agent_management.utils.config import get_semantic_schema, load_env_config
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


def main():
    parser = argparse.ArgumentParser(description="Deploy semantic views from YAML")
    parser.add_argument("--env", "-e", help="Environment (dev, qa, prod)")
    parser.add_argument("--view", "-v", help="Deploy single view by name")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Validate only, no deploy")
    args = parser.parse_args()

    setup_logging(1)

    config = load_env_config(args.env)
    schema_fqn = get_semantic_schema(config)
    sv_files = find_sv_files(args.view)

    logger.info("Environment: %s", config['environment'])
    logger.info("Target: %s", schema_fqn)
    logger.info("Views: %d", len(sv_files))
    logger.info("=" * 60)

    conn = connect(config, schema=config["deployment"]["semantic_schema"])
    cur = conn.cursor()

    success = 0
    failed = 0
    for path in sv_files:
        name = path.stem
        rendered = render_file(path, config)
        if deploy_one(cur, schema_fqn, rendered, name, args.dry_run):
            success += 1
        else:
            failed += 1

    logger.info("\n%s", "=" * 60)
    action = "Validated" if args.dry_run else "Deployed"
    logger.info("%s: %d  Failed: %d  Environment: %s", action, success, failed, config['environment'])

    if not args.dry_run:
        cur.execute(f"SHOW SEMANTIC VIEWS IN SCHEMA {schema_fqn}")
        rows = cur.fetchall()
        logger.info("\nSemantic views in %s: %d", schema_fqn, len(rows))
        for row in rows:
            logger.info("  - %s", row[1])

    cur.close()
    conn.close()
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
