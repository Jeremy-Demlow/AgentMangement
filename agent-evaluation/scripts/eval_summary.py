"""Query the latest DEV evaluation results and output a summary.

Used by validate-pr.yml to surface DEV eval results on PRs targeting main.
Outputs a markdown summary to GITHUB_STEP_SUMMARY and exits non-zero if any
agent's latest eval run failed its thresholds.

Usage (CI):
    python -m agent_evaluation.scripts.eval_summary --env dev

    python agent-evaluation/scripts/eval_summary.py --env dev \
        --account $SNOWFLAKE_ACCOUNT --user $SNOWFLAKE_USER \
        --private-key-path /tmp/snowflake_key.p8
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tomllib
from pathlib import Path

import snowflake.connector
import yaml


def load_env_config(env: str) -> dict:
    env_file = Path(__file__).resolve().parents[2] / "environments" / f"{env}.env.yml"
    if not env_file.exists():
        print(f"ERROR: Environment config not found: {env_file}")
        sys.exit(1)
    return yaml.safe_load(env_file.read_text())


def connect(args, env_config: dict):
    if args.account and args.user and args.private_key_path:
        from cryptography.hazmat.primitives import serialization
        key_data = Path(os.path.expanduser(args.private_key_path)).read_bytes()
        private_key = serialization.load_pem_private_key(key_data, password=None)
        pkb = private_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        conn_kwargs = dict(account=args.account, user=args.user, private_key=pkb)
    elif args.connection:
        toml_path = Path("~/.snowflake/connections.toml").expanduser()
        if toml_path.exists():
            with open(toml_path, "rb") as f:
                connections = tomllib.load(f)
            if args.connection in connections:
                cfg = connections[args.connection]
                key_path_raw = cfg.get("private_key_path", "")
                key_path = str(Path(key_path_raw).expanduser()) if key_path_raw else ""
                conn_kwargs = dict(
                    account=cfg["account"],
                    user=cfg["user"],
                    private_key_file=key_path,
                )
            else:
                conn_kwargs = dict(connection_name=args.connection)
        else:
            conn_kwargs = dict(connection_name=args.connection)
    else:
        print("ERROR: Provide --account/--user/--private-key-path or --connection")
        sys.exit(1)

    sf = env_config.get("snowflake", {})
    deploy = env_config.get("deployment", {})
    conn_kwargs.setdefault("role", sf.get("role"))
    conn_kwargs.setdefault("warehouse", sf.get("warehouse"))
    conn_kwargs.setdefault("database", deploy.get("database"))
    conn_kwargs = {k: v for k, v in conn_kwargs.items() if v}
    return snowflake.connector.connect(**conn_kwargs)


def get_eval_configs(env_config: dict) -> list[dict]:
    configs_dir = Path(__file__).resolve().parents[1] / "configs"
    results = []
    for f in sorted(configs_dir.glob("*.y*ml")):
        if f.name.startswith("_"):
            continue
        raw = f.read_text()
        deploy = env_config.get("deployment", {})
        ev = env_config.get("eval", {})
        raw = raw.replace("{{ eval.source_database }}", deploy.get("database", ""))
        raw = raw.replace("{{ eval.agents_schema }}", deploy.get("agents_schema", ""))
        raw = raw.replace("{{ eval.stage }}", deploy.get("stage", ""))
        raw = raw.replace("{{ eval.file_format }}", "EVAL_CSV_FORMAT")
        raw = raw.replace("{{ eval.warehouse }}", env_config.get("snowflake", {}).get("warehouse", ""))
        for k, v in ev.get("thresholds", {}).items():
            raw = raw.replace(f"{{{{ eval.thresholds.{k} }}}}", str(v))
        parsed = yaml.safe_load(raw)
        suffix = env_config.get("agent", {}).get("name_suffix", "")
        if suffix and not parsed["agent"]["name"].endswith(suffix.upper()):
            parsed["agent"]["name"] += suffix.upper()
        results.append(parsed)
    return results


def find_latest_run(cursor, agent: dict) -> str | None:
    try:
        cursor.execute(f"""
            SELECT DISTINCT record_attributes:"snow.ai.observability.run.name"::STRING AS run_name,
                   MAX(timestamp) AS ended
            FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_OBSERVABILITY_LOGS(
                '{agent["database"]}', '{agent["schema"]}', '{agent["name"]}', 'CORTEX AGENT'
            ))
            WHERE record_attributes:"snow.ai.observability.run.name" IS NOT NULL
            GROUP BY 1
            ORDER BY ended DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        return row[0] if row else None
    except Exception:
        return None


def query_latest_eval(cursor, agent: dict, explicit_run_name: str | None = None) -> tuple[str | None, dict]:
    run_name = explicit_run_name or find_latest_run(cursor, agent)
    if not run_name:
        return None, {}
    try:
        cursor.execute(f"""
            SELECT
                METRIC_NAME,
                ROUND(AVG(EVAL_AGG_SCORE), 4) AS avg_score,
                COUNT(*) AS record_count
            FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_EVALUATION_DATA(
                '{agent["database"]}', '{agent["schema"]}', '{agent["name"]}',
                'CORTEX AGENT', '{run_name}'
            ))
            GROUP BY METRIC_NAME
        """)
        rows = cursor.fetchall()
        if not rows:
            return None, {}
        summary = {}
        for row in rows:
            summary[row[0]] = {"avg": float(row[1]) if row[1] else 0.0, "n": int(row[2] or 0)}
        return run_name, summary
    except Exception as e:
        return f"error: {e}", {}


def main():
    parser = argparse.ArgumentParser(description="Query latest DEV eval results for PR gate")
    parser.add_argument("--env", "-e", required=True)
    parser.add_argument("--account", default=os.environ.get("SNOWFLAKE_ACCOUNT"))
    parser.add_argument("--user", default=os.environ.get("SNOWFLAKE_USER"))
    parser.add_argument("--private-key-path", default=os.environ.get("SNOWFLAKE_PRIVATE_KEY_PATH"))
    parser.add_argument("--connection", default=os.environ.get("SNOWFLAKE_CONNECTION_NAME"))
    parser.add_argument("--run-names", help="JSON file mapping agent names to specific eval run names")
    args = parser.parse_args()

    env_config = load_env_config(args.env)
    configs = get_eval_configs(env_config)

    explicit_runs = {}
    if args.run_names:
        rn_path = Path(args.run_names)
        if rn_path.exists():
            explicit_runs = json.loads(rn_path.read_text())

    if not configs:
        print("No eval configs found — skipping")
        sys.exit(0)

    conn = connect(args, env_config)
    cursor = conn.cursor()

    all_passed = True
    md_lines = [
        "## DEV Evaluation Summary",
        "",
        f"Environment: `{env_config['environment']}` | Database: `{env_config['deployment']['database']}`",
        "",
    ]

    for config in configs:
        agent = config["agent"]
        thresholds = config.get("thresholds", {})
        agent_name = agent["name"]

        md_lines.append(f"### {agent_name}")
        md_lines.append("")

        status, summary = query_latest_eval(cursor, agent, explicit_runs.get(agent_name))

        if status is None:
            md_lines.append("⚠️ No evaluation data found")
            md_lines.append("")
            all_passed = False
            continue

        if status.startswith("error"):
            md_lines.append(f"❌ Error querying eval data: `{status}`")
            md_lines.append("")
            all_passed = False
            continue

        md_lines.append("| Metric | Avg Score | Threshold | Status |")
        md_lines.append("|--------|-----------|-----------|--------|")

        agent_passed = True
        for metric, threshold in thresholds.items():
            if metric not in summary:
                md_lines.append(f"| {metric} | N/A | {threshold:.2f} | ⚠️ Missing |")
                agent_passed = False
                continue
            avg = summary[metric]["avg"]
            n = summary[metric]["n"]
            ok = avg >= threshold
            icon = "✅" if ok else "❌"
            md_lines.append(f"| {metric} | {avg:.3f} ({n} questions) | {threshold:.2f} | {icon} {'PASS' if ok else 'FAIL'} |")
            if not ok:
                agent_passed = False

        if not agent_passed:
            all_passed = False
            md_lines.append("")
            md_lines.append(f"**{agent_name}: FAILED** — does not meet DEV thresholds")
        else:
            md_lines.append("")
            md_lines.append(f"**{agent_name}: PASSED**")
        md_lines.append("")

    md_lines.append("---")
    overall = "✅ All agents passed DEV thresholds" if all_passed else "❌ One or more agents failed DEV thresholds"
    md_lines.append(f"**Overall: {overall}**")
    md_lines.append("")
    md_lines.append("_This summary reflects the latest DEV evaluation results. "
                     "Review agent quality before merging to main._")

    md_output = "\n".join(md_lines)
    print(md_output)

    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a") as f:
            f.write(md_output + "\n")

    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a") as f:
            f.write(f"passed={'true' if all_passed else 'false'}\n")

    comment_file = os.environ.get("EVAL_COMMENT_FILE", "/tmp/eval_summary.md")
    with open(comment_file, "w") as f:
        f.write(md_output)

    cursor.close()
    conn.close()

    if not all_passed:
        print("\nFAILED: DEV eval thresholds not met — review before merging to main")
        sys.exit(1)
    else:
        print("\nPASSED: All DEV eval thresholds met")
        sys.exit(0)


if __name__ == "__main__":
    main()
