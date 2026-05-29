"""Check if QA agents have recent evaluation runs.

Used by promote-prod.yml to warn when promoting to PROD without recent QA coverage.
Exits 0 if all agents have recent evals, exits 1 if coverage is missing/stale
(unless --acknowledge is passed to explicitly skip).

Usage:
    python -m agent_management.check_qa_recency --hours 24
    python -m agent_management.check_qa_recency --hours 24 --acknowledge
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from agent_management import setup_logging
from agent_management.utils.config import load_env_config
from agent_management.utils.snowflake_client import connect

logger = logging.getLogger(__name__)


def get_agent_names(qa_config: dict) -> list[str]:
    suffix = qa_config.get("agent", {}).get("name_suffix", "")
    specs_dir = Path("agents/specs")
    names = []
    for path in sorted(specs_dir.glob("*.y*ml")):
        text = path.read_text()
        match = re.search(r'name:\s*(\S+)', text)
        if match:
            base_name = match.group(1).strip().upper()
            names.append(base_name + suffix.upper())
    return names


def check_eval_recency(cur, database: str, schema: str, agent_name: str, cutoff: datetime) -> tuple[bool, str]:
    try:
        cur.execute(f"""
            SELECT MAX(timestamp) AS latest_eval
            FROM TABLE(SNOWFLAKE.LOCAL.GET_AI_OBSERVABILITY_LOGS(
                '{database}', '{schema}', '{agent_name}', 'CORTEX AGENT'
            ))
            WHERE record_attributes:"snow.ai.observability.run.name" IS NOT NULL
        """)
        row = cur.fetchone()
        if not row or not row[0]:
            return False, "no QA evaluation found"

        latest = row[0]
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=timezone.utc)

        if latest >= cutoff:
            return True, f"QA eval within window (latest: {latest.isoformat()})"
        else:
            return False, f"QA eval older than cutoff (latest: {latest.isoformat()})"
    except Exception as e:
        return False, f"error checking eval: {e}"


def main():
    parser = argparse.ArgumentParser(description="Check QA evaluation recency")
    parser.add_argument("--hours", type=int, default=24, help="Max age in hours for QA evals (default: 24)")
    parser.add_argument("--acknowledge", action="store_true", help="Acknowledge and proceed even if QA coverage is stale")
    args = parser.parse_args()

    setup_logging(1)

    qa_config = load_env_config("qa")
    qa_db = qa_config["deployment"]["database"]
    qa_schema = qa_config["deployment"]["agents_schema"]

    agent_names = get_agent_names(qa_config)
    if not agent_names:
        logger.error("No agent specs found in agents/specs/")
        sys.exit(1)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=args.hours)

    logger.info("=" * 60)
    logger.info("QA EVALUATION RECENCY CHECK")
    logger.info("=" * 60)
    logger.info("Database: %s  Schema: %s  Window: %dh", qa_db, qa_schema, args.hours)

    prod_config = load_env_config("prod")
    conn = connect(prod_config)
    cur = conn.cursor()

    all_recent = True
    agents_checked = 0
    agents_with_recent = 0

    try:
        for name in agent_names:
            agents_checked += 1
            recent, detail = check_eval_recency(cur, qa_db, qa_schema, name, cutoff)
            if recent:
                logger.info("  OK: %s — %s", name, detail)
                agents_with_recent += 1
            else:
                logger.warning("  WARNING: %s — %s", name, detail)
                all_recent = False
    finally:
        cur.close()
        conn.close()

    logger.info("")
    logger.info("=" * 60)

    if all_recent:
        logger.info("QA GATE: PASSED — all %d agents have recent QA evaluations", agents_checked)
    else:
        logger.warning("QA evaluation coverage is incomplete or stale")
        logger.warning("  Agents checked: %d", agents_checked)
        logger.warning("  Agents with recent eval: %d", agents_with_recent)
        if args.acknowledge:
            logger.warning("")
            logger.warning("ACKNOWLEDGED: Proceeding to PROD without full QA coverage (--acknowledge)")
            logger.warning("  This is acceptable for hotfixes or when QA was validated through other means.")
        else:
            logger.error("")
            logger.error("BLOCKED: Set skip_qa_ack=true to explicitly acknowledge skipping QA")
            logger.error("  This ensures intentional promotion — not an accidental skip.")
            sys.exit(1)

    logger.info("=" * 60)


if __name__ == "__main__":
    main()
