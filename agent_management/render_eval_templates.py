"""Render eval config and dataset templates with environment-specific values.

Resolves {{ eval.* }} Jinja2 placeholders in eval YAML files so they can be
used directly by run_eval.py or uploaded to Snowflake stages.

Usage:
    python -m agent_management.render_eval_templates --env dev
    python -m agent_management.render_eval_templates --env dev --file configs/resort_executive.yaml
    python -m agent_management.render_eval_templates --env dev --run-date 20260403

Implements REQ-011: Eval Template Rendering.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import jinja2

from agent_management.render_template import build_context
from agent_management.utils.config import load_env_config


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


EVAL_DIR = Path(__file__).resolve().parent.parent / "agent-evaluation"
GENERATED_DIR = EVAL_DIR / "generated"

EVAL_GLOBS = [
    "configs/*.yaml",
    "configs/*.yml",
    "datasets/*.yaml",
    "datasets/*.yml",
    "*.yaml",
]


def find_eval_files(specific: str | None) -> list[Path]:
    if specific:
        path = EVAL_DIR / specific
        if not path.exists():
            raise FileNotFoundError(f"Eval file not found: {path}")
        return [path]
    files = []
    for pattern in EVAL_GLOBS:
        files.extend(EVAL_DIR.glob(pattern))
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

    config = load_env_config(args.env)
    eval_files = find_eval_files(args.file)
    out_dir = GENERATED_DIR / config["environment"]
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Environment: {config['environment']}")
    print(f"Files: {len(eval_files)}")
    print(f"Output: {out_dir}")
    print("=" * 60)

    success = 0
    failed = 0
    skipped = 0
    for path in eval_files:
        rel = path.relative_to(EVAL_DIR)
        content = path.read_text()

        if "{{" not in content:
            skipped += 1
            continue

        try:
            ctx = build_context(config, run_date=args.run_date)
            j2_env = jinja2.Environment(undefined=_PreserveUndefined, keep_trailing_newline=True)
            rendered = j2_env.from_string(content).render(**ctx)

            if args.dry_run:
                print(f"\n--- {rel} ---")
                print(rendered[:500])
                if len(rendered) > 500:
                    print(f"... ({len(rendered)} chars total)")
            else:
                out_path = out_dir / rel
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(rendered)
                print(f"  {rel} -> {out_path.relative_to(EVAL_DIR)}")

            success += 1
        except Exception as e:
            print(f"  {rel}... FAILED — {e}")
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"Rendered: {success}  Skipped: {skipped}  Failed: {failed}")
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
