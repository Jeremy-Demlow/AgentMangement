"""Validate agent specs and semantic view YAMLs.

Checks YAML structure, required fields, Jinja2 rendering, and optionally
validates against Snowflake via dry-run deployment.

Usage:
    agent-mgmt-validate --env dev
    agent-mgmt-validate --env dev --remote

Implements REQ-002 and REQ-003 validation acceptance criteria.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml

from agent_management import setup_logging
from agent_management.paths import specs_dir, sv_definitions_dir
from agent_management.render_template import render_file
from agent_management.utils.config import _get_nested, load_env_config

logger = logging.getLogger(__name__)

REQUIRED_AGENT_FIELDS = ["metadata.name", "tools"]
REQUIRED_TOOL_FIELDS = ["name", "type", "description"]
TOOL_TYPE_REQUIRED = {
    "cortex_analyst_text_to_sql": ["semantic_view"],
    "cortex_search": ["search_service"],
    "generic": ["identifier"],
}


def validate_agent_yaml(path: Path, config: dict) -> list[str]:
    errors = []
    try:
        rendered = render_file(path, config)
    except Exception as e:
        return [f"Jinja2 render failed: {e}"]

    try:
        agent = yaml.safe_load(rendered)
    except yaml.YAMLError as e:
        return [f"YAML parse failed: {e}"]

    for field in REQUIRED_AGENT_FIELDS:
        if _get_nested(agent, field) is None:
            errors.append(f"Missing required field: {field}")

    tools = agent.get("tools", [])
    if not tools:
        errors.append("At least one tool is required")
    for i, tool in enumerate(tools):
        for f in REQUIRED_TOOL_FIELDS:
            if not tool.get(f):
                errors.append(f"tools[{i}].{f} is required")
        tool_type = tool.get("type", "")
        for f in TOOL_TYPE_REQUIRED.get(tool_type, []):
            if not tool.get(f):
                errors.append(f"tools[{i}].{f} required for type '{tool_type}'")

    return errors


def validate_sv_yaml(path: Path, config: dict) -> list[str]:
    errors = []
    try:
        rendered = render_file(path, config)
    except Exception as e:
        return [f"Jinja2 render failed: {e}"]

    try:
        sv = yaml.safe_load(rendered)
    except yaml.YAMLError as e:
        return [f"YAML parse failed: {e}"]

    if not sv.get("name"):
        errors.append("Missing required field: name")
    if not sv.get("tables"):
        errors.append("Missing required field: tables")

    for i, table in enumerate(sv.get("tables", [])):
        base = table.get("base_table", {})
        for f in ("database", "schema", "table"):
            if not base.get(f):
                errors.append(f"tables[{i}].base_table.{f} is required")

    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate agent specs and SV YAMLs")
    parser.add_argument("--env", "-e", help="Environment (dev, qa, prod)")
    parser.add_argument("--remote", action="store_true", help="Also validate via Snowflake dry-run")
    args = parser.parse_args()

    setup_logging(1)

    config = load_env_config(args.env)

    logger.info("Environment: %s", config['environment'])
    logger.info("=" * 60)

    total_errors = 0

    agent_files = sorted(specs_dir().glob("*.y*ml"))
    logger.info("\nAgent specs (%d):", len(agent_files))
    for path in agent_files:
        errors = validate_agent_yaml(path, config)
        if errors:
            logger.error("  %s — INVALID (%d errors)", path.name, len(errors))
            for e in errors:
                logger.error("    - %s", e)
            total_errors += len(errors)
        else:
            logger.info("  %s — VALID", path.name)

    sv_files = sorted(sv_definitions_dir().glob("sem_*.y*ml"))
    logger.info("\nSemantic view YAMLs (%d):", len(sv_files))
    for path in sv_files:
        errors = validate_sv_yaml(path, config)
        if errors:
            logger.error("  %s — INVALID (%d errors)", path.name, len(errors))
            for e in errors:
                logger.error("    - %s", e)
            total_errors += len(errors)
        else:
            logger.info("  %s — VALID", path.name)

    if args.remote:
        from agent_management.utils.snowflake_client import connect
        from agent_management.utils.config import get_semantic_schema
        logger.info("\nRemote validation (Snowflake dry-run):")
        conn = connect(config, schema=config["deployment"]["semantic_schema"])
        cur = conn.cursor()
        schema_fqn = get_semantic_schema(config)
        for path in sv_files:
            name = path.stem
            rendered = render_file(path, config)
            try:
                cur.execute(
                    f"CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML('{schema_fqn}', $${rendered}$$, TRUE)"
                )
                logger.info("  %s — VALID (Snowflake)", name)
            except Exception as e:
                logger.error("  %s — INVALID (Snowflake) — %s", name, e)
                total_errors += 1
        cur.close()
        conn.close()

    logger.info("\n%s", "=" * 60)
    if total_errors:
        logger.error("VALIDATION FAILED — %d error(s)", total_errors)
        sys.exit(1)
    else:
        logger.info("ALL VALID")
        sys.exit(0)


if __name__ == "__main__":
    main()
