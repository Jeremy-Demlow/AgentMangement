"""Check VQR deployment and eval status across environments.

Usage:
    agent-mgmt-check-sv-evals --env prod
    agent-mgmt-check-sv-evals --env prod dev qa
    agent-mgmt-check-sv-evals --env dev --sv sem_revenue
"""
from __future__ import annotations

import argparse
import logging

import yaml

from agent_management import setup_logging
from agent_management.utils.config import (
    discover_vqr_views,
    get_database,
    get_eval_config,
    load_env_config,
)
from agent_management.utils.snowflake_client import connect

logger = logging.getLogger(__name__)


def check_vqrs(cur, database: str, sv_names: list[str]):
    logger.info("\n  VQR Status:")
    for sv_name in sv_names:
        fq = f"{database}.SEMANTIC.{sv_name}"
        try:
            cur.execute("USE ROLE ACCOUNTADMIN")
            cur.execute(f"SELECT SYSTEM$READ_YAML_FROM_SEMANTIC_VIEW('{fq}')")
            parsed = yaml.safe_load(cur.fetchone()[0])
            n = len(parsed.get("verified_queries", []))
            logger.info("    %s: %s %d VQRs", sv_name, "OK" if n else "FAIL", n)
        except Exception as e:
            logger.info("    %s: ERROR - %s", sv_name, e)


def check_eval_status(cur, database: str, role: str, sv_names: list[str]):
    cur.execute(f"USE ROLE {role}")
    logger.info("\n  Eval Status:")
    for sv_name in sv_names:
        run_name = f"{database.lower()}_{sv_name.lower()}_eval_v2"
        fname = f"sv_eval_{sv_name.lower()}.yaml"
        stage_path = f"@{database}.AGENTS.eval_config_stage/{fname}"
        try:
            cur.execute(
                f"CALL EXECUTE_AI_EVALUATION('STATUS', OBJECT_CONSTRUCT('run_name', '{run_name}'), '{stage_path}')"
            )
            row = cur.fetchone()
            if row:
                logger.info("    %s: %s (run=%s)", sv_name, row[3], row[0])
            else:
                logger.info("    %s: no status", sv_name)
        except Exception as e:
            err = str(e)
            if "does not exist" in err:
                logger.info("    %s: NOT STARTED", sv_name)
            else:
                logger.info("    %s: ERROR - %s", sv_name, e)


def check_eval_results(cur, database: str, sv_names: list[str]):
    logger.info("\n  Eval Results:")
    for sv_name in sv_names:
        run_name = f"{database.lower()}_{sv_name.lower()}_eval_v2"
        try:
            cur.execute(f"""
                SELECT COUNT(*) AS total_records,
                       COUNT(CASE WHEN EVAL_AGG_SCORE IS NOT NULL THEN 1 END) AS scored,
                       AVG(EVAL_AGG_SCORE) AS avg_score
                FROM TABLE(SNOWFLAKE.LOCAL.GET_ANALYST_AI_EVALUATION_DATA(
                    '{database}', 'SEMANTIC', '{sv_name}', 'SEMANTIC VIEW', '{run_name}'
                ))
            """)
            row = cur.fetchone()
            if row and row[0] > 0:
                if row[2]:
                    logger.info("    %s: %d records, %d scored, avg_score=%.3f", sv_name, row[0], row[1], row[2])
                else:
                    logger.info("    %s: %d records, scoring in progress", sv_name, row[0])
            else:
                logger.info("    %s: No results yet", sv_name)
        except Exception as e:
            logger.info("    %s: %s", sv_name, e)


def main():
    parser = argparse.ArgumentParser(description="Check SV eval status across environments")
    parser.add_argument("--env", "-e", nargs="+", default=["prod", "dev", "qa"],
                        help="Environment(s) to check")
    parser.add_argument("--sv", help="Check single SV by name")
    parser.add_argument("-v", "--verbose", action="count", default=1)
    args = parser.parse_args()

    setup_logging(args.verbose)

    sv_names = [args.sv.upper()] if args.sv else discover_vqr_views()

    for env_name in args.env:
        config = load_env_config(env_name)
        database = get_database(config)
        role = config["snowflake"]["role"]

        logger.info("\n%s\n[%s] (%s)\n%s", "=" * 70, env_name.upper(), database, "=" * 70)

        conn = connect(config)
        cur = conn.cursor()

        try:
            check_vqrs(cur, database, sv_names)
            check_eval_status(cur, database, role, sv_names)
            check_eval_results(cur, database, sv_names)
        finally:
            cur.close()
            conn.close()


if __name__ == "__main__":
    main()
