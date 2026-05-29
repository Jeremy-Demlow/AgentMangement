"""Detect drift between semantic view source-of-truth and what's deployed.

Supports two source-of-truth shapes, auto-detected per env:

  1. dbt:   ``dbt_ski_resort/models/marts/semantic/sem_*.sql``
            parsed via structural regex (TABLES/DIMENSIONS/FACTS/METRICS blocks).
  2. yaml:  ``semantic-views/definitions/sem_*.yaml``
            Jinja-rendered against env config, then parsed as Snowflake SV YAML.

The source is picked per env by the ``semantic_views.source`` field in
``environments/<env>.env.yml``. If not set, the library falls back to the
top-level ``project.yml`` default. Both modes compare the same structural
signature (sets of table names, dimension aliases, fact aliases, metric
names) against the deployed SV YAML returned by
``SYSTEM$READ_YAML_FROM_SEMANTIC_VIEW``.

When a consumer repo ships *without* a dbt project and only ships YAML SV
definitions, this check still runs end to end. When a repo ships dbt
models, we parse those instead. When neither exists for a given SV name we
log a skipped warning but don't report drift.

Usage::

    agent-mgmt-detect-sv-drift --env dev
    agent-mgmt-detect-sv-drift --env prod --view sem_safety_incidents
    agent-mgmt-detect-sv-drift --env dev --source yaml --fail-on-drift
    agent-mgmt-detect-sv-drift --env dev --fail-on-drift

Exit codes:
    0 = no drift (or --fail-on-drift not set)
    1 = drift detected and --fail-on-drift set
    2 = error running parser or reading live SV
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

import yaml as pyyaml

from agent_management import setup_logging
from agent_management.paths import (
    project_root,
    sv_definitions_dir,
)
from agent_management.render_template import render_file
from agent_management.utils.config import (
    get_database,
    get_sv_source,
    load_env_config,
    load_project_config,
)
from agent_management.utils.snowflake_client import connect

logger = logging.getLogger(__name__)

REPO_ROOT = project_root()
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
        TABLES ( T1 AS {{ ref(...) }}, T2 AS ... )
        DIMENSIONS ( T1.COL1 AS ALIAS, ... )
        FACTS ( T1.COL2 AS ALIAS, ... )
        METRICS ( T1.NAME AS <expr>, ... )

    For TABLES: name is the LHS identifier.
    For DIMENSIONS/FACTS: name is the RHS identifier (alias after AS).
    For METRICS: name is the part after the dot in the LHS (before AS).
    """
    raw = _strip_comments(sql_path.read_text())

    def extract_block(name: str) -> str:
        """Extract a TABLES/DIMENSIONS/FACTS/METRICS block with proper paren
        balancing.

        The naive ``\\b<NAME>\\s*\\(...\\)`` regex approach breaks on multi-line
        metric definitions like ``FACT.COL AS DIV0(... , ...)`` because the
        non-greedy match closes on the first inner ``)``. We scan character by
        character and count paren depth instead.
        """
        pattern = re.compile(rf"\b{name}\s*\(", re.IGNORECASE)
        m = pattern.search(raw)
        if not m:
            return ""
        start = m.end()  # position just after the opening (
        depth = 1
        i = start
        while i < len(raw) and depth > 0:
            ch = raw[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return raw[start:i]
            i += 1
        return raw[start:i]

    def extract_table_names(block: str) -> set[str]:
        # Tables: "  TABLE_NAME AS {{ ref(...) }}  ..."
        names: set[str] = set()
        for line in block.splitlines():
            stripped = line.strip()
            m = re.match(r"^([A-Za-z_]\w*)\s+AS\b", stripped)
            if m:
                names.add(m.group(1).upper())
        return names

    def extract_dim_fact_aliases(block: str) -> set[str]:
        # Dims/Facts: "TABLE.COL AS ALIAS"
        names: set[str] = set()
        for line in block.splitlines():
            stripped = line.strip()
            m = re.match(r"^[A-Za-z_]\w*\.[A-Za-z_]\w*\s+AS\s+([A-Za-z_]\w*)", stripped)
            if m:
                names.add(m.group(1).upper())
        return names

    def extract_metric_names(block: str) -> set[str]:
        # Metrics: "TABLE.NAME AS <expr>" — capture NAME (after the dot, before AS)
        names: set[str] = set()
        for line in block.splitlines():
            stripped = line.strip()
            m = re.match(r"^[A-Za-z_]\w*\.([A-Za-z_]\w*)\s+AS\b", stripped)
            if m:
                names.add(m.group(1).upper())
        return names

    tables = extract_table_names(extract_block("TABLES"))
    dimensions = extract_dim_fact_aliases(extract_block("DIMENSIONS"))
    facts = extract_dim_fact_aliases(extract_block("FACTS"))
    metrics = extract_metric_names(extract_block("METRICS"))

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


def _render_yaml_source(yaml_path: Path, config: dict) -> str:
    """Render a Jinja-templated SV YAML against the env config."""
    return render_file(str(yaml_path), config)


def parse_source_yaml(yaml_path: Path, config: dict) -> dict[str, set[str]]:
    """Parse a local YAML SV definition (same shape as the live SV YAML)."""
    rendered = _render_yaml_source(yaml_path, config)
    return parse_live_sv(rendered)


def _find_source(sv_name: str, *, source: str) -> tuple[str, Path] | tuple[None, None]:
    """Locate the source-of-truth file for sv_name.

    Returns (kind, path) where kind is 'dbt' or 'yaml'. Returns (None, None)
    if neither source file exists.
    """
    dbt_path = SV_MODEL_DIR / f"{sv_name}.sql"
    yaml_path = sv_definitions_dir() / f"{sv_name}.yaml"
    alt_yaml_path = sv_definitions_dir() / f"{sv_name}.yml"

    # Honor the user's preference when present, fall back if missing.
    if source == "dbt" and dbt_path.exists():
        return ("dbt", dbt_path)
    if source == "yaml":
        if yaml_path.exists():
            return ("yaml", yaml_path)
        if alt_yaml_path.exists():
            return ("yaml", alt_yaml_path)

    # auto / fallback: prefer dbt, fall back to yaml
    if dbt_path.exists():
        return ("dbt", dbt_path)
    if yaml_path.exists():
        return ("yaml", yaml_path)
    if alt_yaml_path.exists():
        return ("yaml", alt_yaml_path)
    return (None, None)


# ---------- Drift check ----------

def diff_sets(expected: set[str], actual: set[str], kind: str, *, source_label: str) -> list[str]:
    msgs = []
    missing = expected - actual
    extra = actual - expected
    for m in sorted(missing):
        msgs.append(f"  MISSING from live {kind}: {m} (in {source_label} but not deployed)")
    for e in sorted(extra):
        msgs.append(f"  EXTRA in live {kind}: {e} (deployed but not in {source_label})")
    return msgs


def check_sv(
    cur,
    env: str,
    sv_name: str,
    database: str,
    semantic_schema: str,
    *,
    source: str = "auto",
    config: dict | None = None,
) -> bool:
    """Return True if drift detected.

    ``source`` = 'dbt', 'yaml', or 'auto' (picks whichever file exists; prefers
    dbt when both do). Repos without a dbt project simply ship YAML files in
    ``semantic-views/definitions/`` and this check works identically.
    """
    kind, path = _find_source(sv_name, source=source)
    if kind is None:
        logger.warning(
            "  No source of truth for %s (neither dbt model in %s nor YAML in %s) -- skipping",
            sv_name, SV_MODEL_DIR, sv_definitions_dir(),
        )
        return False

    if kind == "dbt":
        source_struct = parse_dbt_sv(path)
    else:
        if config is None:
            raise ValueError("parse_source_yaml requires env config for Jinja rendering")
        source_struct = parse_source_yaml(path, config)

    live_yaml = read_deployed_sv_yaml(cur, database, semantic_schema, sv_name)
    if live_yaml is None:
        logger.error(
            "  DRIFT: %s has %s source (%s) but no live SV in %s",
            sv_name, kind, path.name, env,
        )
        return True

    live_struct = parse_live_sv(live_yaml)

    drift_msgs: list[str] = []
    for facet in ("tables", "dimensions", "facts", "metrics"):
        drift_msgs.extend(
            diff_sets(source_struct[facet], live_struct[facet], facet, source_label=kind)
        )

    if drift_msgs:
        logger.error("[%s] %s DRIFT (source=%s):", env, sv_name, kind)
        for m in drift_msgs:
            logger.error(m)
        return True

    logger.info(
        "[%s] %s OK (source=%s tables=%d dims=%d facts=%d metrics=%d)",
        env, sv_name, kind,
        len(source_struct["tables"]),
        len(source_struct["dimensions"]),
        len(source_struct["facts"]),
        len(source_struct["metrics"]),
    )
    return False


def list_sv_models(*, source: str = "auto") -> list[str]:
    """Return the SV names the library should check, union of dbt + yaml sources.

    For ``source='dbt'`` or ``source='yaml'`` we return the respective set.
    For ``source='auto'`` we union the names found in both locations so that a
    repo with partial coverage (some SVs in dbt, some as YAML) still exercises
    every SV.
    """
    names: set[str] = set()
    if source in ("dbt", "auto"):
        if SV_MODEL_DIR.exists():
            names.update(p.stem for p in SV_MODEL_DIR.glob("sem_*.sql"))
    if source in ("yaml", "auto"):
        yaml_dir = sv_definitions_dir()
        if yaml_dir.exists():
            names.update(p.stem for p in yaml_dir.glob("sem_*.yaml"))
            names.update(p.stem for p in yaml_dir.glob("sem_*.yml"))
    return sorted(names)


def main():
    parser = argparse.ArgumentParser(
        description="Detect drift between deployed SV and source-of-truth (dbt model or YAML definition).",
    )
    parser.add_argument("--env", "-e", required=True, help="Environment (dev, prod)")
    parser.add_argument("--view", "-v", help="Check single SV (e.g. sem_safety_incidents)")
    parser.add_argument(
        "--source", choices=["auto", "dbt", "yaml"],
        help="Which source-of-truth format. Default: read semantic_views.source from env config; 'auto' if unset.",
    )
    parser.add_argument("--fail-on-drift", action="store_true", help="Exit non-zero if any drift found")
    args = parser.parse_args()

    setup_logging(1)

    config = load_env_config(args.env)
    database = get_database(config)
    semantic_schema = config["deployment"].get("semantic_schema", "SEMANTIC")

    # Precedence: --source flag > env config semantic_views.source > 'auto'
    if args.source:
        source = args.source
    else:
        try:
            source = get_sv_source(config)
        except Exception:
            source = "auto"
        if source not in ("dbt", "yaml"):
            source = "auto"

    logger.info(
        "Environment: %s  Database: %s  Schema: %s  Source-of-truth: %s",
        args.env, database, semantic_schema, source,
    )
    logger.info("=" * 60)

    if args.view:
        svs = [args.view.lower()]
    else:
        svs = list_sv_models(source=source)
    if not svs:
        logger.warning(
            "No SVs found. Checked dbt dir (%s) and yaml dir (%s).",
            SV_MODEL_DIR, sv_definitions_dir(),
        )
    logger.info("SVs to check: %d", len(svs))

    conn = connect(config)
    cur = conn.cursor()
    any_drift = False
    try:
        for sv_name in svs:
            drifted = check_sv(
                cur, args.env, sv_name, database, semantic_schema,
                source=source, config=config,
            )
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
