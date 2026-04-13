"""Run agent evaluation in CI.

Renders eval config and dataset templates using the environment config,
then executes the evaluation against Snowflake. Exits non-zero if thresholds fail.

Usage (CI):
    python -m agent_management.run_ci_eval --env dev
    python -m agent_management.run_ci_eval --env dev --agent resort_executive
    python -m agent_management.run_ci_eval --env dev --dry-run
"""
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import tempfile
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


def main():
    parser = argparse.ArgumentParser(description="Run agent evaluation in CI")
    parser.add_argument("--env", "-e", required=True, help="Environment (dev, qa, prod)")
    parser.add_argument("--agent", "-a", help="Evaluate single agent by name")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Render configs and show plan only")
    parser.add_argument("--no-wait", action="store_true", help="Start eval and exit without waiting")
    parser.add_argument("--poll-interval", type=int, default=30, help="Seconds between polls")
    args = parser.parse_args()

    setup_logging(1)

    env_config = load_env_config(args.env)
    configs = find_eval_configs(args.agent)

    if not configs:
        logger.info("No eval configs found")
        sys.exit(0)

    logger.info("Environment: %s", env_config['environment'])
    logger.info("Eval configs: %d", len(configs))
    logger.info("=" * 60)

    overall_passed = True

    with tempfile.TemporaryDirectory(prefix="ci_eval_") as tmp_dir:
        for config_path in configs:
            agent_name = config_path.stem
            logger.info("\n--- Evaluating: %s ---", agent_name)

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

            if args.dry_run:
                logger.info("  Agent: %s.%s.%s", parsed['agent']['database'], parsed['agent']['schema'], parsed['agent']['name'])
                logger.info("  Dataset: %s", parsed['dataset']['questions'])
                logger.info("  Table: %s", parsed['dataset']['snowflake_table'])
                logger.info("  Stage: %s", parsed['snowflake']['stage'])
                logger.info("  Thresholds: %s", parsed.get('thresholds', {}))
                logger.info("  Metrics: %s", parsed.get('metrics', []))
                continue

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

            logger.info("  Running evaluation...")
            result = subprocess.run(cmd, cwd=str(eval_dir()))

            if result.returncode != 0:
                logger.error("  FAILED: %s (exit code %d)", agent_name, result.returncode)
                overall_passed = False
            else:
                logger.info("  PASSED: %s", agent_name)

    logger.info("\n%s", "=" * 60)
    if args.dry_run:
        logger.info("DRY RUN complete — no evaluations executed")
        sys.exit(0)

    status = "ALL PASSED" if overall_passed else "FAILURES DETECTED"
    logger.info("Overall: %s", status)
    sys.exit(0 if overall_passed else 1)


if __name__ == "__main__":
    main()
