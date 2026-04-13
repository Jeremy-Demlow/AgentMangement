"""Check semantic view evaluation results via GET_AI_EVALUATION_DATA.

Queries Snowflake for SV eval results, computes SQL correctness score,
and checks against thresholds.

Usage:
    python -m agent_management.check_sv_eval --env prod --run-name "my_eval_run"
    python -m agent_management.check_sv_eval --env prod --sv sem_operations --run-name "my_eval_run"

Implements REQ-009: Semantic View Evaluation.
"""
from __future__ import annotations

import argparse
import logging
import sys

from agent_management import setup_logging
from agent_management.utils.config import get_database, get_thresholds, load_env_config
from agent_management.utils.snowflake_client import connect

logger = logging.getLogger(__name__)


def get_sv_eval_data(cur, database: str, schema: str, sv_name: str, run_name: str) -> list[dict]:
    try:
        cur.execute(f"""
            SELECT *
            FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(
                '{database}', '{schema}', '{sv_name}', 'SEMANTIC VIEW', '{run_name}'
            ))
        """)
        columns = [col[0] for col in cur.description]
        rows = []
        for row in cur.fetchall():
            rows.append(dict(zip(columns, row)))
        return rows
    except Exception as e:
        logger.error("    ERROR querying eval data: %s", e)
        return []


def compute_sv_score(results: list[dict]) -> dict:
    if not results:
        return {"total": 0, "correct": 0, "score": 0.0, "regressions": 0}

    total = len(results)
    correct = sum(1 for r in results if r.get("SQL_CORRECT", r.get("sql_correct")) in (True, "TRUE", "true", 1))
    regressions = sum(1 for r in results if r.get("REGRESSION", r.get("regression")) in (True, "TRUE", "true", 1))

    return {
        "total": total,
        "correct": correct,
        "score": round(correct / total, 4) if total > 0 else 0.0,
        "regressions": regressions,
    }


def main():
    parser = argparse.ArgumentParser(description="Check SV evaluation results")
    parser.add_argument("--env", "-e", help="Environment (dev, qa, prod)")
    parser.add_argument("--run-name", required=True, help="Eval run name")
    parser.add_argument("--sv", help="Check single SV by name")
    args = parser.parse_args()

    setup_logging(1)

    config = load_env_config(args.env)
    thresholds = get_thresholds(config)
    database = get_database(config)
    schema = config["deployment"]["semantic_schema"]

    sv_threshold = thresholds.get("sv_sql_correctness", 0.70)
    max_regressions = thresholds.get("sv_max_regressions", 0)

    logger.info("Environment: %s", config['environment'])
    logger.info("Run: %s", args.run_name)
    logger.info("Thresholds: sql_correctness >= %s, max_regressions <= %s", sv_threshold, max_regressions)
    logger.info("=" * 60)

    conn = connect(config)
    cur = conn.cursor()

    try:
        if args.sv:
            sv_names = [args.sv.upper()]
        else:
            cur.execute(f"SHOW SEMANTIC VIEWS IN SCHEMA {database}.{schema}")
            sv_names = [row[1] for row in cur.fetchall()]

        all_passed = True
        total_checked = 0

        for sv_name in sv_names:
            logger.info("\n  %s:", sv_name)
            results = get_sv_eval_data(cur, database, schema, sv_name, args.run_name)

            if not results:
                logger.info("    No eval data found")
                continue

            metrics = compute_sv_score(results)
            total_checked += 1

            score_pass = metrics["score"] >= sv_threshold
            regression_pass = metrics["regressions"] <= max_regressions

            logger.info("    Queries: %d", metrics['total'])
            logger.info("    Correct: %d", metrics['correct'])
            logger.info("    Score: %.4f %s %s [%s]", metrics['score'], '≥' if score_pass else '<', sv_threshold, 'PASS' if score_pass else 'FAIL')
            logger.info("    Regressions: %d %s %s [%s]", metrics['regressions'], '≤' if regression_pass else '>', max_regressions, 'PASS' if regression_pass else 'FAIL')

            if not score_pass or not regression_pass:
                all_passed = False

        logger.info("\n%s", "=" * 60)
        if total_checked == 0:
            logger.warning("NO EVAL DATA FOUND — cannot determine pass/fail")
            logger.warning("Run SV evaluations first, then re-run this check.")
        elif all_passed:
            logger.info("SV EVAL GATE: PASSED (%d views checked)", total_checked)
        else:
            logger.error("SV EVAL GATE: FAILED (%d views checked)", total_checked)
            sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
