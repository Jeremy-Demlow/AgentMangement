"""Detect drift between deployed semantic views and what dbt would produce.

Compares the YAML from `SYSTEM$READ_YAML_FROM_SEMANTIC_VIEW` (what is actually
deployed in Snowflake) against the YAML produced by compiling the dbt
semantic_view model (source of truth).

This catches two failure modes:
  1. Someone manually deployed a SV via SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML
     and the dbt model was never updated -> deployed != compiled.
  2. dbt model was updated but never deployed to this environment
     -> compiled != deployed.

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
import subprocess
import sys
from pathlib import Path

from agent_management import setup_logging
from agent_management.utils.config import get_database, load_env_config
from agent_management.utils.snowflake_client import connect

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
DBT_DIR = REPO_ROOT / "dbt_ski_resort"
SV_MODEL_DIR = DBT_DIR / "models" / "marts" / "semantic"


# ---------- Normalization ----------

def normalize_yaml(text: str) -> str:
    """Return a canonical form of a SV YAML string for diffing.

    Strips trailing whitespace, blank lines, and auto-generated fields that
    change on every deploy (created_at, verified_at on VQRs).
    """
    lines = []
    for raw in text.splitlines():
        line = raw.rstrip()
        # drop dynamic fields
        stripped = line.strip()
        if stripped.startswith(("verified_at:", "created_at:", "updated_at:")):
            continue
        if not stripped:
            continue
        lines.append(line)
    return "\n".join(lines) + "\n"


# ---------- Read live SV ----------

def read_deployed_sv_yaml(cur, database: str, schema: str, sv_name: str) -> str | None:
    fqn = f"{database}.{schema}.{sv_name}".upper()
    try:
        cur.execute(f"SELECT SYSTEM$READ_YAML_FROM_SEMANTIC_VIEW('{fqn}')")
        row = cur.fetchone()
        return row[0] if row else None
    except Exception as e:
        logger.warning("  Could not read live SV %s: %s", fqn, e)
        return None


# ---------- Compile dbt to get expected YAML ----------

def dbt_compile(env: str) -> bool:
    """Run `dbt compile` for the given target; returns True on success."""
    cmd = ["dbt", "compile", "--profiles-dir", ".", "--target", env]
    logger.info("  Running: %s (in %s)", " ".join(cmd), DBT_DIR)
    proc = subprocess.run(cmd, cwd=DBT_DIR, capture_output=True, text=True)
    if proc.returncode != 0:
        logger.error("  dbt compile failed:\n%s", proc.stdout + proc.stderr)
        return False
    return True


def read_compiled_sv_sql(sv_name: str) -> str | None:
    """Read the compiled CREATE SEMANTIC VIEW DDL produced by dbt compile."""
    compiled = DBT_DIR / "target" / "compiled" / "dbt_ski_resort" / "models" / "marts" / "semantic" / f"{sv_name.lower()}.sql"
    if not compiled.exists():
        logger.warning("  Compiled dbt model not found: %s", compiled)
        return None
    return compiled.read_text()


# ---------- Deploy to scratch schema & read back ----------

def deploy_and_read_expected_yaml(cur, compiled_sql: str, scratch_db: str, scratch_schema: str, sv_name: str) -> str | None:
    """Create the SV in a scratch schema so we can SYSTEM$READ_YAML it.

    This is needed because the compiled DDL is procedural SQL, not a YAML
    doc. To compare apples-to-apples we deploy it and read it back.
    """
    scratch_fqn = f"{scratch_db}.{scratch_schema}.{sv_name.upper()}_DRIFT_CHECK"
    # The compiled SQL references the real DB in FROM clauses, so we can
    # create the SV in scratch without rebuilding base tables.
    try:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {scratch_db}.{scratch_schema}")
        # The compiled SQL has CREATE OR REPLACE SEMANTIC VIEW {{name}}.
        # We need to rewrite the target to the scratch FQN.
        rewritten = compiled_sql.replace(
            f"CREATE OR REPLACE SEMANTIC VIEW",
            f"CREATE OR REPLACE SEMANTIC VIEW",
            1,
        )
        # dbt's compiled file already has the target FQN embedded — we replace
        # it with the scratch FQN on the first CREATE line.
        lines = rewritten.splitlines()
        for i, line in enumerate(lines):
            if line.strip().upper().startswith("CREATE OR REPLACE SEMANTIC VIEW"):
                # replace third token (the FQN) with scratch
                parts = line.split()
                if len(parts) >= 5:
                    parts[4] = scratch_fqn
                    lines[i] = " ".join(parts)
                break
        rewritten = "\n".join(lines)
        cur.execute(rewritten)
        cur.execute(f"SELECT SYSTEM$READ_YAML_FROM_SEMANTIC_VIEW('{scratch_fqn}')")
        row = cur.fetchone()
        return row[0] if row else None
    except Exception as e:
        logger.error("  Scratch deploy failed for %s: %s", sv_name, e)
        return None
    finally:
        try:
            cur.execute(f"DROP SEMANTIC VIEW IF EXISTS {scratch_fqn}")
        except Exception:
            pass


# ---------- Main ----------

def list_sv_models() -> list[str]:
    return sorted(p.stem for p in SV_MODEL_DIR.glob("sem_*.sql"))


def check_drift(cur, env: str, sv_name: str, scratch_db: str, scratch_schema: str, semantic_schema: str, database: str) -> bool:
    """Return True if drift detected."""
    logger.info("\n[%s] %s", env, sv_name)

    deployed = read_deployed_sv_yaml(cur, database, semantic_schema, sv_name)
    if deployed is None:
        logger.error("  DRIFT: SV not deployed in %s (dbt model exists but no live SV)", env)
        return True

    compiled_sql = read_compiled_sv_sql(sv_name)
    if compiled_sql is None:
        logger.error("  Could not find compiled dbt artifact for %s", sv_name)
        return True

    expected = deploy_and_read_expected_yaml(cur, compiled_sql, scratch_db, scratch_schema, sv_name)
    if expected is None:
        logger.error("  Could not deploy dbt-compiled SV to scratch for comparison")
        return True

    norm_deployed = normalize_yaml(deployed)
    norm_expected = normalize_yaml(expected)

    if norm_deployed == norm_expected:
        logger.info("  OK — deployed matches dbt source of truth")
        return False

    logger.error("  DRIFT — deployed SV differs from dbt-compiled output")
    # Show a short diff preview
    import difflib
    diff = list(difflib.unified_diff(
        norm_expected.splitlines(),
        norm_deployed.splitlines(),
        fromfile=f"dbt-compiled ({sv_name})",
        tofile=f"deployed ({env})",
        lineterm="",
        n=2,
    ))
    for line in diff[:40]:
        logger.error("    %s", line)
    if len(diff) > 40:
        logger.error("    ... (%d more diff lines)", len(diff) - 40)
    return True


def main():
    parser = argparse.ArgumentParser(description="Detect drift between deployed SV and dbt source of truth")
    parser.add_argument("--env", "-e", required=True, help="Environment (dev, qa, prod)")
    parser.add_argument("--view", "-v", help="Check single SV (e.g. sem_safety_incidents)")
    parser.add_argument("--fail-on-drift", action="store_true", help="Exit non-zero if any drift found")
    parser.add_argument("--scratch-schema", default="DRIFT_CHECK", help="Schema for temporary SVs (default: DRIFT_CHECK)")
    args = parser.parse_args()

    setup_logging(1)

    config = load_env_config(args.env)
    database = get_database(config)
    semantic_schema = config["deployment"].get("semantic_schema", "SEMANTIC")

    logger.info("Environment: %s  Database: %s  Schema: %s", args.env, database, semantic_schema)
    logger.info("Scratch: %s.%s", database, args.scratch_schema)
    logger.info("=" * 60)

    logger.info("Compiling dbt project...")
    if not dbt_compile(args.env):
        sys.exit(2)

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
            drifted = check_drift(cur, args.env, sv_name, database, args.scratch_schema, semantic_schema, database)
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
