"""Check semantic view evaluation results via GET_ANALYST_AI_EVALUATION_DATA.

Queries Snowflake for SV eval results, computes SQL correctness score
from EVAL_AGG_SCORE, and checks against thresholds.

Function reference:
    SNOWFLAKE.LOCAL.GET_ANALYST_AI_EVALUATION_DATA(
        <DATABASE>,    -- Database containing the semantic view
        <SCHEMA>,      -- Schema containing the semantic view
        <OBJECT_NAME>, -- Name of the semantic view
        <OBJECT_TYPE>, -- 'SEMANTIC VIEW'
        <RUN_NAME>     -- Eval run label e.g. 'eval_revenue_v9'
    )

    Returns columns:
        RECORD_ID       VARCHAR   Unique record identifier
        INPUT_ID        VARCHAR   Unique input identifier
        REQUEST_ID      VARCHAR   Unique request identifier
        TIMESTAMP       TIMESTAMP Time the request was made
        DURATION_MS     INT       Analyst response time in ms
        INPUT           VARCHAR   Query string used as input
        OUTPUT          VARCHAR   SQL response from Cortex Analyst
        ERROR           VARCHAR   Error info (empty on success)
        GROUND_TRUTH    VARCHAR   Expected SQL from VQR
        METRIC_NAME     VARCHAR   Metric name (e.g. 'sql_correctness')
        EVAL_AGG_SCORE  NUMBER    Score: 1=correct, 0.5=partial, 0=wrong, NULL=error
        METRIC_TYPE     VARCHAR   'system' for built-in, 'custom' for custom
        METRIC_STATUS   VARIANT   Internal status object
        METRIC_CALLS    VARIANT   Internal metric call details

    NOTE: This is different from GET_AI_EVALUATION_DATA which only works
    for agent_type='CORTEX AGENT'. For semantic view evals, you MUST use
    GET_ANALYST_AI_EVALUATION_DATA.

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
            FROM TABLE(SNOWFLAKE.LOCAL.GET_ANALYST_AI_EVALUATION_DATA(
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
        return {"total": 0, "scored": 0, "sum_score": 0.0, "score": 0.0, "errors": 0, "details": []}

    total = len(results)
    details = []
    sum_score = 0.0
    scored = 0
    errors = 0

    for r in results:
        agg = r.get("EVAL_AGG_SCORE")
        question = (r.get("INPUT") or "")[:120]
        error = r.get("ERROR") or ""
        detail = {"question": question, "score": agg, "has_error": bool(error)}
        details.append(detail)

        if agg is not None:
            sum_score += float(agg)
            scored += 1
        else:
            errors += 1

    return {
        "total": total,
        "scored": scored,
        "sum_score": round(sum_score, 4),
        "score": round(sum_score / scored, 4) if scored > 0 else 0.0,
        "errors": errors,
        "details": details,
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

    logger.info("Environment: %s", config['environment'])
    logger.info("Run: %s", args.run_name)
    logger.info("Threshold: sql_correctness >= %s", sv_threshold)
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

            logger.info("    VQRs: %d total, %d scored, %d errors", metrics['total'], metrics['scored'], metrics['errors'])
            logger.info("    Score: %.1f%% (%s/%s) %s %s [%s]",
                        metrics['score'] * 100, metrics['sum_score'], metrics['scored'],
                        '≥' if score_pass else '<', f"{sv_threshold:.0%}",
                        'PASS' if score_pass else 'FAIL')
            for d in metrics['details']:
                flag = '✓' if d['score'] == 1 else ('½' if d['score'] == 0.5 else ('✗' if d['score'] == 0 else '?'))
                logger.info("      [%s] %s", flag, d['question'])

            if not score_pass:
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
