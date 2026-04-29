"""Query recent rollback events and format as a PR comment.

Queries CORTEX_AGENT_VERSION_LOG for rollback/promote events in the last N
days across DEV and PROD, and emits a markdown summary. validate-pr.yml posts
this to the PR so reviewers see recent prod instability at a glance.

Usage:
    python -m agent_management.format_rollback_history_comment --output /tmp/rollback_history.md

Produces empty output (exit 0, empty file) when there's nothing to report so
the PR doesn't get noisy comments during stable periods.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from agent_management import setup_logging
from agent_management.utils.config import get_database, load_env_config
from agent_management.utils.snowflake_client import connect

logger = logging.getLogger(__name__)

LOG_TABLE = "CORTEX_AGENT_VERSION_LOG"


def fetch_rollbacks(conn, database: str, schema: str, days: int) -> list[dict]:
    """Return rollback + demotion events in the last <days> days."""
    fqn = f"{database}.{schema}.{LOG_TABLE}"
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            SELECT
                event_ts,
                agent_fqn,
                version_name,
                alias_set,
                version_before,
                actor,
                env,
                spec_summary,
                extra:event_type::STRING AS event_type
            FROM {fqn}
            WHERE event_ts >= DATEADD('day', -%s, CURRENT_TIMESTAMP())
              AND (
                   extra:event_type::STRING IN ('rollback', 'promote')
                OR spec_summary ILIKE 'ROLLBACK%%'
                OR spec_summary ILIKE 'PROMOTE%%'
              )
            ORDER BY event_ts DESC
            LIMIT 50
            """,
            (days,),
        )
        cols = [c[0].lower() for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as exc:
        # Table may not exist yet in a fresh env.
        logger.warning("Could not query rollback history in %s: %s", fqn, exc)
        return []
    finally:
        cur.close()


def render_markdown(events: list[dict], days: int) -> str:
    rollbacks = [e for e in events if (e.get("event_type") == "rollback") or str(e.get("spec_summary", "")).startswith("ROLLBACK")]
    promotes = [e for e in events if (e.get("event_type") == "promote") or str(e.get("spec_summary", "")).startswith("PROMOTE")]

    # Nothing to show: return empty so the workflow can skip the comment.
    if not rollbacks and not promotes:
        return ""

    lines: list[str] = []
    lines.append(f"### Recent Release Activity (last {days} days)")
    lines.append("")

    if rollbacks:
        lines.append(f"**Rollbacks** ({len(rollbacks)}):")
        lines.append("")
        lines.append("| When | Env | Agent | Rolled back to | By |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")
        for e in rollbacks[:10]:
            ts = e.get("event_ts")
            ts_str = ts.strftime("%Y-%m-%d %H:%M UTC") if hasattr(ts, "strftime") else str(ts)
            fqn_parts = str(e.get("agent_fqn", "")).split(".")
            agent_short = fqn_parts[-1] if fqn_parts else e.get("agent_fqn", "?")
            lines.append(
                f"| {ts_str} | {e.get('env', '?')} | `{agent_short}` | "
                f"`{e.get('version_name', '?')}` | {e.get('actor', '?')} |"
            )
        lines.append("")

    if promotes:
        lines.append(f"**Promotions to production** ({len(promotes)}):")
        lines.append("")
        lines.append("| When | Env | Agent | Version | By |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")
        for e in promotes[:10]:
            ts = e.get("event_ts")
            ts_str = ts.strftime("%Y-%m-%d %H:%M UTC") if hasattr(ts, "strftime") else str(ts)
            fqn_parts = str(e.get("agent_fqn", "")).split(".")
            agent_short = fqn_parts[-1] if fqn_parts else e.get("agent_fqn", "?")
            lines.append(
                f"| {ts_str} | {e.get('env', '?')} | `{agent_short}` | "
                f"`{e.get('version_name', '?')}` | {e.get('actor', '?')} |"
            )
        lines.append("")

    lines.append("_Source: `CORTEX_AGENT_VERSION_LOG` (append-only audit). "
                 "Multiple rollbacks in a short window suggest reviewing "
                 "test coverage on the affected agent before merging._")
    return "\n".join(lines) + "\n"


def _try_query_env(env: str, days: int) -> tuple[list[dict], str]:
    """Attempt to query the audit table for <env>. Returns (events, db_used).
    Empty list on any failure (connection, missing table, access denied)."""
    try:
        config = load_env_config(env)
    except SystemExit:
        return [], ""
    database = get_database(config)
    schema = config["deployment"].get("agent_schema") or config["deployment"].get("schema") or "AGENTS"
    try:
        conn = connect(config)
    except Exception as exc:
        logger.info("[%s] connect failed (non-fatal): %s", env, exc)
        return [], database
    try:
        events = fetch_rollbacks(conn, database, schema, days)
        return events, database
    finally:
        try:
            conn.close()
        except Exception:
            pass


def main() -> int:
    ap = argparse.ArgumentParser(description="Format recent rollback/promote events as a PR comment")
    ap.add_argument("--env", default="prod", help="Primary env config (default: prod; falls back to dev)")
    ap.add_argument("--days", type=int, default=7, help="Look-back window (default: 7)")
    ap.add_argument("--output", default="/tmp/rollback_history.md", help="Output markdown path")
    ap.add_argument("-v", "--verbose", action="count", default=1)
    args = ap.parse_args()
    setup_logging(args.verbose)

    # Try primary env first; if empty or inaccessible, fall back to dev.
    events, db_used = _try_query_env(args.env, args.days)
    if not events and args.env != "dev":
        logger.info("No results from %s (or access denied); falling back to dev", args.env)
        dev_events, dev_db = _try_query_env("dev", args.days)
        if dev_events:
            events = dev_events
            db_used = dev_db

    markdown = render_markdown(events, args.days)
    Path(args.output).write_text(markdown)
    if markdown:
        logger.info("Wrote %s (%d bytes, source=%s)", args.output, len(markdown), db_used)
    else:
        logger.info("No rollback/promote events in last %d days — wrote empty file", args.days)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
