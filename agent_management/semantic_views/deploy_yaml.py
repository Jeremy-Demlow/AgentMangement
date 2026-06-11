"""Deploy VQRs to semantic views across environments.

Reads SV YAML from PROD, merges verified_queries from local YAML files,
and deploys via CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML.

Usage:
    agent-mgmt-deploy-svs-yaml --env prod
    agent-mgmt-deploy-svs-yaml --env prod dev qa
    agent-mgmt-deploy-svs-yaml --env dev --sv sem_revenue
    agent-mgmt-deploy-svs-yaml --env dev --dry-run
"""
from __future__ import annotations

import argparse
import logging

import yaml

from agent_management import setup_logging
from agent_management.paths import sv_verified_queries_dir
from agent_management.utils.config import (
    discover_vqr_views,
    get_database,
    get_semantic_schema,
    load_env_config,
)
from agent_management.utils.snowflake_client import connect

logger = logging.getLogger(__name__)


def load_vqrs(sv_name: str) -> list[dict] | None:
    path = sv_verified_queries_dir() / f"{sv_name.lower()}.yaml"
    if not path.exists():
        return None
    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("verified_queries", [])


def deploy_one(
    cur, sv_name: str, env_name: str, target_db: str, target_schema: str,
    source_db: str, dry_run: bool = False,
) -> bool:
    cur.execute("USE ROLE ACCOUNTADMIN")
    cur.execute(f"SELECT SYSTEM$READ_YAML_FROM_SEMANTIC_VIEW('{source_db}.SEMANTIC.{sv_name}')")
    sv_yaml_str = cur.fetchone()[0]

    if target_db != source_db:
        sv_yaml_str = sv_yaml_str.replace(f"database: {source_db}", f"database: {target_db}")

    sv_yaml = yaml.safe_load(sv_yaml_str)

    vqrs = load_vqrs(sv_name)
    if not vqrs:
        logger.info("  [%s] %s: SKIP - no VQR file", env_name, sv_name)
        return False

    sv_yaml["verified_queries"] = vqrs
    final_yaml = yaml.dump(sv_yaml, default_flow_style=False, sort_keys=False, width=200, allow_unicode=True)

    if dry_run:
        logger.info("  [DRY RUN] [%s] %s: would deploy %d VQRs", env_name, sv_name, len(vqrs))
        return True

    try:
        cur.execute(f"CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML('{target_schema}', $${final_yaml}$$)")
        logger.info("  [%s] %s: %s (%d VQRs)", env_name, sv_name, cur.fetchone()[0], len(vqrs))
        return True
    except Exception as e:
        logger.error("  [%s] %s: FAILED - %s", env_name, sv_name, e)
        return False


def verify_vqrs(cur, env_name: str, target_db: str, sv_names: list[str]):
    logger.info("\n[%s] Verifying VQRs:", env_name)
    for sv_name in sv_names:
        fq = f"{target_db}.SEMANTIC.{sv_name}"
        try:
            cur.execute(f"SELECT SYSTEM$READ_YAML_FROM_SEMANTIC_VIEW('{fq}')")
            parsed = yaml.safe_load(cur.fetchone()[0])
            n = len(parsed.get("verified_queries", []))
            logger.info("  %s: %s %d VQRs", sv_name, "OK" if n else "FAIL", n)
        except Exception as e:
            logger.info("  %s: ERROR - %s", sv_name, e)


def main():
    parser = argparse.ArgumentParser(description="Deploy VQRs to semantic views")
    parser.add_argument("--env", "-e", nargs="+", default=["prod", "dev", "qa"],
                        help="Target environment(s)")
    parser.add_argument("--sv", help="Deploy single SV by name (e.g. SEM_REVENUE)")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Preview without deploying")
    parser.add_argument("-v", "--verbose", action="count", default=1)
    args = parser.parse_args()

    setup_logging(args.verbose)

    source_config = load_env_config("prod")
    source_db = get_database(source_config)

    sv_names = [args.sv.upper()] if args.sv else discover_vqr_views()
    logger.info("Source: %s.SEMANTIC", source_db)
    logger.info("SVs with VQRs: %s", ", ".join(sv_names))

    for env_name in args.env:
        config = load_env_config(env_name)
        target_db = get_database(config)
        target_schema = get_semantic_schema(config)

        logger.info("\n%s\nDeploying to %s (%s)\n%s", "=" * 60, env_name, target_db, "=" * 60)

        conn = connect(config)
        cur = conn.cursor()

        try:
            for sv_name in sv_names:
                deploy_one(cur, sv_name, env_name, target_db, target_schema, source_db, args.dry_run)

            verify_vqrs(cur, env_name, target_db, sv_names)
        finally:
            cur.close()
            conn.close()


if __name__ == "__main__":
    main()
