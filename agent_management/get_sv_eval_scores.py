"""Retrieve and display semantic view evaluation scores.

Queries SNOWFLAKE.LOCAL.GET_ANALYST_AI_EVALUATION_DATA for each semantic view
and produces a summary scorecard with per-VQR detail.

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

    NOTE: GET_AI_EVALUATION_DATA does NOT work for semantic view evals.
          Always use GET_ANALYST_AI_EVALUATION_DATA instead.

Usage:
    python -m agent_management.get_sv_eval_scores --env prod
    python -m agent_management.get_sv_eval_scores --env prod --sv sem_revenue --run-name eval_revenue_v9
    python -m agent_management.get_sv_eval_scores --env prod --detail
    python -m agent_management.get_sv_eval_scores --env prod --json
    python -m agent_management.get_sv_eval_scores --env prod --threshold 0.80
"""
from __future__ import annotations

import argparse
import json
import logging
import sys

from agent_management import setup_logging
from agent_management.utils.config import (
    get_database,
    get_thresholds,
    load_env_config,
)
from agent_management.utils.snowflake_client import connect

logger = logging.getLogger(__name__)


def fetch_eval_data(
    cur, database: str, schema: str, sv_name: str, run_name: str
) -> list[dict]:
    cur.execute(f"""
        SELECT *
        FROM TABLE(SNOWFLAKE.LOCAL.GET_ANALYST_AI_EVALUATION_DATA(
            '{database}', '{schema}', '{sv_name}', 'SEMANTIC VIEW', '{run_name}'
        ))
    """)
    columns = [col[0] for col in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def score_results(results: list[dict]) -> dict:
    if not results:
        return {"total": 0, "scored": 0, "sum_score": 0.0, "score": 0.0, "errors": 0, "vqrs": []}

    total = len(results)
    sum_score = 0.0
    scored = 0
    errors = 0
    vqrs = []

    for r in results:
        agg = r.get("EVAL_AGG_SCORE")
        question = (r.get("INPUT") or "")[:200]
        error_text = r.get("ERROR") or ""
        duration = r.get("DURATION_MS")

        vqr = {
            "question": question,
            "score": float(agg) if agg is not None else None,
            "duration_ms": duration,
            "has_error": bool(error_text),
            "error_preview": error_text[:200] if error_text else "",
        }
        vqrs.append(vqr)

        if agg is not None:
            sum_score += float(agg)
            scored += 1
        else:
            errors += 1

    return {
        "total": total,
        "scored": scored,
        "sum_score": round(sum_score, 2),
        "score": round(sum_score / scored, 4) if scored > 0 else 0.0,
        "errors": errors,
        "vqrs": vqrs,
    }


def find_latest_run(cur, database: str, schema: str, sv_name: str) -> str | None:
    try:
        cur.execute(f"SHOW DATASETS IN SCHEMA {database}.{schema}")
        rows = cur.fetchall()
        ds_name = f"{sv_name}_SYSTEM_EVAL"
        for row in rows:
            if row[1] and row[1].upper() == ds_name:
                cur.execute(f"""
                    SELECT VALUE
                    FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_OBSERVABILITY_LOGS(
                        '{database}', '{schema}',
                        'SYSTEM_AI_OBS_ANALYST_EVAL_{sv_name}',
                        'Semantic View Optimization'
                    ))
                    WHERE VALUE LIKE '%Finalizer updating Metric Status for Run%'
                    ORDER BY TIMESTAMP DESC LIMIT 1
                """)
                log_row = cur.fetchone()
                if log_row:
                    val = str(log_row[0])
                    if "Run " in val:
                        return val.split("Run ")[-1].strip()
        return None
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Retrieve SV evaluation scores via GET_ANALYST_AI_EVALUATION_DATA"
    )
    parser.add_argument("--env", "-e", help="Environment (dev, qa, prod)")
    parser.add_argument("--sv", help="Single SV name (e.g. SEM_REVENUE)")
    parser.add_argument("--run-name", help="Eval run name (auto-detects latest if omitted)")
    parser.add_argument("--detail", action="store_true", help="Show per-VQR detail")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Output as JSON")
    parser.add_argument("--threshold", type=float, help="Override pass threshold (default from config)")
    parser.add_argument("-v", "--verbose", action="count", default=1)
    args = parser.parse_args()

    setup_logging(args.verbose)

    config = load_env_config(args.env)
    database = get_database(config)
    schema = config["deployment"]["semantic_schema"]
    thresholds = get_thresholds(config)
    sv_threshold = args.threshold or thresholds.get("sv_sql_correctness", 0.80)

    conn = connect(config)
    cur = conn.cursor()
    cur.execute(f"USE DATABASE {database}")
    cur.execute(f"USE SCHEMA {database}.{schema}")

    try:
        if args.sv:
            sv_names = [args.sv.upper()]
        else:
            cur.execute(f"SHOW SEMANTIC VIEWS IN SCHEMA {database}.{schema}")
            sv_names = [row[1] for row in cur.fetchall() if row[7]]

        all_scores = {}
        all_passed = True
        no_data_count = 0

        if not args.json_output:
            logger.info("=" * 70)
            logger.info("SV Evaluation Scorecard — %s (%s.%s)", config["environment"].upper(), database, schema)
            logger.info("Threshold: %.0f%%", sv_threshold * 100)
            logger.info("=" * 70)

        for sv_name in sorted(sv_names):
            run_name = args.run_name
            if not run_name:
                run_name = find_latest_run(cur, database, schema, sv_name)

            if not run_name:
                if not args.json_output:
                    logger.info("\n  %-35s  NO EVAL RUN FOUND", sv_name)
                all_scores[sv_name] = {"status": "no_run"}
                no_data_count += 1
                continue

            try:
                results = fetch_eval_data(cur, database, schema, sv_name, run_name)
            except Exception as e:
                if not args.json_output:
                    logger.info("\n  %-35s  ERROR: %s", sv_name, e)
                all_scores[sv_name] = {"status": "error", "error": str(e)}
                continue

            if not results:
                if not args.json_output:
                    logger.info("\n  %-35s  NO RESULTS (run=%s)", sv_name, run_name)
                all_scores[sv_name] = {"status": "empty", "run_name": run_name}
                no_data_count += 1
                continue

            metrics = score_results(results)
            passed = metrics["score"] >= sv_threshold
            if not passed:
                all_passed = False

            all_scores[sv_name] = {
                "status": "PASS" if passed else "FAIL",
                "run_name": run_name,
                **metrics,
            }

            if not args.json_output:
                flag = "PASS" if passed else "FAIL"
                pct = metrics["score"] * 100
                logger.info(
                    "\n  %-35s  %5.1f%%  (%s/%s scored)  [%s]  run=%s",
                    sv_name, pct, metrics["sum_score"], metrics["scored"], flag, run_name,
                )
                if metrics["errors"]:
                    logger.info("    %d VQR(s) returned NULL score (error)", metrics["errors"])

                if args.detail:
                    for v in metrics["vqrs"]:
                        icon = {1.0: "+", 0.5: "~", 0.0: "-"}.get(v["score"], "?")
                        score_str = f"{v['score']:.1f}" if v["score"] is not None else "NULL"
                        ms = f"  ({v['duration_ms']}ms)" if v["duration_ms"] else ""
                        logger.info("    [%s] %s  %s%s", icon, score_str, v["question"][:100], ms)
                        if v["has_error"] and v["error_preview"]:
                            logger.info("        ERROR: %s", v["error_preview"][:120])

        if args.json_output:
            output = {
                "environment": config["environment"],
                "database": database,
                "schema": schema,
                "threshold": sv_threshold,
                "all_passed": all_passed,
                "views": all_scores,
            }
            print(json.dumps(output, indent=2, default=str))
        else:
            logger.info("\n" + "=" * 70)
            passing = sum(1 for v in all_scores.values() if v.get("status") == "PASS")
            failing = sum(1 for v in all_scores.values() if v.get("status") == "FAIL")
            logger.info(
                "SUMMARY: %d PASS, %d FAIL, %d no data  (%d total)",
                passing, failing, no_data_count, len(sv_names),
            )
            if all_passed and no_data_count == 0:
                logger.info("EVAL GATE: PASSED")
            elif failing > 0:
                logger.error("EVAL GATE: FAILED")
            else:
                logger.warning("EVAL GATE: INCOMPLETE (missing eval data)")
            logger.info("=" * 70)

        if failing > 0:
            sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
