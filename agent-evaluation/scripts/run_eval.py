#!/usr/bin/env python3
"""
Run a Cortex Agent evaluation end-to-end.

Reads a config YAML, loads questions (from YAML or CSV) into Snowflake,
generates the Snowflake evaluation YAML, uploads it to a stage, and starts the run.
Polls until complete, checks thresholds, and saves JSON results.

Supports two question formats:
  - YAML (recommended): datasets/agent_eval.yaml  (structured: expected_tools, category, tags, validation_query)
  - CSV  (simple):      datasets/agent_eval.csv   (flat: target_tool, question, ground_truth, test_type)

Usage:
    python scripts/run_eval.py configs/resort_executive.yaml --dry-run

    python scripts/run_eval.py configs/resort_executive.yaml --connection myconn

    python scripts/run_eval.py configs/resort_executive.yaml --no-wait --connection myconn

    python scripts/run_eval.py configs/resort_executive.yaml --env dev --connection myconn

    python scripts/run_eval.py configs/resort_executive.yaml --status --connection myconn

    python scripts/run_eval.py configs/resort_executive.yaml --results --connection myconn

    python scripts/run_eval.py configs/resort_executive.yaml --results --connection myconn --category revenue
"""

import argparse
import csv
import json
import os
import sys
import time
import tomllib
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import snowflake.connector

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from agent_management.paths import eval_dir
from agent_management.utils.config import load_env_config

try:
    import yaml
except ImportError:
    print("PyYAML is required. Install with: uv add pyyaml")
    sys.exit(1)

POLL_INTERVAL_SECONDS = 30
MAX_POLL_ATTEMPTS = 60


def load_config(config_path: str) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def resolve_dataset_path(config_path: str, relative_path: str) -> str:
    config_dir = Path(config_path).parent.parent
    return str(config_dir / relative_path)


def load_questions(dataset_path: str, category: str = None, tags: list = None) -> list[dict]:
    path = Path(dataset_path)

    if path.suffix in (".yaml", ".yml"):
        with open(path) as f:
            data = yaml.safe_load(f)
        questions = []
        for q in data.get("questions", []):
            if not q.get("question", "").strip():
                continue
            questions.append({
                "question": q["question"].strip(),
                "ground_truth": q.get("ground_truth", "").strip(),
                "expected_tools": q.get("expected_tools", []),
                "category": q.get("category", ""),
                "tags": q.get("tags", []),
                "test_type": q.get("test_type", "in_scope"),
                "validation_query": q.get("validation_query", "").strip(),
                "answer_template": q.get("answer_template", "").strip(),
            })
    elif path.suffix == ".csv":
        questions = []
        with open(path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if not row.get("question", "").strip():
                    continue
                questions.append({
                    "question": row["question"].strip(),
                    "ground_truth": row.get("ground_truth", "").strip(),
                    "expected_tools": [row["target_tool"]] if row.get("target_tool") else [],
                    "category": row.get("category", ""),
                    "tags": [],
                    "test_type": row.get("test_type", "in_scope"),
                    "validation_query": "",
                })
    else:
        print(f"Error: Unsupported dataset format: {path.suffix} (use .yaml or .csv)")
        sys.exit(1)

    if category:
        questions = [q for q in questions if q["category"] == category]
    if tags:
        tag_set = set(tags)
        questions = [q for q in questions if tag_set.intersection(q["tags"])]

    return questions


def resolve_dynamic_ground_truth(cursor, questions: list[dict]) -> list[dict]:
    resolved = 0
    failed = 0
    for q in questions:
        vq = q.get("validation_query", "").strip()
        tmpl = q.get("answer_template", "").strip()
        if not vq or not tmpl:
            continue
        try:
            cursor.execute(vq)
            cols = [desc[0].lower() for desc in cursor.description]
            rows = cursor.fetchall()
            if rows:
                parts = []
                for row in rows:
                    row_dict = {}
                    for col, val in zip(cols, row):
                        if isinstance(val, Decimal):
                            row_dict[col] = float(val)
                        elif isinstance(val, (int, float)):
                            row_dict[col] = val
                        else:
                            row_dict[col] = str(val) if val is not None else ""
                    parts.append(tmpl.format_map(row_dict))
                q["ground_truth"] = " ".join(parts)
                resolved += 1
            else:
                print(f"    WARN: validation_query returned no rows for: {q['question'][:60]}")
                failed += 1
        except Exception as e:
            print(f"    WARN: validation_query failed for: {q['question'][:60]}")
            print(f"           {e}")
            failed += 1

    empty_gt = [q for q in questions if not q.get("ground_truth", "").strip()]
    if empty_gt:
        print(f"    WARN: {len(empty_gt)} question(s) have empty ground_truth (will score 0% on answer_correctness)")
        for q in empty_gt:
            print(f"           - {q['question'][:70]}")

    print(f"  Dynamic ground truth: {resolved} resolved, {failed} failed, {len(questions) - resolved - failed} static")
    return questions


def load_questions_to_snowflake(cursor, questions: list[dict], target_table: str):
    print(f"  Questions: {len(questions)} loaded")

    cursor.execute(f"""
        CREATE OR REPLACE TABLE {target_table} (
            input_query VARCHAR,
            output VARIANT
        )
    """)

    for q in questions:
        q_escaped = q["question"].replace("'", "''")
        gt = q["ground_truth"]
        gt_escaped = (
            gt.replace("\\", "\\\\")
            .replace("'", "\\'")
            .replace('"', '\\"')
        )
        cursor.execute(f"""
            INSERT INTO {target_table} (input_query, output)
            SELECT
                '{q_escaped}',
                PARSE_JSON('{{"ground_truth_output": "{gt_escaped}"}}')
        """)

    cursor.execute(f"SELECT COUNT(*) FROM {target_table}")
    count = cursor.fetchone()[0]
    print(f"  Table: {target_table} ({count} rows)")
    return count


def generate_snowflake_yaml(config: dict, dataset_name: str) -> str:
    agent = config["agent"]
    fq_agent = f'{agent["database"]}.{agent["schema"]}.{agent["name"]}'
    # NOTE: EXECUTE_AI_EVALUATION does NOT accept agent_name!<alias> selectors
    # (verified against Snowflake 10.14.103). Eval always runs against the
    # default version (= most recent committed). If the caller supplied
    # --alias or --version, we surface a warning. In practice this is fine
    # because right after a deploy, the new version IS the default — so
    # evaluating "validated" is equivalent to evaluating the default until
    # the next deploy shifts the default forward.
    selector = agent.get("version") or agent.get("alias")
    if selector:
        import sys as _sys
        print(
            f"[WARN] EXECUTE_AI_EVALUATION ignores version/alias selectors; "
            f"evaluating DEFAULT version on {fq_agent} "
            f"(requested selector '{selector}' is informational only).",
            file=_sys.stderr,
        )
    fq_table = config["dataset"]["snowflake_table"]
    eval_cfg = config.get("evaluation", {})

    metrics_section = []
    for m in config.get("metrics", []):
        if isinstance(m, str):
            metrics_section.append(f'  - "{m}"')
        elif isinstance(m, dict):
            metrics_section.append(f'  - name: "{m["name"]}"')
            if "score_ranges" in m:
                metrics_section.append("    score_ranges:")
                for k, v in m["score_ranges"].items():
                    metrics_section.append(f"      {k}: {v}")
            if "prompt" in m:
                metrics_section.append("    prompt: |")
                for line in m["prompt"].rstrip().split("\n"):
                    metrics_section.append(f"      {line}")

    return f"""dataset:
  dataset_type: "CORTEX AGENT"
  table_name: "{fq_table}"
  dataset_name: "{dataset_name}"
  column_mapping:
    query_text: "INPUT_QUERY"
    ground_truth: "OUTPUT"

evaluation:
  agent_params:
    agent_name: "{fq_agent}"
    agent_type: "CORTEX AGENT"
  run_params:
    label: "{eval_cfg.get('label', f'{agent["name"]} evaluation')}"
    description: "{eval_cfg.get('description', 'Automated evaluation')}"
  source_metadata:
    type: "dataset"
    dataset_name: "{dataset_name}"

metrics:
{chr(10).join(metrics_section)}
"""


def ensure_stage(cursor, config: dict):
    sf = config["snowflake"]
    stage = sf["stage"]
    ff = sf["file_format"]

    cursor.execute(f"""
        CREATE FILE FORMAT IF NOT EXISTS {ff}
          TYPE = 'CSV'
          FIELD_DELIMITER = NONE
          RECORD_DELIMITER = '\\n'
          SKIP_HEADER = 0
          FIELD_OPTIONALLY_ENCLOSED_BY = NONE
          ESCAPE_UNENCLOSED_FIELD = NONE
    """)

    cursor.execute(f"""
        CREATE STAGE IF NOT EXISTS {stage}
          FILE_FORMAT = {ff}
    """)
    print(f"  Stage: {stage}")


def upload_yaml(cursor, yaml_content: str, stage: str, filename: str):
    escaped = yaml_content.replace("'", "''")
    cursor.execute(f"""
        COPY INTO @{stage}/{filename}
        FROM (SELECT '{escaped}')
        FILE_FORMAT = (TYPE = 'CSV' FIELD_DELIMITER = NONE RECORD_DELIMITER = NONE COMPRESSION = NONE)
        SINGLE = TRUE
        OVERWRITE = TRUE
    """)
    print(f"  Uploaded: @{stage}/{filename}")


def start_eval(cursor, run_name: str, stage: str, filename: str):
    cursor.execute(f"""
        CALL EXECUTE_AI_EVALUATION(
            'START',
            OBJECT_CONSTRUCT('run_name', '{run_name}'),
            '@{stage}/{filename}'
        )
    """)
    print(f"  Run started: {run_name}")


def check_status(cursor, run_name: str, stage: str, filename: str):
    cursor.execute(f"""
        CALL EXECUTE_AI_EVALUATION(
            'STATUS',
            OBJECT_CONSTRUCT('run_name', '{run_name}'),
            '@{stage}/{filename}'
        )
    """)
    row = cursor.fetchone()
    print(f"  Run:    {row[0]}")
    print(f"  Agent:  {row[1]}")
    print(f"  Status: {row[3]}")
    if row[4]:
        print(f"  Detail: {row[4]}")
    return row[3]


def show_results(cursor, config: dict, run_name: str, category: str = None):
    agent = config["agent"]

    where_clause = ""
    if category:
        dataset_path = config["dataset"].get("questions", config["dataset"].get("local_csv", ""))
        if dataset_path.endswith((".yaml", ".yml")):
            base_dir = Path(config.get("_config_path", "")).parent.parent
            questions = load_questions(str(base_dir / dataset_path), category=category)
            q_list = [q["question"] for q in questions]
            if q_list:
                escaped = [q.replace("'", "''") for q in q_list]
                in_clause = ", ".join(f"'{q}'" for q in escaped)
                where_clause = f"WHERE INPUT IN ({in_clause})"
                print(f"  Filtering to category: {category} ({len(q_list)} questions)")

    cursor.execute(f"""
        SELECT
            METRIC_NAME,
            ROUND(AVG(EVAL_AGG_SCORE), 4) AS avg_score,
            COUNT(*) AS record_count,
            SUM(CASE WHEN EVAL_AGG_SCORE >= 0.8 THEN 1 ELSE 0 END) AS high,
            SUM(CASE WHEN EVAL_AGG_SCORE < 0.3 THEN 1 ELSE 0 END) AS low
        FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(
            '{agent["database"]}', '{agent["schema"]}', '{agent["name"]}',
            'CORTEX AGENT', '{run_name}'
        ))
        {where_clause}
        GROUP BY METRIC_NAME
    """)

    print(f"\n{'Metric':<25} {'Avg':>8} {'Count':>6} {'High':>6} {'Low':>6}")
    print("-" * 55)
    for row in cursor.fetchall():
        metric = str(row[0]) if row[0] is not None else "unknown"
        score_pct = f"{float(row[1])*100:.1f}%" if row[1] is not None else "N/A"
        cnt = int(row[2]) if row[2] is not None else 0
        high = int(row[3]) if row[3] is not None else 0
        low = int(row[4]) if row[4] is not None else 0
        print(f"{metric:<25} {score_pct:>8} {cnt:>6} {high:>6} {low:>6}")

    cursor.execute(f"""
        SELECT
            LEFT(INPUT, 70) AS question,
            METRIC_NAME,
            ROUND(EVAL_AGG_SCORE, 2) AS score
        FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(
            '{agent["database"]}', '{agent["schema"]}', '{agent["name"]}',
            'CORTEX AGENT', '{run_name}'
        ))
        {where_clause}
        ORDER BY METRIC_NAME, EVAL_AGG_SCORE ASC
    """)

    print(f"\n  {'Score':>5}  {'Metric':<22} Question")
    print(f"  {'-----':>5}  {'------':<22} --------")
    for row in cursor.fetchall():
        score = f"{row[2]:.2f}" if row[2] is not None else "  N/A"
        metric = row[1] or "unknown"
        question = row[0] or "(no question)"
        print(f"  {score:>5}  {metric:<22} {question}")

    cursor.execute(
        "SELECT LOWER(CURRENT_ORGANIZATION_NAME()), LOWER(CURRENT_ACCOUNT_NAME())"
    )
    org, account = cursor.fetchone()
    url = (
        f"https://app.snowflake.com/{org}/{account}/#/agents"
        f"/database/{agent['database']}/schema/{agent['schema']}"
        f"/agent/{agent['name']}/evaluations/{run_name}/records"
    )
    print(f"\nSnowsight: {url}")


def poll_until_done(cursor, run_name: str, stage: str, filename: str, poll_interval: int = POLL_INTERVAL_SECONDS) -> tuple[str, str]:
    """Poll EXECUTE_AI_EVALUATION until it reaches a terminal status.

    Returns ``(status, status_details)`` where ``status`` is one of:
      - ``"COMPLETED"``                 -> eval finished successfully
      - ``"FAILED: <terminal_token>"``  -> orchestrator gave up
      - ``"TIMEOUT"``                   -> we ran out of poll attempts

    ``status_details`` is the orchestrator's STATUS_DETAILS column (empty
    string when absent). Surfacing it lets callers distinguish a transient
    Cortex platform flake (``Invocation failed``) from a genuine eval engine
    error so the caller can decide whether to retry.
    """
    # Snowflake reports a sequence of statuses for Cortex Agent evals:
    #   CREATED -> INVOCATION_IN_PROGRESS -> INVOCATION_COMPLETED ->
    #   (metric computation, async) -> COMPLETED
    # Substring-matching "COMPLETED" inside "INVOCATION_COMPLETED" exits the
    # loop one phase too early - the LLM judge has not written metric_name
    # yet, so fetch_results() returns rows with NULL metrics and the eval
    # looks "malformed". Use exact-match against the documented terminal
    # tokens; everything else is transient and we keep polling.
    TERMINAL_OK = {"COMPLETED", "SUCCEEDED", "DONE"}
    TERMINAL_FAIL = {
        "FAILED", "ERROR", "CANCELLED",
        # Real terminal failure modes from EXECUTE_AI_EVALUATION; keep so we
        # bail fast on a genuine error instead of polling for 30 minutes.
        "INVOCATION_FAILED", "INVOCATION_ERROR",
    }
    last_details = ""
    for attempt in range(1, MAX_POLL_ATTEMPTS + 1):
        cursor.execute(f"""
            CALL EXECUTE_AI_EVALUATION(
                'STATUS',
                OBJECT_CONSTRUCT('run_name', '{run_name}'),
                '@{stage}/{filename}'
            )
        """)
        rows = cursor.fetchall()
        if rows:
            col_names = [d[0].upper() for d in cursor.description]
            if "STATUS" in col_names:
                status_str = str(rows[0][col_names.index("STATUS")]).upper()
            elif len(rows[0]) > 3:
                status_str = str(rows[0][3]).upper()
            else:
                status_str = str(rows[0][0]).upper()

            details_raw = ""
            if "STATUS_DETAILS" in col_names:
                details_raw = rows[0][col_names.index("STATUS_DETAILS")] or ""
            elif len(rows[0]) > 4:
                details_raw = rows[0][4] or ""
            last_details = _flatten_status_details(details_raw)

            print(f"  [{attempt:02d}] Status: {status_str}" + (
                f"  ({last_details})" if last_details else ""
            ))

            if status_str in TERMINAL_OK:
                return "COMPLETED", last_details
            if status_str in TERMINAL_FAIL:
                return f"FAILED: {status_str}", last_details

        time.sleep(poll_interval)

    return "TIMEOUT", last_details


# Cortex platform-level transient signatures. When the orchestrator reports
# FAILED with one of these in STATUS_DETAILS, retrying the run usually
# succeeds; the failure is not in our spec or our questions. Mirrors the
# `_PLATFORM_BLOCKER_PATTERNS` in agent_management/evals/sv_runner.py.
#
# IMPORTANT: only retry signatures that happen BEFORE Cortex creates its
# internal `SYSTEM_AI_OBS_CORTEX_AGENT_DATASET_VERSION_DO_NOT_DELETE` object
# (i.e. during INVOCATION_IN_PROGRESS or earlier). Once that object exists,
# `EXECUTE_AI_EVALUATION('START', ...)` rejects any retry with error 210007
# (`Dataset version ... already exists`) until Cortex cleans it up. Failures
# that happen during COMPUTATION_IN_PROGRESS (metric judge timeouts) hit
# this constraint on retry and CANNOT be auto-recovered. They are intentionally
# excluded so we surface the real signal instead of crashing on retry.
_RETRYABLE_DETAIL_PATTERNS = (
    "invocation failed",
    "service is currently unavailable",
    "internal error",
    # Generic transients that can occur in either phase. Kept because some
    # invocation-phase failures surface this way, and the START guard below
    # turns the post-COMPUTATION variant into a clean message rather than
    # a crash.
    "timed out",
    "timeout",
    "rate limit",
)

# Cortex error code emitted when EXECUTE_AI_EVALUATION('START', ...) hits
# the dataset-version uniqueness constraint after a previous failed run.
# Treat as a hard "do not retry again" signal: surface the original failure.
_DATASET_VERSION_LOCK_ERROR_CODE = "210007"


def _flatten_status_details(raw) -> str:
    """Render STATUS_DETAILS as a single readable line.

    Snowflake's `EXECUTE_AI_EVALUATION('STATUS', ...)` returns STATUS_DETAILS
    as either a plain string ("Invocation failed") or a JSON-encoded array
    (`'[\\n  "Metric \\'logical_consistency\\' failed"\\n]'`). The raw repr
    is unreadable in CI logs because of embedded newlines and quoting.
    Flatten arrays into ``"; "``-joined items so the per-poll log line and
    the failure summary stay legible.

    Pure function so the rendering and pattern-match surface is testable.
    """
    if raw is None or raw == "":
        return ""
    if isinstance(raw, (list, tuple)):
        return "; ".join(str(x) for x in raw if x)
    text = str(raw).strip()
    if text.startswith("[") and text.endswith("]"):
        try:
            import json
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return "; ".join(str(x) for x in parsed if x)
        except (json.JSONDecodeError, ValueError):
            pass
    return text


def is_retryable_failure(status_details) -> bool:
    """True if the FAILED status_details looks like a transient platform flake.

    Pure function so it is unit-testable without spinning up a real eval.
    Returns False for empty/None details (no signal == do not retry).
    Accepts string or list/tuple from the Snowflake driver.
    """
    flat = _flatten_status_details(status_details)
    if not flat:
        return False
    msg = flat.lower()
    return any(pat in msg for pat in _RETRYABLE_DETAIL_PATTERNS)


def fetch_results(cursor, agent: dict, run_name: str,
                  retry_on_empty: int = 2, retry_sleep: int = 30) -> list[dict]:
    """Fetch eval results, retrying briefly if metrics are missing.

    Even when STATUS=COMPLETED, GET_AI_EVALUATION_DATA can briefly trail
    by a few seconds before metric_name is populated on every row. A naive
    single fetch occasionally returns rows-with-no-metrics on slow accounts,
    poisoning the threshold check. Retry up to retry_on_empty times if we
    see rows but no metric_name set anywhere - that's the only failure
    mode we want to retry; a real empty result (truly 0 rows) bails out
    immediately so we surface the genuine error.
    """
    last_rows: list[dict] = []
    for attempt in range(retry_on_empty + 1):
        cursor.execute(f"""
            SELECT * FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(
                '{agent["database"]}', '{agent["schema"]}', '{agent["name"]}',
                'CORTEX AGENT', '{run_name}'
            ))
        """)
        columns = [d[0].lower() for d in cursor.description]
        last_rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        # If any row has a non-NULL metric_name we have real data.
        if last_rows and any(r.get("metric_name") for r in last_rows):
            return last_rows
        # No rows at all - genuine empty, no point retrying.
        if not last_rows:
            return last_rows
        # Rows present but every metric_name is NULL - metric scoring lagging.
        if attempt < retry_on_empty:
            print(
                f"  [retry {attempt + 1}/{retry_on_empty}] {len(last_rows)} rows "
                f"returned but no metric_name yet; sleeping {retry_sleep}s..."
            )
            time.sleep(retry_sleep)
    return last_rows


def fetch_errors(cursor, agent: dict, run_name: str) -> list[dict]:
    cursor.execute(f"""
        SELECT * FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_OBSERVABILITY_LOGS(
            '{agent["database"]}', '{agent["schema"]}', '{agent["name"]}',
            'CORTEX AGENT'
        ))
        WHERE record:"severity_text" IN ('ERROR', 'WARN')
          AND record_attributes:"snow.ai.observability.run.name" = '{run_name}'
    """)
    columns = [d[0].lower() for d in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def compute_summary(results: list[dict]) -> dict[str, dict]:
    metrics: dict[str, list[float]] = {}
    for row in results:
        metric_name = row.get("metric_name")
        score = row.get("eval_agg_score")
        if metric_name and score is not None:
            try:
                metrics.setdefault(metric_name, []).append(float(score))
            except (TypeError, ValueError):
                pass
    return {
        name: {"avg": sum(scores) / len(scores), "n": len(scores)}
        for name, scores in metrics.items()
    }


def check_thresholds(summary: dict[str, dict], thresholds: dict[str, float]) -> bool:
    # If no metrics were computed at all, something went wrong (e.g.,
    # METRIC_NAME returned NULL for every row). A silent pass here hides
    # real breakage — treat empty summary against any configured threshold
    # as a failure.
    if thresholds and not summary:
        print("  ERROR: no metrics present in results; eval likely malformed")
        return False
    passed = True
    checked = 0
    for metric, threshold in thresholds.items():
        if metric not in summary:
            print(f"  {metric:25s} MISSING (threshold {threshold:.2f}) [FAIL]")
            passed = False
            continue
        avg = summary[metric]["avg"]
        ok = avg >= threshold
        status = "PASS" if ok else "FAIL"
        print(f"  {metric:25s} {avg:.3f}  (threshold: {threshold:.2f})  [{status}]")
        if not ok:
            passed = False
        checked += 1
    if thresholds and checked == 0:
        print("  ERROR: no configured threshold matched any reported metric")
        return False
    return passed


def save_results_json(config: dict, run_name: str, summary: dict, results: list[dict], thresholds: dict, passed: bool) -> Path:
    results_dir = eval_dir() / "results"
    results_dir.mkdir(exist_ok=True)
    agent_name = config["agent"]["name"].lower()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = results_dir / f"{agent_name}_{ts}.json"
    output_file.write_text(
        json.dumps(
            {
                "agent": config["agent"]["name"],
                "run_name": run_name,
                "timestamp": ts,
                "summary": summary,
                "thresholds": thresholds,
                "passed": passed,
                "total_records": len(results),
                "results": results,
            },
            indent=2,
            default=str,
        )
        + "\n"
    )
    return output_file



def _connect(args, env_config: dict = None):
    """Open a Snowflake connection via SnowflakeConfig.

    Hard-fails with ConfigError if role/warehouse/database cannot be resolved
    from (kwargs > env vars > env_config yaml). Never silently falls back to
    the authenticating user's DEFAULT_ROLE — that bug is why this function
    was rewritten (MCP_OPERATOR crash on every PROD eval).
    """
    # Import locally to keep module import-time light for non-connecting code paths.
    try:
        from agent_management.snowflake_config import SnowflakeConfig, connect as _connect_cfg
    except ImportError:
        # Fallback only if agent_management package isn't importable (rare —
        # indicates PYTHONPATH is misconfigured). Preserve old behaviour so
        # error messages are familiar.
        import sys as _sys
        print("ERROR: agent_management.snowflake_config not importable. "
              "Set PYTHONPATH to repo root.", file=_sys.stderr)
        _sys.exit(2)

    sf = (env_config or {}).get("snowflake", {}) or {}
    deploy = (env_config or {}).get("deployment", {}) or {}

    cfg = SnowflakeConfig.resolve(
        env=getattr(args, "env", None),
        account=getattr(args, "account", None) or sf.get("account"),
        user=getattr(args, "user", None) or sf.get("user"),
        role=sf.get("role"),  # run_eval.py has no --role flag; rely on yaml/env
        warehouse=sf.get("warehouse") or deploy.get("warehouse"),
        database=deploy.get("database"),
        schema=deploy.get("schema"),
        connection_name=getattr(args, "connection", None),
        private_key_path=getattr(args, "private_key_path", None) or sf.get("private_key_path"),
    )
    return _connect_cfg(cfg)


def main():
    parser = argparse.ArgumentParser(description="Run a Cortex Agent evaluation")
    parser.add_argument("config", help="Path to eval config YAML")
    parser.add_argument(
        "--connection",
        default=os.getenv("SNOWFLAKE_CONNECTION_NAME"),
        help="Snowflake connection name (from connections.toml)",
    )
    parser.add_argument(
        "--account",
        default=os.getenv("SNOWFLAKE_ACCOUNT"),
        help="Snowflake account (alternative to --connection)",
    )
    parser.add_argument(
        "--user",
        default=os.getenv("SNOWFLAKE_USER"),
        help="Snowflake user (used with --account)",
    )
    parser.add_argument(
        "--private-key-path",
        default=os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH"),
        help="Path to private key file (used with --account)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show plan without executing")
    parser.add_argument("--resolve-only", action="store_true", help="Resolve dynamic ground truth and print results (no eval)")
    parser.add_argument("--status", action="store_true", help="Check status of last run")
    parser.add_argument("--results", action="store_true", help="Show results of last run")
    parser.add_argument("--run-name", help="Override run name (default: auto-generated)")
    parser.add_argument("--category", help="Filter questions by category")
    parser.add_argument("--tag", action="append", dest="tags", help="Filter questions by tag (repeatable)")
    parser.add_argument("--no-wait", action="store_true", help="Start evaluation and exit without polling")
    parser.add_argument("--poll-interval", type=int, default=POLL_INTERVAL_SECONDS, help=f"Seconds between status polls (default: {POLL_INTERVAL_SECONDS})")
    parser.add_argument("--env", choices=["dev", "prod"], help="Load environment config from environments/<env>.env.yml")
    parser.add_argument("--alias", help="Agent alias selector (validated, production, latest).")
    parser.add_argument("--version", help="Explicit VERSION$N selector (takes precedence over --alias).")

    args = parser.parse_args()
    config = load_config(args.config)
    config["_config_path"] = args.config

    env_config = None
    if args.env:
        env_config = load_env_config(args.env)
        deploy = env_config.get("deployment", {})
        suffix = (env_config.get("agent", {}).get("name_suffix", "")
                  or env_config.get("settings", {}).get("version_suffix", ""))
        if deploy.get("database"):
            config["agent"]["database"] = deploy["database"]
        if deploy.get("schema"):
            config["agent"]["schema"] = deploy["schema"]
        if suffix:
            base_name = config["agent"]["name"]
            if not base_name.endswith(suffix.upper()):
                config["agent"]["name"] = base_name + suffix.upper()
        if deploy.get("warehouse"):
            config.setdefault("snowflake", {})["warehouse"] = deploy["warehouse"]

    # Agent Versioning selector: prefer explicit --version, then --alias, then
    # env's agent.deploy_alias (so main-merge runs auto-target 'validated').
    if args.version:
        config["agent"]["version"] = args.version
    elif args.alias:
        config["agent"]["alias"] = args.alias
    elif env_config:
        env_deploy_alias = env_config.get("agent", {}).get("deploy_alias")
        if env_deploy_alias:
            config["agent"]["alias"] = env_deploy_alias

    agent = config["agent"]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_name = args.run_name or f"{agent['name'].lower()}_eval_{timestamp}"
    dataset_name = f"{agent['database']}.{agent['schema']}.{agent['name']}_EVAL_DS_{timestamp}"
    stage = config["snowflake"]["stage"]
    sf_yaml_filename = f"{agent['name'].lower()}_eval_{timestamp}.yaml"
    thresholds = config.get("thresholds", {})

    dataset_relative = config["dataset"].get("questions", config["dataset"].get("local_csv", ""))
    dataset_path = resolve_dataset_path(args.config, dataset_relative)

    questions = load_questions(dataset_path, category=args.category, tags=args.tags)

    if args.dry_run:
        print("=== DRY RUN ===\n")
        print(f"Config:     {args.config}")
        print(f"Agent:      {agent['database']}.{agent['schema']}.{agent['name']}")
        print(f"Dataset:    {dataset_path}")
        print(f"Table:      {config['dataset']['snowflake_table']}")
        print(f"Stage:      {stage}")
        print(f"Run name:   {run_name}")
        print(f"SF Dataset: {dataset_name}")
        print(f"Metrics:    {[m if isinstance(m, str) else m['name'] for m in config.get('metrics', [])]}")
        if args.category:
            print(f"Category:   {args.category}")
        if args.tags:
            print(f"Tags:       {args.tags}")

        categories = {}
        for q in questions:
            cat = q.get("category", "uncategorized")
            categories.setdefault(cat, []).append(q)

        print(f"\nQuestions ({len(questions)}):")
        dynamic_count = sum(1 for q in questions if q.get("validation_query"))
        static_count = len(questions) - dynamic_count
        print(f"  ({dynamic_count} dynamic via validation_query, {static_count} static)")
        for cat, qs in sorted(categories.items()):
            print(f"\n  [{cat}] ({len(qs)} questions)")
            for i, q in enumerate(qs, 1):
                tools = ", ".join(q.get("expected_tools", [])) or "—"
                tt = q.get("test_type", "in_scope")
                gt_type = "dynamic" if q.get("validation_query") else "static"
                print(f"    {i}. [{tt}] [{gt_type}] {q['question'][:55]}")
                print(f"       Tools: {tools}")

        print("\nGenerated Snowflake YAML:")
        print("-" * 40)
        print(generate_snowflake_yaml(config, dataset_name))
        return

    conn = _connect(args, env_config=env_config)
    cursor = conn.cursor()

    try:
        wh = config.get("snowflake", {}).get("warehouse")
        if wh:
            cursor.execute(f"USE WAREHOUSE {wh}")

        if args.resolve_only:
            cursor.execute(f"USE DATABASE {agent['database']}")
            cursor.execute(f"USE SCHEMA {agent['schema']}")
            print("=== RESOLVE DYNAMIC GROUND TRUTH ===\n")
            questions = resolve_dynamic_ground_truth(cursor, questions)
            for i, q in enumerate(questions, 1):
                gt_type = "DYNAMIC" if q.get("validation_query") else "STATIC"
                print(f"\n{i}. [{gt_type}] {q['question']}")
                print(f"   Ground truth: {q['ground_truth'][:120]}")
            return

        if args.status:
            cursor.execute(f"USE DATABASE {agent['database']}")
            cursor.execute(f"USE SCHEMA {agent['schema']}")
            cursor.execute(f"LIST @{stage}")
            files = [r[0] for r in cursor.fetchall()]
            yaml_files = [f for f in files if f.endswith(".yaml")]
            if not yaml_files:
                print("No evaluation configs found on stage.")
                return
            latest = sorted(yaml_files)[-1]
            fname = latest.split("/")[-1]
            rn = args.run_name or fname.replace(".yaml", "")
            check_status(cursor, rn, stage, fname)
            return

        if args.results:
            cursor.execute(f"USE DATABASE {agent['database']}")
            cursor.execute(f"USE SCHEMA {agent['schema']}")
            cursor.execute(f"LIST @{stage}")
            files = [r[0] for r in cursor.fetchall()]
            yaml_files = sorted([f for f in files if f.endswith(".yaml")])
            if not yaml_files:
                print("No evaluation configs found on stage.")
                return
            latest = yaml_files[-1]
            fname = latest.split("/")[-1]
            rn = args.run_name or fname.replace(".yaml", "")
            show_results(cursor, config, rn, category=args.category)
            return

        if not questions:
            print("Error: No questions found (check dataset path, category, or tag filters)")
            sys.exit(1)

        print(f"=== Evaluating {agent['name']} ===\n")

        cursor.execute(f"USE DATABASE {agent['database']}")
        cursor.execute(f"USE SCHEMA {agent['schema']}")

        print("1. Resolving dynamic ground truth...")
        questions = resolve_dynamic_ground_truth(cursor, questions)

        print("\n2. Loading questions into Snowflake...")
        load_questions_to_snowflake(
            cursor, questions, config["dataset"]["snowflake_table"]
        )

        print("\n3. Setting up stage...")
        ensure_stage(cursor, config)

        print("\n4. Generating and uploading Snowflake YAML...")
        sf_yaml = generate_snowflake_yaml(config, dataset_name)
        upload_yaml(cursor, sf_yaml, stage, sf_yaml_filename)

        print("\n5. Starting evaluation...")
        start_eval(cursor, run_name, stage, sf_yaml_filename)

        conn_args = ""
        if args.connection:
            conn_args = f"--connection {args.connection}"
        elif args.account:
            conn_args = f"--account {args.account} --user {args.user} --private-key-path {args.private_key_path}"

        if args.no_wait:
            print(f"\n  --no-wait: evaluation started. Check later with:")
            print(f"  python scripts/run_eval.py {args.config} --status --run-name {run_name} {conn_args}")
            return

        print(f"\n6. Polling every {args.poll_interval}s (max {MAX_POLL_ATTEMPTS} attempts)...")
        final_status, status_details = poll_until_done(cursor, run_name, stage, sf_yaml_filename, poll_interval=args.poll_interval)

        # Retry once on transient platform flakes (Invocation failed,
        # service unavailable, internal error). Same retry policy used by
        # agent_management/evals/sv_runner.py and deploy-prod-validated.yml.
        # A retry uses a fresh run_name so the orchestrator does not see a
        # stale FAILED record on STATUS calls.
        if "FAILED" in final_status and is_retryable_failure(status_details):
            retry_run_name = f"{run_name}-r1"
            retry_filename = sf_yaml_filename.replace(run_name, retry_run_name) \
                if run_name in sf_yaml_filename else f"{retry_run_name}.yaml"
            print(
                f"\n  Eval reported transient platform flake "
                f"(STATUS_DETAILS={status_details!r}); retrying once as {retry_run_name}..."
            )
            sf_yaml_retry = generate_snowflake_yaml(config, dataset_name)
            try:
                upload_yaml(cursor, sf_yaml_retry, stage, retry_filename)
                start_eval(cursor, retry_run_name, stage, retry_filename)
            except Exception as exc:  # noqa: BLE001 - guarded retry
                # Cortex error 210007 means the original run created an
                # internal dataset version object that has not been cleaned
                # up. The platform refuses to start a retry until it does.
                # Surface the original failure cleanly instead of crashing.
                msg = str(exc)
                if _DATASET_VERSION_LOCK_ERROR_CODE in msg or \
                        "DATASET_VERSION_DO_NOT_DELETE" in msg:
                    print(
                        f"\n  Retry blocked by Cortex internal dataset lock "
                        f"(error {_DATASET_VERSION_LOCK_ERROR_CODE}). "
                        f"Treating original failure as final."
                    )
                    # final_status already set from the first poll; skip retry poll.
                else:
                    print(f"\n  Retry start failed: {exc}")
                    raise
            else:
                final_status, status_details = poll_until_done(cursor, retry_run_name, stage, retry_filename, poll_interval=args.poll_interval)
                if "FAILED" not in final_status and "TIMEOUT" not in final_status:
                    run_name = retry_run_name
                    sf_yaml_filename = retry_filename

        if "FAILED" in final_status or "TIMEOUT" in final_status:
            print(f"\n  Evaluation did not complete: {final_status}")
            if status_details:
                print(f"  STATUS_DETAILS: {status_details}")
            errors = fetch_errors(cursor, agent, run_name)
            if errors:
                print(f"\n  Errors/warnings ({len(errors)}):")
                for e in errors[:5]:
                    print(f"    {e}")
            sys.exit(1)

        print("\n7. Fetching results...")
        results = fetch_results(cursor, agent, run_name)
        summary = compute_summary(results)

        n_records = len({r.get("record_id") for r in results if r.get("record_id")})
        print(f"\n{'=' * 60}")
        print(f"EVALUATION RESULTS — {agent['name']}")
        print(f"Run: {run_name}  |  Records: {n_records}")
        print(f"{'=' * 60}")
        for metric, stats in sorted(summary.items()):
            print(f"  {metric:25s} {stats['avg']:.3f}  (n={stats['n']:3d})")

        errors = fetch_errors(cursor, agent, run_name)
        if errors:
            print(f"\n  Errors/warnings: {len(errors)}")
            for e in errors[:3]:
                print(f"    {e}")

        passed = True
        if thresholds:
            print(f"\n{'=' * 60}")
            print("THRESHOLD CHECK")
            print(f"{'=' * 60}")
            passed = check_thresholds(summary, thresholds)
            overall = "PASSED" if passed else "FAILED"
            print(f"\n  Overall: {overall}")

        output_file = save_results_json(config, run_name, summary, results, thresholds, passed)
        print(f"  Results saved: {output_file}")

        show_results(cursor, config, run_name, category=args.category)

        sys.exit(0 if passed else 1)

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
