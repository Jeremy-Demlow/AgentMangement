"""Run agent evaluation in CI.

Renders eval config and dataset templates using the environment config,
then executes evaluations against Snowflake **in parallel**. Exits non-zero
if any agent fails its thresholds.

Usage (CI):
    python -m agent_management.run_ci_eval --env dev
    python -m agent_management.run_ci_eval --env dev --agent resort_executive
    python -m agent_management.run_ci_eval --env dev --dry-run
    python -m agent_management.run_ci_eval --env dev --max-parallel 4
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml

from agent_management import setup_logging
from agent_management.paths import eval_dir
from agent_management.render_template import render_file
from agent_management.utils.config import load_env_config

logger = logging.getLogger(__name__)

CONFIGS_DIR = eval_dir() / "configs"
SCRIPTS_DIR = eval_dir() / "scripts"


def find_eval_configs(agent: str | None) -> list[Path]:
    if agent:
        path = CONFIGS_DIR / f"{agent}.yaml"
        if not path.exists():
            path = CONFIGS_DIR / f"{agent}.yml"
        if not path.exists():
            raise FileNotFoundError(f"Eval config not found: {agent}")
        return [path]
    files = sorted(CONFIGS_DIR.glob("*.y*ml"))
    return [f for f in files if not f.name.startswith("_")]


def render_and_write(template_path: Path, env_config: dict, tmp_dir: str, strict: bool = True) -> str:
    rendered = render_file(template_path, env_config, strict=strict)
    out = Path(tmp_dir) / template_path.name
    out.write_text(rendered)
    return str(out)


def prepare_agent(config_path: Path, env_config: dict, tmp_dir: str) -> tuple[str, dict, Path]:
    rendered_config = render_file(config_path, env_config, strict=False)
    parsed = yaml.safe_load(rendered_config)

    suffix = env_config.get("agent", {}).get("name_suffix", "")
    if suffix:
        base_name = parsed["agent"]["name"]
        if not base_name.endswith(suffix.upper()):
            parsed["agent"]["name"] = base_name + suffix.upper()

    dataset_relative = parsed["dataset"].get("questions", "")
    if dataset_relative:
        dataset_path = eval_dir() / dataset_relative
        if dataset_path.exists():
            rendered_dataset_path = render_and_write(dataset_path, env_config, tmp_dir, strict=False)
            parsed["dataset"]["questions"] = rendered_dataset_path

    rendered_config_path = Path(tmp_dir) / config_path.name
    rendered_config_path.write_text(yaml.dump(parsed, default_flow_style=False))

    return config_path.stem, parsed, rendered_config_path


def build_cmd(rendered_config_path: Path, args) -> list[str]:
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "run_eval.py"),
        str(rendered_config_path),
    ]

    account = os.environ.get("SNOWFLAKE_ACCOUNT")
    user = os.environ.get("SNOWFLAKE_USER")
    key_path = os.environ.get("SNOWFLAKE_PRIVATE_KEY_PATH")

    if account and user and key_path:
        cmd.extend(["--account", account, "--user", user, "--private-key-path", key_path])
    else:
        connection = os.environ.get("SNOWFLAKE_CONNECTION_NAME", "myconnection")
        cmd.extend(["--connection", connection])

    if args.no_wait:
        cmd.append("--no-wait")
    if args.poll_interval != 30:
        cmd.extend(["--poll-interval", str(args.poll_interval)])
    # CRITICAL: pass --env so run_eval loads env_config and sets role from
    # environments/<env>.env.yml. Without this the connector falls back to
    # the user's DEFAULT_ROLE (which may not have AGENTS privs), producing
    # cryptic 'Insufficient privileges to operate on schema' errors.
    if args.env:
        cmd.extend(["--env", args.env])
    # Versioning selectors (informational — EXECUTE_AI_EVALUATION evaluates
    # the default version regardless; run_eval.py prints a warning).
    if getattr(args, "alias", None):
        cmd.extend(["--alias", args.alias])
    if getattr(args, "version", None):
        cmd.extend(["--version", args.version])

    return cmd


def run_single_eval(agent_name: str, cmd: list[str]) -> tuple[str, int, str, str]:
    result = subprocess.run(
        cmd,
        cwd=str(eval_dir()),
        capture_output=True,
        text=True,
    )
    return agent_name, result.returncode, result.stdout, result.stderr


def extract_run_name(stdout: str) -> str | None:
    m = re.search(r"Run started:\s+(\S+)", stdout)
    return m.group(1) if m else None


def classify_eval_outcome(returncode: int, stdout: str, stderr: str) -> str:
    """Classify a single agent eval subprocess result.

    Returns one of:
      - "passed"          : returncode == 0
      - "threshold_fail"  : eval ran end-to-end and scored below threshold
      - "crashed"         : infrastructure error (eval did not reach the
                            THRESHOLD CHECK section or stderr contains a
                            Python Traceback)

    Pulled out as a pure function so the classification logic is unit-testable
    without spinning up Snowflake / running a real eval. Threshold-fail and
    crash exit the job differently in CI: crash hard-fails (exit 2), threshold
    fail is advisory on dev (exit 1).
    """
    if returncode == 0:
        return "passed"
    crashed = (
        "THRESHOLD CHECK" not in (stdout or "")
        or "Traceback" in (stderr or "")
    )
    return "crashed" if crashed else "threshold_fail"


def main():
    parser = argparse.ArgumentParser(description="Run agent evaluation in CI")
    parser.add_argument("--env", "-e", required=True, help="Environment (dev, qa, prod)")
    parser.add_argument("--agent", "-a", help="Evaluate single agent by name")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Render configs and show plan only")
    parser.add_argument("--no-wait", action="store_true", help="Start eval and exit without waiting")
    parser.add_argument("--poll-interval", type=int, default=30, help="Seconds between polls")
    parser.add_argument("--max-parallel", type=int, default=10, help="Max concurrent agent evaluations (default: 10)")
    parser.add_argument("--alias", help="Informational alias selector; EXECUTE_AI_EVALUATION uses default version regardless.")
    parser.add_argument("--version", help="Informational VERSION$N selector; same caveat as --alias.")
    args = parser.parse_args()

    setup_logging(1)

    env_config = load_env_config(args.env)
    configs = find_eval_configs(args.agent)

    if not configs:
        logger.info("No eval configs found")
        sys.exit(0)

    logger.info("Environment: %s", env_config['environment'])
    logger.info("Eval configs: %d", len(configs))
    logger.info("Parallel: %d max workers", min(args.max_parallel, len(configs)))
    logger.info("=" * 60)

    with tempfile.TemporaryDirectory(prefix="ci_eval_") as tmp_dir:
        prepared = []
        for config_path in configs:
            agent_name, parsed, rendered_path = prepare_agent(config_path, env_config, tmp_dir)
            prepared.append((agent_name, parsed, rendered_path))

        if args.dry_run:
            for agent_name, parsed, _ in prepared:
                logger.info("\n--- %s (dry run) ---", agent_name)
                logger.info("  Agent: %s.%s.%s", parsed['agent']['database'], parsed['agent']['schema'], parsed['agent']['name'])
                logger.info("  Dataset: %s", parsed['dataset']['questions'])
                logger.info("  Table: %s", parsed['dataset']['snowflake_table'])
                logger.info("  Stage: %s", parsed['snowflake']['stage'])
                logger.info("  Thresholds: %s", parsed.get('thresholds', {}))
                logger.info("  Metrics: %s", parsed.get('metrics', []))
            logger.info("\n%s", "=" * 60)
            logger.info("DRY RUN complete — no evaluations executed")
            sys.exit(0)

        for agent_name, _, _ in prepared:
            logger.info("  Starting: %s", agent_name)

        workers = min(args.max_parallel, len(prepared))
        results: dict[str, tuple[int, str, str]] = {}

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {}
            for agent_name, _, rendered_path in prepared:
                cmd = build_cmd(rendered_path, args)
                future = pool.submit(run_single_eval, agent_name, cmd)
                futures[future] = agent_name

            for future in as_completed(futures):
                agent_name, returncode, stdout, stderr = future.result()
                results[agent_name] = (returncode, stdout, stderr)
                status = "PASSED" if returncode == 0 else "FAILED"
                logger.info("  Finished: %s — %s", agent_name, status)

        overall_passed = True
        had_crash = False
        run_names = {}
        for agent_name, parsed, _ in prepared:
            returncode, stdout, stderr = results[agent_name]
            logger.info("\n%s", "=" * 60)
            logger.info("--- %s ---", agent_name)
            logger.info("=" * 60)
            if stdout:
                for line in stdout.rstrip().split("\n"):
                    print(line)
                rn = extract_run_name(stdout)
                if rn:
                    run_names[parsed["agent"]["name"]] = rn
            if stderr:
                for line in stderr.rstrip().split("\n"):
                    print(line, file=sys.stderr)
            if returncode != 0:
                outcome = classify_eval_outcome(returncode, stdout, stderr)
                if outcome == "crashed":
                    logger.error("RESULT: %s CRASHED (exit code %d) — infrastructure error", agent_name, returncode)
                    had_crash = True
                else:
                    logger.error("RESULT: %s FAILED (exit code %d) — threshold", agent_name, returncode)
                overall_passed = False
            else:
                logger.info("RESULT: %s PASSED", agent_name)

        if run_names:
            run_names_file = eval_dir() / "results" / "run_names.json"
            run_names_file.parent.mkdir(parents=True, exist_ok=True)
            run_names_file.write_text(json.dumps(run_names, indent=2))
            logger.info("Run names written to %s", run_names_file)

    logger.info("\n%s", "=" * 60)
    if had_crash:
        logger.error("Overall: CRASH DETECTED — evaluation could not complete")
        sys.exit(2)
    elif not overall_passed:
        logger.warning("Overall: EVAL RAN, THRESHOLDS NOT MET")
        sys.exit(1)
    else:
        logger.info("Overall: ALL PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
