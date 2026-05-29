"""Render eval config and dataset templates with environment-specific values.

Resolves {{ eval.* }} Jinja2 placeholders in eval YAML files so they can be
used directly by run_eval.py or uploaded to Snowflake stages.

Usage:
    agent-mgmt-render-eval --env dev
    agent-mgmt-render-eval --env dev --file configs/resort_executive.yaml
    agent-mgmt-render-eval --env dev --run-date 20260403

Implements REQ-011: Eval Template Rendering.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import jinja2

from agent_management import setup_logging
from agent_management.paths import eval_dir
from agent_management.render_template import build_context
from agent_management.utils.config import load_env_config

logger = logging.getLogger(__name__)


class _PreserveUndefined(jinja2.Undefined):
    """Renders unknown variables back as {{ varname }}.

    Eval metric prompts use {{output}}, {{ground_truth}}, {{input}} as
    LLM-judge placeholders — these must pass through untouched while
    {{ eval.* }} and {{ env.* }} get resolved.
    """

    def __str__(self):
        return f"{{{{ {self._undefined_name} }}}}"

    def __iter__(self):
        return iter([])

    def __bool__(self):
        return False


GENERATED_DIR = eval_dir() / "generated"

EVAL_GLOBS = [
    "configs/*.yaml",
    "configs/*.yml",
    "datasets/*.yaml",
    "datasets/*.yml",
    "*.yaml",
]


def find_eval_files(specific: str | None) -> list[Path]:
    if specific:
        path = eval_dir() / specific
        if not path.exists():
            raise FileNotFoundError(f"Eval file not found: {path}")
        return [path]
    files = []
    for pattern in EVAL_GLOBS:
        files.extend(eval_dir().glob(pattern))
    seen = set()
    unique = []
    for f in sorted(files):
        if f not in seen and "generated" not in f.parts and "snapshots" not in f.parts:
            seen.add(f)
            unique.append(f)
    return unique


def main():
    parser = argparse.ArgumentParser(description="Render eval templates")
    parser.add_argument("--env", "-e", default="dev", help="Environment (dev, qa, prod)")
    parser.add_argument("--file", "-f", help="Render single file (relative to agent-evaluation/)")
    parser.add_argument("--run-date", help="Override eval run date (YYYYMMDD)")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Print rendered output, don't write")
    args = parser.parse_args()

    setup_logging(1)

    config = load_env_config(args.env)
    eval_files = find_eval_files(args.file)
    out_dir = GENERATED_DIR / config["environment"]
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Environment: %s", config['environment'])
    logger.info("Files: %d", len(eval_files))
    logger.info("Output: %s", out_dir)
    logger.info("=" * 60)

    success = 0
    failed = 0
    skipped = 0
    for path in eval_files:
        rel = path.relative_to(eval_dir())
        content = path.read_text()

        if "{{" not in content:
            skipped += 1
            continue

        try:
            ctx = build_context(config, run_date=args.run_date)
            j2_env = jinja2.Environment(undefined=_PreserveUndefined, keep_trailing_newline=True)
            rendered = j2_env.from_string(content).render(**ctx)

            if args.dry_run:
                logger.info("\n--- %s ---", rel)
                logger.info("%s", rendered[:500])
                if len(rendered) > 500:
                    logger.info("... (%d chars total)", len(rendered))
            else:
                out_path = out_dir / rel
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(rendered)
                logger.info("  %s -> %s", rel, out_path.relative_to(eval_dir()))

            success += 1
        except Exception as e:
            logger.error("  %s... FAILED — %s", rel, e)
            failed += 1

    logger.info("\n%s", "=" * 60)
    logger.info("Rendered: %d  Skipped: %d  Failed: %d", success, skipped, failed)
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
