"""Detect drift between dbt semantic view sources and what's deployed.

Minimal version: verifies each dbt sem_*.sql model has a corresponding
deployed semantic view in the target environment, and compares high-level
table/metric/dimension counts between compiled dbt output and live SV.

A full byte-level structural diff would require deploying the dbt-compiled
SV to a scratch schema (which needs CREATE SCHEMA privileges we don't have
in the CI deploy role). Instead we compare structure counts and the set of
table/metric/dimension names, which is enough to catch the common drift
cases:
  - dbt model deployed in one env but not another
  - dbt model has a new table/metric/dimension that isn't live
  - live SV has a table/metric/dimension not in the dbt model

Usage:
    python -m agent_management.detect_sv_drift --env dev
    python -m agent_management.detect_sv_drift --env prod --view sem_safety_incidents
    python -m agent_management.detect_sv_drift --env qa --fail-on-drift

Exit codes:
    0 = no drift (or --fail-on-drift not set)
    1 = drift detected and --fail-on-drift set
    2 = error running dbt or reading live SV
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

import yaml as pyyaml

from agent_management import setup_logging
from agent_management.utils.config import get_database, load_env_config
from agent_management.utils.snowflake_client import connect

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
DBT_DIR = REPO_ROOT / "dbt_ski_resort"
SV_MODEL_DIR = DBT_DIR / "models" / "marts" / "semantic"


# ---------- Parse dbt SV SQL ----------

def _strip_comments(sql: str) -> str:
    """Remove SQL line comments and dbt jinja for easier parsing."""
    out_lines = []
    for line in sql.splitlines():
        stripped = line.split("--", 1)[0]
        out_lines.append(stripped)
    return "\n".join(out_lines)


def parse_dbt_sv(sql_path: Path) -> dict:
    """Extract table, dimension, fact, and metric names from a dbt SV SQL file.

    The file uses the Snowflake CREATE SEMANTIC VIEW syntax (pre-compile),
    which has blocks like:
        TABLES ( T1 AS ..., T2 AS ... )
        DIMENSIONS ( T1.COL1 AS ALIAS, ... )
        FACTS ( T1.COL2 AS ALIAS, ... )
        METRICS ( T1.NAME AS <expr>, ... )
    """
    raw = _strip_comments(sql_path.read_text())

    def extract_block(name: str) -> str:
        m = re.search(rf"\b{name}\s*\((.*?)\n\)", raw, re.IGNORECASE | re.DOTALL)
        return m.group(1) if m else ""

    def extract_names(block: str) -> set[str]:
        names: set[str] = set()
        # pattern matches "TABLE.COL AS ALIAS" or "TABLE AS ..." — capture last identifier before AS
        for line in block.splitlines():
            line = line.strip().rstrip(",")
            if not line:
                continue
            # "T.COL AS ALIAS" -> alias
            m = re.match(r"([A-Za-z_][\w.]*)\s+AS\s+([A-Za-z_]\w*)", line, re.IGNORECASE)
            if m:
                names.add(m.group(2).upper())
        return names

    tables = extract_names(extract_block("TABLES"))
    dimensions = extract_names(extract_block("DIMENSIONS"))
    facts = extract_names(extract_block("FACTS"))
    metrics = extract_names(extract_block("METRICS"))

    return {
        "tables": tables,
        "dimensions": dimensions,
        "facts": facts,
        "metrics": metrics,
    }


# ---------- Parse live SV YAML ----------

def read_deployed_sv_yaml(cur, database: str, schema: str, sv_name: str) -> str | None:
    fqn = f"{database}.{schema}.{sv_name}".upper()
    try:
        cur.execute(f"SELECT SYSTEM$READ_YAML_FROM_SEMANTIC_VIEW('{fqn}')")
        row = cur.fetchone()
        return row[0] if row else None
    except Exception as e:
        logger.warning("  Could not read live SV %s: %s", fqn, e)
        return None


def parse_live_sv(yaml_text: str) -> dict:
    try:
        doc = pyyaml.safe_load(yaml_text) or {}
    except Exception:
        return {"tables": set(), "dimensions": set(), "facts": set(), "metrics": set()}

    tables: set[str] = set()
    dimensions: set[str] = set()
    facts: set[str] = set()
    metrics: set[str] = set()
    for table_def in doc.get("tables", []) or []:
        if isinstance(table_def, dict):
            name = table_def.get("name")
            if name:
                tables.add(str(name).upper())
            for d in table_def.get("dimensions", []) or []:
                if isinstance(d, dict) and d.get("name"):
                    dimensions.add(str(d["name"]).upper())
            for f in table_def.get("facts", []) or []:
                if isinstance(f, dict) and f.get("name"):
                    facts.add(str(f["name"]).upper())
            for m in table_def.get("metrics", []) or []:
                if isinstance(m, dict) and m.get("name"):
                    metrics.add(str(m["name"]).upper())

    return {
        "tables": tables,
        "dimensions": dimensions,
        "facts": facts,
        "metrics": metrics,
    }


# ---------- Drift check ----------

def diff_sets(expected: set[str], actual: set[str], kind: str) -> list[str]:
    msgs = []
    missing = expected - actual
    extra = actual - expected
    for m in sorted(missing):
        msgs.append(f"  MISSING from live {kind}: {m} (in dbt but not deployed)")
    for e in sorted(extra):
        msgs.append(f"  EXTRA in live {kind}: {e} (deployed but not in dbt)")
    return msgs


def check_sv(cur, env: str, sv_name: str, database: str, semantic_schema: str) -> bool:
    """Return True if drift detected."""
    sql_path = SV_MODEL_DIR / f"{sv_name}.sql"
    if not sql_path.exists():
        logger.warning("  No dbt model for %s (skipping)", sv_name)
        return False

    dbt_struct = parse_dbt_sv(sql_path)

    live_yaml = read_deployed_sv_yaml(cur, database, semantic_schema, sv_name)
    if live_yaml is None:
        logger.error("  DRIFT: %s has dbt model but no live SV in %s", sv_name, env)
        return True

    live_struct = parse_live_sv(live_yaml)

    drift_msgs: list[str] = []
    for kind in ("tables", "dimensions", "facts", "metrics"):
        drift_msgs.extend(diff_sets(dbt_struct[kind], live_struct[kind], kind))

    if drift_msgs:
        logger.error("[%s] %s DRIFT:", env, sv_name)
        for m in drift_msgs:
            logger.error(m)
        return True

    logger.info("[%s] %s OK (tables=%d dims=%d facts=%d metrics=%d)",
                env, sv_name,
                len(dbt_struct["tables"]),
                len(dbt_struct["dimensions"]),
                len(dbt_struct["facts"]),
                len(dbt_struct["metrics"]))
    return False


def list_sv_models() -> list[str]:
    return sorted(p.stem for p in SV_MODEL_DIR.glob("sem_*.sql"))


def main():
    parser = argparse.ArgumentParser(description="Detect drift between deployed SV and dbt source of truth")
    parser.add_argument("--env", "-e", required=True, help="Environment (dev, qa, prod)")
    parser.add_argument("--view", "-v", help="Check single SV (e.g. sem_safety_incidents)")
    parser.add_argument("--fail-on-drift", action="store_true", help="Exit non-zero if any drift found")
    args = parser.parse_args()

    setup_logging(1)

    config = load_env_config(args.env)
    database = get_database(config)
    semantic_schema = config["deployment"].get("semantic_schema", "SEMANTIC")

    logger.info("Environment: %s  Database: %s  Schema: %s", args.env, database, semantic_schema)
    logger.info("=" * 60)

    if args.view:
        svs = [args.view.lower()]
    else:
        svs = list_sv_models()
    logger.info("SVs to check: %d", len(svs))

    conn = connect(config)
    cur = conn.cursor()
    any_drift = False
    try:
        for sv_name in svs:
            drifted = check_sv(cur, args.env, sv_name, database, semantic_schema)
            any_drift = any_drift or drifted

        logger.info("\n%s", "=" * 60)
        if any_drift:
            logger.error("DRIFT DETECTED in %s", args.env)
            if args.fail_on_drift:
                sys.exit(1)
        else:
            logger.info("NO DRIFT — all SVs match dbt source of truth")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
