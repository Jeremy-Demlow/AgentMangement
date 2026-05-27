"""Run Cortex Analyst semantic view evaluations end-to-end.

Generates eval config YAML, uploads to stage, starts EXECUTE_AI_EVALUATION,
polls until complete, fetches results via GET_ANALYST_AI_EVALUATION_DATA,
and checks thresholds.

When evaluating multiple SVs, evals are started sequentially then polled
in parallel using a thread pool (each thread gets its own Snowflake
connection). This cuts wall time from ~25 min to ~3-5 min for 11 SVs.

Function reference:
    SNOWFLAKE.LOCAL.GET_ANALYST_AI_EVALUATION_DATA(
        <DATABASE>, <SCHEMA>, <OBJECT_NAME>, 'SEMANTIC VIEW', <RUN_NAME>
    )
    Returns: RECORD_ID, INPUT_ID, REQUEST_ID, TIMESTAMP, DURATION_MS,
             INPUT, OUTPUT, ERROR, GROUND_TRUTH, METRIC_NAME,
             EVAL_AGG_SCORE (1=correct, 0.5=partial, 0=wrong, NULL=error),
             METRIC_TYPE, METRIC_STATUS, METRIC_CALLS

    NOTE: GET_AI_EVALUATION_DATA does NOT work for semantic view evals.
          Always use GET_ANALYST_AI_EVALUATION_DATA instead.

Usage:
    python -m agent_management.run_sv_eval --env prod
    python -m agent_management.run_sv_eval --env prod --sv sem_revenue
    python -m agent_management.run_sv_eval --env prod --agent ski_ops_assistant
    python -m agent_management.run_sv_eval --env dev --dry-run
    python -m agent_management.run_sv_eval --env dev --max-parallel 4
    python -m agent_management.run_sv_eval --env prod --status --run-name "sv_eval_20260416"
    python -m agent_management.run_sv_eval --env prod --results --run-name "sv_eval_20260416"

Implements REQ-009: Semantic View Evaluation.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from agent_management import setup_logging
from agent_management.get_sv_eval_scores import is_platform_error
from agent_management.utils.config import (
    get_database,
    get_sv_eval_config,
    get_svs_for_agents,
    get_thresholds,
    load_env_config,
)
from agent_management.utils.snowflake_client import connect

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 30
MAX_POLL_ATTEMPTS = 60

# Exit code taxonomy (matches run_ci_eval.py):
#   0 = all SVs passed threshold
#   1 = one or more SVs below threshold (advisory in DEV, hard-fail in PROD)
#   2 = crash / unhandled error (always hard-fail)
#   3 = platform blocker (Snowflake Cortex Analyst Evaluations PuPr bug —
#       SYSTEM_AI_OBS_ANALYST_EVAL_* object missing). Always advisory; the
#       rest of the pipeline should proceed.
EXIT_PASS = 0
EXIT_THRESHOLD_FAIL = 1
EXIT_CRASH = 2
EXIT_PLATFORM_BLOCKED = 3

# Error signatures that indicate Snowflake platform issues, not our code or
# spec. Detecting these lets CI classify the failure instead of dumping the
# raw stack and confusing operators.
_PLATFORM_BLOCKER_PATTERNS = (
    # The Cortex Analyst Evaluations PuPr optimization-object bug.
    "semantic view optimization",
    "system_ai_obs_analyst_eval",
    # Also seen on platform outages / maintenance windows.
    "service is currently unavailable",
    "execute_ai_evaluation.*internal error",
)


def is_platform_blocker(err: object) -> bool:
    """True if an error looks like the known Cortex Analyst PuPr bug or a
    platform outage. Never returns True for threshold failures or code bugs."""
    if err is None:
        return False
    msg = str(err).lower()
    return any(pat in msg for pat in _PLATFORM_BLOCKER_PATTERNS)


def generate_eval_yaml(
    database: str,
    schema: str,
    sv_name: str,
    run_name: str,
    label: str | None = None,
) -> str:
    return f"""evaluation:
  analyst_params:
    analyst_name: "{database}.{schema}.{sv_name}"
    analyst_type: "SEMANTIC VIEW"
  run_params:
    label: "{label or f'{sv_name} evaluation'}"
    description: "Automated SV evaluation - {run_name}"
  source_metadata:
    type: "verified_queries"

metrics:
  - "sql_correctness"
"""


def ensure_stage(cur, stage: str, file_format: str):
    cur.execute(f"""
        CREATE FILE FORMAT IF NOT EXISTS {file_format}
          TYPE = 'CSV'
          FIELD_DELIMITER = NONE
          RECORD_DELIMITER = '\\n'
          SKIP_HEADER = 0
          FIELD_OPTIONALLY_ENCLOSED_BY = NONE
          ESCAPE_UNENCLOSED_FIELD = NONE
    """)
    cur.execute(f"CREATE STAGE IF NOT EXISTS {stage} FILE_FORMAT = {file_format}")
    logger.info("  Stage: %s", stage)


def upload_yaml(cur, yaml_content: str, stage: str, filename: str):
    escaped = yaml_content.replace("'", "''")
    cur.execute(f"""
        COPY INTO @{stage}/{filename}
        FROM (SELECT '{escaped}')
        FILE_FORMAT = (TYPE = 'CSV' FIELD_DELIMITER = NONE RECORD_DELIMITER = NONE COMPRESSION = NONE)
        SINGLE = TRUE
        OVERWRITE = TRUE
    """)
    logger.info("  Uploaded: @%s/%s", stage, filename)


def start_eval(cur, run_name: str, stage: str, filename: str):
    cur.execute(f"""
        CALL EXECUTE_AI_EVALUATION(
            'START',
            OBJECT_CONSTRUCT('run_name', '{run_name}'),
            '@{stage}/{filename}'
        )
    """)
    row = cur.fetchone()
    logger.info("  Eval started: %s", run_name)
    if row:
        logger.info("  Response: %s", row[0])
    return row


def check_status(cur, run_name: str, stage: str, filename: str) -> tuple[str, str]:
    """Return (status, detail_text). Detail is empty string when absent.

    Detail is exposed so callers can distinguish a generic FAILED from a
    documented Cortex Analyst platform error like 'Invocation failed' /
    error code 392700, which let the runner classify these as advisory
    platform_blocked rather than real eval-engine crashes.
    """
    cur.execute(f"""
        CALL EXECUTE_AI_EVALUATION(
            'STATUS',
            OBJECT_CONSTRUCT('run_name', '{run_name}'),
            '@{stage}/{filename}'
        )
    """)
    row = cur.fetchone()
    if not row:
        return "UNKNOWN", ""
    cols = [col[0].upper() for col in cur.description] if cur.description else []
    if "STATUS" in cols:
        idx = cols.index("STATUS")
        status = str(row[idx])
    elif len(row) > 3:
        status = str(row[3])
    else:
        status = str(row[0])
    logger.info("  Status: %s", status)
    detail_idx = cols.index("STATUS_DETAILS") if "STATUS_DETAILS" in cols else (4 if len(row) > 4 else -1)
    detail = ""
    if detail_idx >= 0 and row[detail_idx]:
        detail = str(row[detail_idx])
        logger.info("  Detail: %s", detail)
    return status, detail


def get_eval_results(cur, database: str, schema: str, sv_name: str, run_name: str) -> list[dict]:
    try:
        cur.execute(f"""
            SELECT *
            FROM TABLE(SNOWFLAKE.LOCAL.GET_ANALYST_AI_EVALUATION_DATA(
                '{database}', '{schema}', '{sv_name}', 'SEMANTIC VIEW', '{run_name}'
            ))
        """)
        columns = [col[0] for col in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]
    except Exception as e:
        logger.error("  Error fetching eval data: %s", e)
        return []


def compute_score(results: list[dict]) -> dict:
    if not results:
        return {"total": 0, "scored": 0, "sum_score": 0.0, "score": 0.0, "errors": 0, "flake_errors": 0}

    total = len(results)
    sum_score = 0.0
    scored = 0
    errors = 0
    flake_errors = 0

    for r in results:
        agg = r.get("EVAL_AGG_SCORE")
        if agg is not None:
            sum_score += float(agg)
            scored += 1
        else:
            errors += 1
            err_text = (r.get("ERROR") or "").lower()
            # Known Cortex Analyst platform flake: "Invocation failed" on
            # individual VQR submission. Retryable.
            if "invocation failed" in err_text:
                flake_errors += 1

    return {
        "total": total,
        "scored": scored,
        "sum_score": round(sum_score, 4),
        "score": round(sum_score / scored, 4) if scored > 0 else 0.0,
        "errors": errors,
        "flake_errors": flake_errors,
    }


def _is_retryable(metrics: dict) -> bool:
    """True if the only failures are platform flakes ('Invocation failed').

    We only retry when every non-scored row is a known flake — never retry
    real metric failures (those are signal).
    """
    errors = metrics.get("errors", 0) or 0
    flake = metrics.get("flake_errors", 0) or 0
    return errors > 0 and flake == errors


def start_sv_eval(
    cur,
    database: str,
    schema: str,
    sv_name: str,
    stage: str,
    file_format: str,
    run_name: str,
) -> str:
    logger.info("\n  === %s ===", sv_name)
    eval_yaml = generate_eval_yaml(database, schema, sv_name, run_name)
    filename = f"sv_eval_{sv_name.lower()}_{run_name}.yaml"
    ensure_stage(cur, stage, file_format)
    upload_yaml(cur, eval_yaml, stage, filename)
    start_eval(cur, run_name, stage, filename)
    return filename


def poll_and_collect(
    config: dict,
    database: str,
    schema: str,
    sv_name: str,
    stage: str,
    filename: str,
    run_name: str,
) -> dict:
    conn = connect(config)
    cur = conn.cursor()
    try:
        cur.execute(f"USE DATABASE {database}")
        cur.execute(f"USE SCHEMA {database}.{schema}")

        logger.info("  [%s] Polling (interval=%ds, max=%d attempts)...",
                    sv_name, POLL_INTERVAL_SECONDS, MAX_POLL_ATTEMPTS)

        for attempt in range(1, MAX_POLL_ATTEMPTS + 1):
            time.sleep(POLL_INTERVAL_SECONDS)
            try:
                status, detail = check_status(cur, run_name, stage, filename)
            except Exception as exc:
                if is_platform_blocker(exc):
                    logger.warning(
                        "  [%s] PLATFORM BLOCKED while polling: %s",
                        sv_name, str(exc)[:200],
                    )
                    return {"total": 0, "scored": 0, "score": 0.0,
                            "errors": 0, "flake_errors": 0,
                            "error": "PLATFORM_BLOCKED",
                            "platform_blocked": True}
                raise

            if status in ("COMPLETED", "SUCCEEDED"):
                logger.info("  [%s] Completed after %d poll(s)", sv_name, attempt)
                results = get_eval_results(cur, database, schema, sv_name, run_name)
                metrics = compute_score(results)
                # Auto-retry ONCE on pure platform flake (all errors are
                # "Invocation failed"). Never retry real metric failures.
                if _is_retryable(metrics):
                    logger.warning(
                        "  [%s] %d VQR(s) hit platform flake ('Invocation failed'); retrying once",
                        sv_name, metrics["flake_errors"],
                    )
                    retry_run_name = f"{run_name}-r1"
                    try:
                        start_eval(cur, retry_run_name, stage, filename)
                        for r_attempt in range(1, MAX_POLL_ATTEMPTS + 1):
                            time.sleep(POLL_INTERVAL_SECONDS)
                            r_status, _ = check_status(cur, retry_run_name, stage, filename)
                            if r_status in ("COMPLETED", "SUCCEEDED"):
                                r_results = get_eval_results(cur, database, schema, sv_name, retry_run_name)
                                r_metrics = compute_score(r_results)
                                logger.info("  [%s] Retry succeeded: %d/%d scored", sv_name, r_metrics["scored"], r_metrics["total"])
                                return r_metrics
                            if r_status in ("FAILED", "ERROR", "CANCELLED"):
                                logger.warning("  [%s] Retry terminal: %s (keeping original metrics)", sv_name, r_status)
                                break
                    except Exception as exc:
                        logger.warning("  [%s] Retry attempt raised (keeping original): %s", sv_name, exc)
                return metrics
            elif status in ("FAILED", "ERROR", "CANCELLED"):
                # If the orchestrator-level detail text matches a documented
                # Cortex Analyst platform error signature, classify the run
                # as platform_blocked without trying to read per-VQR data
                # (which won't exist when the eval framework itself errors).
                if is_platform_error(detail):
                    logger.warning(
                        "  [%s] PLATFORM BLOCKED: orchestrator failed with %s -- %s",
                        sv_name, status, detail[:200],
                    )
                    return {
                        "total": 0, "scored": 0, "score": 0.0,
                        "errors": 0, "flake_errors": 0,
                        "error": status,
                        "platform_blocked": True,
                    }
                # Eval framework reported terminal failure. Try to fetch
                # per-VQR data anyway: when every VQR carries a documented
                # Cortex Analyst platform error (e.g. 392700), the
                # underlying queries are fine and only the eval engine
                # broke -- classify as platform_blocked rather than a
                # real run failure. If the fetch itself raises, fall back
                # to the original error path.
                try:
                    results = get_eval_results(cur, database, schema, sv_name, run_name)
                    metrics = compute_score(results)
                    if (
                        metrics["scored"] == 0
                        and metrics["errors"] > 0
                        and metrics["flake_errors"] == metrics["errors"]
                    ):
                        logger.warning(
                            "  [%s] Eval status %s but every VQR carries a"
                            " documented Cortex Analyst platform error (%d flake);"
                            " classifying as platform_blocked (advisory).",
                            sv_name, status, metrics["flake_errors"],
                        )
                        return {**metrics, "error": status, "platform_blocked": True}
                except Exception as fetch_exc:  # noqa: BLE001
                    logger.debug("  [%s] post-FAILED fetch raised: %s", sv_name, fetch_exc)
                logger.error("  [%s] Eval %s after %d poll(s)", sv_name, status, attempt)
                return {"total": 0, "scored": 0, "score": 0.0, "errors": 0, "flake_errors": 0, "error": status}

            logger.info("    [%s] Poll %d/%d: %s", sv_name, attempt, MAX_POLL_ATTEMPTS, status)

        logger.error("  [%s] Timed out after %d polls", sv_name, MAX_POLL_ATTEMPTS)
        return {"total": 0, "scored": 0, "score": 0.0, "errors": 0, "error": "TIMEOUT"}
    finally:
        cur.close()
        conn.close()


def run_eval_for_sv(
    cur,
    database: str,
    schema: str,
    sv_name: str,
    stage: str,
    file_format: str,
    run_name: str,
    no_wait: bool = False,
    dry_run: bool = False,
) -> dict | None:
    logger.info("\n  === %s ===", sv_name)

    eval_yaml = generate_eval_yaml(database, schema, sv_name, run_name)
    filename = f"sv_eval_{sv_name.lower()}_{run_name}.yaml"

    if dry_run:
        logger.info("  [DRY RUN] Would upload eval config:")
        logger.info("  %s", eval_yaml.replace("\n", "\n  "))
        return None

    ensure_stage(cur, stage, file_format)
    upload_yaml(cur, eval_yaml, stage, filename)
    start_eval(cur, run_name, stage, filename)

    if no_wait:
        logger.info("  Started (--no-wait). Check with --status --run-name %s", run_name)
        return None

    logger.info("  Polling for completion (interval=%ds, max=%d attempts)...",
                POLL_INTERVAL_SECONDS, MAX_POLL_ATTEMPTS)

    for attempt in range(1, MAX_POLL_ATTEMPTS + 1):
        time.sleep(POLL_INTERVAL_SECONDS)
        status, detail = check_status(cur, run_name, stage, filename)

        if status in ("COMPLETED", "SUCCEEDED"):
            logger.info("  Completed after %d poll(s)", attempt)
            results = get_eval_results(cur, database, schema, sv_name, run_name)
            metrics = compute_score(results)
            if _is_retryable(metrics):
                logger.warning(
                    "  %d VQR(s) hit platform flake ('Invocation failed'); retrying once",
                    metrics["flake_errors"],
                )
                retry_run_name = f"{run_name}-r1"
                try:
                    start_eval(cur, retry_run_name, stage, filename)
                    for r_attempt in range(1, MAX_POLL_ATTEMPTS + 1):
                        time.sleep(POLL_INTERVAL_SECONDS)
                        r_status, _ = check_status(cur, retry_run_name, stage, filename)
                        if r_status in ("COMPLETED", "SUCCEEDED"):
                            r_results = get_eval_results(cur, database, schema, sv_name, retry_run_name)
                            r_metrics = compute_score(r_results)
                            logger.info("  Retry succeeded: %d/%d scored", r_metrics["scored"], r_metrics["total"])
                            return r_metrics
                        if r_status in ("FAILED", "ERROR", "CANCELLED"):
                            logger.warning("  Retry terminal: %s (keeping original metrics)", r_status)
                            break
                except Exception as exc:
                    logger.warning("  Retry attempt raised (keeping original): %s", exc)
            return metrics
        elif status in ("FAILED", "ERROR", "CANCELLED"):
            # Same orchestrator-level platform classification as
            # poll_and_collect.
            if is_platform_error(detail):
                logger.warning(
                    "  PLATFORM BLOCKED: orchestrator failed with %s -- %s",
                    status, detail[:200],
                )
                return {
                    "total": 0, "scored": 0, "score": 0.0,
                    "errors": 0, "flake_errors": 0,
                    "error": status,
                    "platform_blocked": True,
                }
            # Same all-flake classification as poll_and_collect: try to
            # fetch per-VQR data and treat as platform_blocked when every
            # error is a documented Cortex Analyst platform flake.
            try:
                results = get_eval_results(cur, database, schema, sv_name, run_name)
                metrics = compute_score(results)
                if (
                    metrics["scored"] == 0
                    and metrics["errors"] > 0
                    and metrics["flake_errors"] == metrics["errors"]
                ):
                    logger.warning(
                        "  Eval status %s but every VQR carries a documented"
                        " Cortex Analyst platform error (%d flake);"
                        " classifying as platform_blocked (advisory).",
                        status, metrics["flake_errors"],
                    )
                    return {**metrics, "error": status, "platform_blocked": True}
            except Exception as fetch_exc:  # noqa: BLE001
                logger.debug("  post-FAILED fetch raised: %s", fetch_exc)
            logger.error("  Eval %s after %d poll(s)", status, attempt)
            return {"total": 0, "scored": 0, "score": 0.0, "errors": 0, "flake_errors": 0, "error": status}

        logger.info("    Poll %d/%d: %s", attempt, MAX_POLL_ATTEMPTS, status)

    logger.error("  Timed out after %d polls", MAX_POLL_ATTEMPTS)
    return {"total": 0, "scored": 0, "score": 0.0, "errors": 0, "error": "TIMEOUT"}


def main():
    parser = argparse.ArgumentParser(description="Run SV evaluations via EXECUTE_AI_EVALUATION")
    parser.add_argument("--env", "-e", help="Environment (dev, qa, prod)")
    parser.add_argument("--sv", help="Evaluate a single SV by name (e.g. SEM_REVENUE)")
    parser.add_argument("--agent", action="append", help="Evaluate only SVs used by this agent (repeatable, from project.yml)")
    parser.add_argument("--run-name", help="Custom run name (default: auto-generated)")
    parser.add_argument("--no-wait", action="store_true", help="Start eval and exit without waiting")
    parser.add_argument("--dry-run", action="store_true", help="Show eval config without executing")
    parser.add_argument("--status", action="store_true", help="Check status of existing run")
    parser.add_argument("--results", action="store_true", help="Fetch results of existing run")
    parser.add_argument("--max-parallel", type=int, default=11, help="Max concurrent SV evaluations (default: 11)")
    parser.add_argument("-v", "--verbose", action="count", default=1)
    args = parser.parse_args()

    setup_logging(args.verbose)

    config = load_env_config(args.env)
    database = get_database(config)
    schema = config["deployment"]["semantic_schema"]
    thresholds = get_thresholds(config)

    sv_eval_cfg = get_sv_eval_config(config)
    stage = sv_eval_cfg["stage"]
    file_format = sv_eval_cfg["file_format"]

    sv_threshold = thresholds.get("sv_sql_correctness", 0.70)

    run_name = args.run_name or f"sv_eval_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    logger.info("Environment: %s", config["environment"])
    logger.info("Database: %s.%s", database, schema)
    logger.info("Run name: %s", run_name)
    logger.info("Threshold: sql_correctness >= %s", sv_threshold)
    logger.info("=" * 60)

    conn = connect(config)
    cur = conn.cursor()
    cur.execute(f"USE DATABASE {database}")
    cur.execute(f"USE SCHEMA {database}.{schema}")

    try:
        if args.sv:
            sv_names = [args.sv.upper()]
        elif args.agent:
            sv_names = get_svs_for_agents(args.agent)
            if not sv_names:
                logger.error("No semantic views configured for agent(s): %s", ", ".join(args.agent))
                logger.error("Check the 'agents' section in project.yml")
                sys.exit(1)
            logger.info("Agent scope: %s -> %d SVs", ", ".join(args.agent), len(sv_names))
        else:
            cur.execute(f"SHOW SEMANTIC VIEWS IN SCHEMA {database}.{schema}")
            rows = cur.fetchall()
            sv_names = [row[1] for row in rows if row[7]]

        if args.status:
            for sv_name in sv_names:
                filename = f"sv_eval_{sv_name.lower()}_{run_name}.yaml"
                logger.info("\n  %s:", sv_name)
                check_status(cur, run_name, stage, filename)
            return

        if args.results:
            all_passed = True
            for sv_name in sv_names:
                logger.info("\n  %s:", sv_name)
                results = get_eval_results(cur, database, schema, sv_name, run_name)
                if not results:
                    logger.info("    No eval data found")
                    continue
                metrics = compute_score(results)
                score_pass = metrics["score"] >= sv_threshold
                logger.info("    VQRs: %d total, %d scored, %d errors", metrics["total"], metrics["scored"], metrics["errors"])
                logger.info("    Score: %.1f%% (%s/%s) %s %s [%s]",
                            metrics["score"] * 100, metrics["sum_score"], metrics["scored"],
                            ">=" if score_pass else "<",
                            f"{sv_threshold:.0%}", "PASS" if score_pass else "FAIL")
                if not score_pass:
                    all_passed = False

            if not all_passed:
                logger.error("\nSV EVAL GATE: FAILED")
                sys.exit(1)
            logger.info("\nSV EVAL GATE: PASSED")
            return

        logger.info("SVs to evaluate: %s", ", ".join(sv_names))
        all_passed = True
        total_checked = 0
        # Initialize before the branch so the bottom-of-function exit logic
        # can rely on it whether we took the dry_run/single-SV path or the
        # parallel-ThreadPool path. Mirror the platform_blocked classification
        # the reporting layer (get_sv_eval_scores) uses, so a SV whose every
        # VQR hit a documented Cortex Analyst platform error (Invocation
        # failed, error code 392700, etc.) is treated as advisory rather
        # than a real threshold miss.
        platform_blocked: list[str] = []

        if args.dry_run or len(sv_names) == 1:
            for sv_name in sv_names:
                sv_run_name = f"{run_name}_{sv_name.lower()}"
                metrics = run_eval_for_sv(
                    cur, database, schema, sv_name, stage, file_format,
                    sv_run_name, args.no_wait, args.dry_run,
                )

                if metrics is None:
                    continue

                # Check platform_blocked BEFORE the generic "error" branch
                # so an orchestrator-level Cortex Analyst flake (the runner
                # returns {error: "FAILED", platform_blocked: True}) is
                # classified as advisory, not as a real eval failure.
                if metrics.get("platform_blocked"):
                    logger.warning("  %s: PLATFORM BLOCKED (advisory)", sv_name)
                    platform_blocked.append(sv_name)
                    continue

                if "error" in metrics:
                    all_passed = False
                    continue

                # Platform-blocked classification: completed but every VQR
                # produced a documented Cortex Analyst platform error. Not
                # a content regression -- a Snowflake-side issue. Don't
                # flip all_passed; surface separately.
                scored = metrics.get("scored", 0)
                errored = metrics.get("errors", 0)
                flake = metrics.get("flake_errors", 0)
                if scored == 0 and errored > 0 and flake == errored:
                    logger.warning(
                        "  %s: PLATFORM BLOCKED (advisory) -- %d/%d VQR(s) all flake errors",
                        sv_name, flake, errored,
                    )
                    platform_blocked.append(sv_name)
                    continue

                total_checked += 1
                score_pass = metrics["score"] >= sv_threshold

                logger.info("    Score: %.1f%% (%s/%s) %s %s [%s]",
                            metrics["score"] * 100, metrics["sum_score"], metrics["scored"],
                            ">="  if score_pass else "<",
                            f"{sv_threshold:.0%}", "PASS" if score_pass else "FAIL")

                if not score_pass:
                    all_passed = False
        else:
            started: list[tuple[str, str, str]] = []
            for sv_name in sv_names:
                sv_run_name = f"{run_name}_{sv_name.lower()}"
                try:
                    filename = start_sv_eval(
                        cur, database, schema, sv_name, stage, file_format, sv_run_name,
                    )
                    started.append((sv_name, sv_run_name, filename))
                except Exception as e:
                    if is_platform_blocker(e):
                        logger.warning(
                            "  [%s] PLATFORM BLOCKED (Cortex Analyst Eval PuPr bug): %s",
                            sv_name, str(e)[:200],
                        )
                        platform_blocked.append(sv_name)
                    else:
                        logger.error("  [%s] Failed to start: %s", sv_name, e)
                        all_passed = False

            if args.no_wait:
                logger.info("\nStarted %d eval(s) — use --status to check progress", len(started))
            elif not started:
                # Every SV failed to start (either platform-blocked or crashed
                # before the poll stage). Skip ThreadPoolExecutor (max_workers
                # must be >0) and let the main exit logic below classify.
                logger.info(
                    "\nNo evals successfully started (started=0, platform_blocked=%d). "
                    "Skipping poll phase.",
                    len(platform_blocked),
                )
            else:
                workers = min(args.max_parallel, len(started))
                logger.info("\nPolling %d eval(s) in parallel (workers=%d)...", len(started), workers)

                sv_metrics: dict[str, dict] = {}
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    futures = {}
                    for sv_name, sv_run_name, filename in started:
                        future = pool.submit(
                            poll_and_collect, config, database, schema,
                            sv_name, stage, filename, sv_run_name,
                        )
                        futures[future] = sv_name

                    for future in as_completed(futures):
                        sv_name = futures[future]
                        try:
                            metrics = future.result()
                        except Exception as e:
                            logger.error("  [%s] Thread error: %s", sv_name, e)
                            metrics = {"total": 0, "scored": 0, "score": 0.0, "errors": 0, "error": str(e)}
                        sv_metrics[sv_name] = metrics

                for sv_name, _, _ in started:
                    metrics = sv_metrics.get(sv_name, {})
                    if metrics.get("platform_blocked"):
                        logger.warning("  %s: PLATFORM BLOCKED (advisory)", sv_name)
                        platform_blocked.append(sv_name)
                        continue
                    if "error" in metrics:
                        logger.error("  %s: ERROR — %s", sv_name, metrics["error"])
                        all_passed = False
                        continue

                    # Same per-SV platform_blocked classification the
                    # reporting layer uses: scored=0 with all VQR errors
                    # being documented platform flakes is advisory, not
                    # a real threshold miss.
                    scored_n = metrics.get("scored", 0)
                    errored_n = metrics.get("errors", 0)
                    flake_n = metrics.get("flake_errors", 0)
                    if scored_n == 0 and errored_n > 0 and flake_n == errored_n:
                        logger.warning(
                            "  %s: PLATFORM BLOCKED (advisory) -- %d/%d VQR(s) all flake errors",
                            sv_name, flake_n, errored_n,
                        )
                        platform_blocked.append(sv_name)
                        continue

                    total_checked += 1
                    score_pass = metrics["score"] >= sv_threshold

                    logger.info("  %s: %.1f%% (%s/%s) %s %s [%s]",
                                sv_name,
                                metrics["score"] * 100, metrics["sum_score"], metrics["scored"],
                                ">=" if score_pass else "<",
                                f"{sv_threshold:.0%}", "PASS" if score_pass else "FAIL")

                    if not score_pass:
                        all_passed = False

        logger.info("\n%s", "=" * 60)
        if args.dry_run:
            logger.info("DRY RUN complete — no evals started")
        elif args.no_wait:
            logger.info("All evals started — use --status to check progress")
        elif total_checked == 0 and len(sv_names) > 0:
            # Distinguish "platform blocked every SV" from "everything crashed"
            if len(platform_blocked) == len(sv_names):
                logger.warning(
                    "SV EVAL GATE: PLATFORM BLOCKED for all %d view(s). "
                    "Snowflake Cortex Analyst Evaluations PuPr bug — the "
                    "SYSTEM_AI_OBS_ANALYST_EVAL_* optimization object is "
                    "missing / not queryable. This is a known Cortex Analyst "
                    "evaluation platform blocker. Advisory: pipeline will continue.",
                    len(sv_names),
                )
                sys.exit(EXIT_PLATFORM_BLOCKED)
            logger.warning("NO EVAL RESULTS — cannot determine pass/fail")
            sys.exit(EXIT_CRASH)
        elif all_passed:
            logger.info("SV EVAL GATE: PASSED (%d views)", total_checked)
            if platform_blocked:
                logger.warning(
                    "  NOTE: %d view(s) platform-blocked (advisory): %s",
                    len(platform_blocked), ", ".join(platform_blocked),
                )
        else:
            logger.error("SV EVAL GATE: FAILED (%d views)", total_checked)
            sys.exit(EXIT_THRESHOLD_FAIL)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
