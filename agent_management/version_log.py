"""Audit log of agent deploys: what went live, when, from where.

Each row in ``<db>.<agents_schema>.CORTEX_AGENT_VERSION_LOG`` captures a single
deploy event, including the git SHA and PR number, so operators can answer:

  - What is VERSION$5? (which spec, which PR, who deployed, when)
  - Which version is currently holding the `production` alias?
  - Show me the deploy history for RESORT_EXECUTIVE in the last 30 days.

The table is append-only. Rows are never updated in place.

Schema:

    CREATE TABLE CORTEX_AGENT_VERSION_LOG (
        event_ts TIMESTAMP_TZ,
        agent_fqn VARCHAR,
        version_name VARCHAR,
        alias_set VARCHAR,
        git_sha VARCHAR(40),
        git_ref VARCHAR,
        pr_number INT,
        actor VARCHAR,
        env VARCHAR,
        first_deploy BOOLEAN,
        version_before VARCHAR,
        spec_summary VARCHAR,
        extra VARIANT
    );
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


VERSION_LOG_TABLE = "CORTEX_AGENT_VERSION_LOG"


@dataclass
class DeployIdentity:
    """Metadata attached to a deploy event.

    Most fields are discovered from environment variables set by GitHub
    Actions (``GITHUB_SHA``, ``GITHUB_REF_NAME``, ``GITHUB_ACTOR``,
    ``GITHUB_RUN_ID``, ``GITHUB_REPOSITORY``), with fallbacks to ``git``
    invocations when running locally.
    """

    git_sha: str
    git_ref: str | None
    pr_number: int | None
    actor: str
    env: str
    ci_run_url: str | None = None

    def short_sha(self) -> str:
        return (self.git_sha or "local")[:7]


def _git(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True, text=True, check=False, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:  # noqa: BLE001
        return None
    return None


def discover_identity(env: str, *, actor_fallback: str = "") -> DeployIdentity:
    """Collect identity metadata from env + git with graceful fallbacks."""
    git_sha = (
        os.environ.get("GITHUB_SHA")
        or _git("rev-parse", "HEAD")
        or "unknown"
    )
    git_ref = (
        os.environ.get("GITHUB_REF_NAME")
        or _git("rev-parse", "--abbrev-ref", "HEAD")
    )
    actor = (
        os.environ.get("GITHUB_ACTOR")
        or os.environ.get("USER")
        or actor_fallback
        or "unknown"
    )
    pr_raw = os.environ.get("GITHUB_PR_NUMBER") or os.environ.get("PR_NUMBER")
    pr_number: int | None
    try:
        pr_number = int(pr_raw) if pr_raw else None
    except ValueError:
        pr_number = None

    run_id = os.environ.get("GITHUB_RUN_ID")
    repo = os.environ.get("GITHUB_REPOSITORY")
    ci_run_url = (
        f"https://github.com/{repo}/actions/runs/{run_id}"
        if run_id and repo else None
    )

    return DeployIdentity(
        git_sha=git_sha,
        git_ref=git_ref,
        pr_number=pr_number,
        actor=actor,
        env=env,
        ci_run_url=ci_run_url,
    )


def format_version_comment(identity: DeployIdentity, *, summary: str | None = None) -> str:
    """Produce a short one-line comment for MODIFY VERSION SET COMMENT.

    Format::

        <short-sha> [PR#<n>] <env> <iso-ts> by <actor>[: <summary>]

    Keep summary under ~80 chars; the overall comment string is truncated to
    ~500 chars for safety.
    """
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    pr_tag = f" PR#{identity.pr_number}" if identity.pr_number else ""
    base = f"{identity.short_sha()}{pr_tag} {identity.env} {ts} by {identity.actor}"
    if summary:
        base = f"{base}: {summary}"
    return base[:500]


def ensure_log_table(conn, database: str, schema: str) -> str:
    """Create the audit table if missing. Returns its FQN."""
    fqn = f"{database}.{schema}.{VERSION_LOG_TABLE}"
    cur = conn.cursor()
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {fqn} (
            event_ts TIMESTAMP_TZ DEFAULT CURRENT_TIMESTAMP,
            agent_fqn VARCHAR NOT NULL,
            version_name VARCHAR NOT NULL,
            alias_set VARCHAR,
            git_sha VARCHAR(40),
            git_ref VARCHAR,
            pr_number INT,
            actor VARCHAR,
            env VARCHAR,
            first_deploy BOOLEAN,
            version_before VARCHAR,
            spec_summary VARCHAR,
            extra VARIANT
        )
        """
    )
    return fqn


def record_deploy(
    conn,
    *,
    database: str,
    schema: str,
    agent_fqn: str,
    version_name: str,
    alias_set: str | None,
    identity: DeployIdentity,
    first_deploy: bool,
    version_before: str | None,
    spec_summary: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Append a deploy event to the audit table. Never raises — audit-only."""
    try:
        fqn = ensure_log_table(conn, database, schema)
        cur = conn.cursor()
        extra_json = json.dumps(extra) if extra else None
        cur.execute(
            f"""
            INSERT INTO {fqn}
                (agent_fqn, version_name, alias_set, git_sha, git_ref, pr_number,
                 actor, env, first_deploy, version_before, spec_summary, extra)
            SELECT %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, PARSE_JSON(%s)
            """,
            (
                agent_fqn, version_name, alias_set,
                identity.git_sha, identity.git_ref, identity.pr_number,
                identity.actor, identity.env, first_deploy,
                version_before, spec_summary, extra_json,
            ),
        )
        logger.info("audit: appended %s %s to %s", agent_fqn, version_name, fqn)
    except Exception as exc:  # noqa: BLE001 - never block deploy on audit failure
        logger.warning("audit append failed (non-fatal): %s", exc)


def list_log(
    conn,
    *,
    database: str,
    schema: str,
    agent_fqn: str | None = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    """Return recent deploy events, newest first."""
    fqn = f"{database}.{schema}.{VERSION_LOG_TABLE}"
    cur = conn.cursor()
    try:
        cur.execute(f"DESC TABLE {fqn}")
    except Exception:
        return []
    clause = ""
    params: tuple = ()
    if agent_fqn:
        clause = "WHERE agent_fqn = %s"
        params = (agent_fqn,)
    cur.execute(
        f"""
        SELECT event_ts, agent_fqn, version_name, alias_set, git_sha,
               pr_number, actor, env, first_deploy, version_before, spec_summary
        FROM {fqn}
        {clause}
        ORDER BY event_ts DESC
        LIMIT {int(limit)}
        """,
        params,
    )
    cols = [c[0].lower() for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]
