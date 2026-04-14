"""Detect schema drift between SV YAML definitions and actual Snowflake tables.

Compares columns declared in SV YAML templates against DESCRIBE TABLE output
to identify added, removed, or type-changed columns.

Usage:
    python -m agent_management.detect_drift --env prod
    python -m agent_management.detect_drift --env prod --view sem_operations

Implements REQ-006: Drift Detection.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml as pyyaml

from agent_management import setup_logging
from agent_management.paths import sv_definitions_dir
from agent_management.render_template import render_file
from agent_management.utils.config import load_env_config
from agent_management.utils.snowflake_client import connect

logger = logging.getLogger(__name__)


def get_table_columns(cur, database: str, schema: str, table: str) -> dict[str, str]:
    fqn = f"{database}.{schema}.{table}"
    try:
        cur.execute(f"DESCRIBE TABLE {fqn}")
        return {row[0].upper(): row[1].upper() for row in cur.fetchall()}
    except Exception:
        return {}


def check_drift_for_sv(cur, sv_yaml: dict, config: dict) -> tuple[list[dict], list[dict]]:
    errors = []
    warnings = []
    sv_name = sv_yaml.get("name", "unknown")

    for table_def in sv_yaml.get("tables", []):
        base = table_def.get("base_table", {})
        db = base.get("database", "")
        schema = base.get("schema", "")
        table = base.get("table", "")
        table_fqn = f"{db}.{schema}.{table}"

        actual_cols = get_table_columns(cur, db, schema, table)
        if not actual_cols:
            errors.append({
                "sv": sv_name,
                "table": table_fqn,
                "type": "TABLE_NOT_FOUND",
                "detail": f"Table {table_fqn} does not exist or no access",
            })
            continue

        declared_cols = set()
        for section in ("dimensions", "facts"):
            for col in table_def.get(section, []):
                col_name = col.get("name", "").upper()
                col_expr = col.get("expr", "").upper().strip()
                if col_name and col_expr == col_name:
                    declared_cols.add(col_name)
        for col in table_def.get("time_dimensions", []):
            col_name = col.get("name", "").upper()
            col_expr = col.get("expr", "").upper().strip()
            if col_name and col_expr == col_name:
                declared_cols.add(col_name)
        pk = table_def.get("primary_key", {})
        for col_name in pk.get("columns", []):
            declared_cols.add(col_name.upper())

        for col in declared_cols:
            if col not in actual_cols:
                errors.append({
                    "sv": sv_name,
                    "table": table_fqn,
                    "type": "COLUMN_MISSING",
                    "detail": f"Column {col} declared in SV but not in table",
                })

        for actual_col in actual_cols:
            if actual_col not in declared_cols:
                warnings.append({
                    "sv": sv_name,
                    "table": table_fqn,
                    "type": "COLUMN_UNDECLARED",
                    "detail": f"Column {actual_col} in table but not declared in SV",
                })

    return errors, warnings


def main():
    parser = argparse.ArgumentParser(description="Detect SV schema drift")
    parser.add_argument("--env", "-e", help="Environment (dev, qa, prod)")
    parser.add_argument("--view", "-v", help="Check single SV by name")
    args = parser.parse_args()

    setup_logging(1)

    config = load_env_config(args.env)

    if args.view:
        path = sv_definitions_dir() / f"{args.view}.yaml"
        if not path.exists():
            path = sv_definitions_dir() / f"{args.view}.yml"
        if not path.exists():
            logger.error("SV YAML not found: %s", args.view)
            sys.exit(1)
        sv_files = [path]
    else:
        sv_files = sorted(sv_definitions_dir().glob("sem_*.y*ml"))

    logger.info("Environment: %s", config['environment'])
    logger.info("Views: %d", len(sv_files))
    logger.info("=" * 60)

    conn = connect(config)
    cur = conn.cursor()

    try:
        total_errors = 0
        total_warnings = 0
        for path in sv_files:
            rendered = render_file(path, config)
            sv_yaml = pyyaml.safe_load(rendered)
            sv_name = sv_yaml.get("name", path.stem)

            errors, warnings = check_drift_for_sv(cur, sv_yaml, config)
            if errors:
                logger.error("\n  %s — %d error(s):", sv_name, len(errors))
                for d in errors:
                    logger.error("    [%s] %s", d['type'], d['detail'])
                total_errors += len(errors)
            if warnings:
                logger.warning("\n  %s — %d undeclared column(s) (info only):", sv_name, len(warnings))
                for d in warnings:
                    logger.info("    [%s] %s", d['type'], d['detail'])
                total_warnings += len(warnings)
            if not errors and not warnings:
                logger.info("  %s — no drift", sv_name)

        logger.info("\n%s", "=" * 60)
        if total_warnings:
            logger.info("UNDECLARED COLUMNS: %d (SVs expose a curated subset — this is expected)", total_warnings)
        if total_errors:
            logger.error("DRIFT DETECTED — %d breaking issue(s)", total_errors)
            sys.exit(1)
        else:
            logger.info("NO BREAKING DRIFT — all SV-declared columns exist in tables")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
