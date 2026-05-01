"""Cortex Agent Versioning (Private Preview) DDL helpers.

Verified against Snowflake 10.14.103, April 2026. The DDL surface is:

    SHOW VERSIONS IN AGENT <fqn>
        columns: created_on, name, alias, spec_file_path, is_default, comment, profile
        Empty-name row = editable LIVE draft (not yet committed).

    DESCRIBE AGENT <fqn>
        returns aliases as a JSON dict:
          {"DEFAULT": "VERSION$N", "FIRST": "VERSION$1", "LAST": "VERSION$N",
           "<user_alias>": "VERSION$X", ...}

    ALTER AGENT <fqn> ADD LIVE VERSION FROM LAST
        -- creates editable LIVE seeded from the latest committed version
        -- fails if a LIVE already exists

    ALTER AGENT <fqn> MODIFY LIVE VERSION SET SPECIFICATION = $$<yaml>$$
        -- overwrites the LIVE draft with a new spec

    ALTER AGENT <fqn> COMMIT
        -- commits LIVE to a new VERSION$N+1 and clears the draft

    ALTER AGENT <fqn> MODIFY VERSION <name> SET ALIAS = <alias>
        -- atomically (re)assigns the alias to the named version

    ALTER AGENT <fqn> DROP VERSION <name>
        -- NEARLY USELESS: Snowflake forbids dropping any version that is a
        -- base for another version. Since ADD LIVE FROM LAST creates a linear
        -- chain, every version is a base for the next. There is effectively no
        -- version pruning in Private Preview. This module does NOT expose a
        -- prune_versions helper for that reason.

Reserved alias names: FIRST, LAST, LIVE, DEFAULT, and anything starting with
"version$". The system uppercases user aliases when it stores them.

Agent invocation is REST-only: this module does not issue chat requests; see
agent_management.smoke_test for that path.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass
from typing import Iterable

from agent_management import setup_logging
from agent_management.utils.config import get_agent_fqn, load_env_config
from agent_management.utils.snowflake_client import connect

logger = logging.getLogger(__name__)


_VERSION_RE = re.compile(r"^VERSION\$\d+$", re.IGNORECASE)
_RESERVED_ALIASES = frozenset({"FIRST", "LAST", "LIVE", "DEFAULT"})


@dataclass(frozen=True)
class VersionInfo:
    name: str            # "VERSION$3"  (empty string == editable LIVE draft)
    alias: str | None    # single alias currently pointing at this version, if any
    created: str | None
    is_default: bool
    comment: str | None


def _rows_as_dicts(cursor) -> list[dict]:
    cols = [c[0].lower() for c in cursor.description]
    return [dict(zip(cols, r)) for r in cursor.fetchall()]


def _assert_version_name(name: str) -> None:
    if not _VERSION_RE.match(name):
        raise ValueError(
            f"Invalid version name '{name}'. Expected 'VERSION$N' (e.g. VERSION$3)."
        )


def _assert_identifier(name: str, *, kind: str = "identifier") -> None:
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_$]*(\.[A-Za-z_][A-Za-z0-9_$]*)*$", name):
        raise ValueError(f"Invalid {kind}: {name!r}")


def _assert_user_alias(alias: str) -> None:
    _assert_identifier(alias, kind="alias")
    if alias.upper() in _RESERVED_ALIASES:
        raise ValueError(
            f"Alias {alias!r} is reserved by Snowflake "
            f"(reserved: {sorted(_RESERVED_ALIASES)}, plus any 'version$*')."
        )


def list_versions(conn, agent_fqn: str, *, include_live: bool = False) -> list[VersionInfo]:
    """Return the agent's committed versions (oldest first).

    The LIVE draft row (empty ``name``) is excluded by default. Pass
    ``include_live=True`` to include it.
    """
    _assert_identifier(agent_fqn, kind="agent fqn")
    cur = conn.cursor()
    cur.execute(f"SHOW VERSIONS IN AGENT {agent_fqn}")
    rows = _rows_as_dicts(cur)
    versions: list[VersionInfo] = []
    for row in rows:
        name = str(row.get("name") or "")
        if not name and not include_live:
            continue
        alias = row.get("alias")
        is_default_raw = row.get("is_default")
        if isinstance(is_default_raw, str):
            is_default = is_default_raw.strip().lower() == "true"
        else:
            is_default = bool(is_default_raw)
        versions.append(
            VersionInfo(
                name=name,
                alias=str(alias) if alias else None,
                created=str(row.get("created_on") or "") or None,
                is_default=is_default,
                comment=str(row.get("comment") or "") or None,
            )
        )
    # SHOW returns newest-first; reverse for oldest-first consistency.
    versions.reverse()
    return versions


def version_exists(conn, agent_fqn: str, version: str) -> bool:
    _assert_version_name(version)
    return any(v.name.upper() == version.upper() for v in list_versions(conn, agent_fqn))


def get_aliases(conn, agent_fqn: str) -> dict[str, str]:
    """Return alias -> version mapping.

    Reads from ``DESCRIBE AGENT`` which exposes the full alias dict
    (DEFAULT, FIRST, LAST, LATEST, plus user-assigned aliases) as JSON on
    the ``aliases`` column. ``SHOW VERSIONS`` only carries a per-row ``alias``
    value which is frequently empty even when aliases exist, so it is not a
    reliable source for this mapping.

    Alias names come back uppercased.
    """
    _assert_identifier(agent_fqn, kind="agent fqn")
    cur = conn.cursor()
    cur.execute(f"DESCRIBE AGENT {agent_fqn}")
    cols = [c[0].lower() for c in cur.description]
    row = cur.fetchone()
    if not row:
        return {}
    row_dict = dict(zip(cols, row))
    raw = row_dict.get("aliases")
    if not raw:
        return {}
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return {}
    out: dict[str, str] = {}
    for alias, version in (data or {}).items():
        if alias and version:
            out[str(alias).upper()] = str(version).upper()
    return out


def assert_alias_points_to(
    conn,
    agent_fqn: str,
    alias: str,
    expected_version: str,
) -> None:
    """Fail loudly if ``alias`` on ``agent_fqn`` does not point at
    ``expected_version``. Runs after set_alias() to catch alias misses.

    Also verifies the DEFAULT alias is populated — without DEFAULT, REST
    calls to ``/agents/<name>:run`` (no selector) fail with
    ``Version 'live' not found`` and smoke tests silently misroute.
    """
    _assert_identifier(agent_fqn, kind="agent fqn")
    _assert_version_name(expected_version)
    aliases = get_aliases(conn, agent_fqn)
    key = alias.upper()
    actual = aliases.get(key)
    if not actual:
        raise RuntimeError(
            f"post-deploy assertion failed: alias {alias!r} is not set on "
            f"{agent_fqn}. aliases={aliases!r}"
        )
    if actual.upper() != expected_version.upper():
        raise RuntimeError(
            f"post-deploy assertion failed: alias {alias!r} on {agent_fqn} "
            f"points at {actual!r}, expected {expected_version!r}. "
            f"aliases={aliases!r}"
        )
    if "DEFAULT" not in aliases:
        raise RuntimeError(
            f"post-deploy assertion failed: DEFAULT alias missing on "
            f"{agent_fqn}. A committed version must be the DEFAULT or REST "
            f"calls without a selector will fail with 'Version live not found'. "
            f"aliases={aliases!r}"
        )
    logger.info(
        "post-deploy assertion OK: %s[%s]=%s (DEFAULT=%s)",
        agent_fqn, alias, actual, aliases.get("DEFAULT"),
    )


def has_live_draft(conn, agent_fqn: str) -> bool:
    """True if the agent has an uncommitted LIVE draft."""
    _assert_identifier(agent_fqn, kind="agent fqn")
    cur = conn.cursor()
    cur.execute(f"SHOW VERSIONS IN AGENT {agent_fqn}")
    for row in _rows_as_dicts(cur):
        if not str(row.get("name") or ""):
            return True
    return False


def set_version_comment(conn, agent_fqn: str, version: str, comment: str) -> None:
    """Attach a human-readable comment to a committed version.

    The comment is visible in the ``comment`` column of
    ``SHOW VERSIONS IN AGENT``. Use it to pin identity metadata (git SHA,
    PR number, actor, deploy timestamp, one-line summary) to a version so
    operators can answer "what is VERSION$5?" without fetching the spec.

    Snowflake accepts up to ~1KB in a version comment. Keep it short.
    """
    _assert_identifier(agent_fqn, kind="agent fqn")
    _assert_version_name(version)
    # Quote escape single quotes.
    escaped = comment.replace("'", "''")
    cur = conn.cursor()
    cur.execute(
        f"ALTER AGENT {agent_fqn} MODIFY VERSION {version} SET COMMENT = '{escaped}'"
    )


def set_alias(conn, agent_fqn: str, version: str, alias: str) -> None:
    """Point ``alias`` at ``version`` on the agent.

    The operation is atomic: if ``alias`` currently points at a different
    version, the server reassigns it in one DDL.
    """
    _assert_identifier(agent_fqn, kind="agent fqn")
    _assert_version_name(version)
    _assert_user_alias(alias)
    cur = conn.cursor()
    cur.execute(
        f"ALTER AGENT {agent_fqn} MODIFY VERSION {version} SET ALIAS = {alias}"
    )
    logger.info("alias set: %s -> %s on %s", alias, version, agent_fqn)


def modify_live_spec(conn, agent_fqn: str, spec_yaml: str) -> None:
    """Overwrite the LIVE draft spec with ``spec_yaml``.

    Uses a $$...$$ string literal to match the Snowflake convention for
    multi-line YAML/JSON payloads. Raises if the YAML contains '$$'.
    """
    _assert_identifier(agent_fqn, kind="agent fqn")
    if "$$" in spec_yaml:
        raise ValueError("spec_yaml contains '$$' delimiter; cannot embed in DDL")
    cur = conn.cursor()
    cur.execute(
        f"ALTER AGENT {agent_fqn} MODIFY LIVE VERSION SET SPECIFICATION = $$\n{spec_yaml}\n$$"
    )


def add_live_from_last(conn, agent_fqn: str) -> None:
    """Seed an editable LIVE draft from the last committed version."""
    _assert_identifier(agent_fqn, kind="agent fqn")
    cur = conn.cursor()
    cur.execute(f"ALTER AGENT {agent_fqn} ADD LIVE VERSION FROM LAST")


def commit_live(conn, agent_fqn: str) -> str:
    """Commit the LIVE draft to a new VERSION$N and return its name."""
    _assert_identifier(agent_fqn, kind="agent fqn")
    cur = conn.cursor()
    cur.execute(f"ALTER AGENT {agent_fqn} COMMIT")
    versions = list_versions(conn, agent_fqn)
    if not versions:
        raise RuntimeError(
            f"commit_live: no versions visible after COMMIT on {agent_fqn}"
        )
    # Newest committed version = the one just created. After reverse() oldest-first,
    # so take the last element.
    newest = versions[-1].name
    logger.info("committed new version: %s on %s", newest, agent_fqn)
    return newest


def commit_version(
    conn,
    agent_fqn: str,
    spec_yaml: str,
    *,
    seed_from_last: bool = True,
) -> str:
    """High-level helper: (optionally seed LIVE) -> MODIFY -> COMMIT.

    ``seed_from_last=False`` skips ``ADD LIVE VERSION FROM LAST`` — use this on
    first-time deploys where ``CREATE AGENT`` auto-created an empty LIVE draft
    that we can overwrite directly.
    """
    if seed_from_last and not has_live_draft(conn, agent_fqn):
        add_live_from_last(conn, agent_fqn)
    elif not seed_from_last and not has_live_draft(conn, agent_fqn):
        # Nothing to modify; the caller is wrong about the state.
        raise RuntimeError(
            f"commit_version(seed_from_last=False): no LIVE draft on {agent_fqn}. "
            "For fresh agents, call CREATE AGENT first."
        )
    modify_live_spec(conn, agent_fqn, spec_yaml)
    return commit_live(conn, agent_fqn)


def promote_alias(
    conn,
    agent_fqn: str,
    *,
    from_alias: str,
    to_alias: str,
) -> str:
    """Reassign ``to_alias`` to the version currently under ``from_alias``."""
    aliases = get_aliases(conn, agent_fqn)
    key = from_alias.upper()
    if key not in aliases:
        raise RuntimeError(
            f"promote_alias: {from_alias!r} is not set on {agent_fqn}; "
            f"current aliases: {aliases!r}"
        )
    target_version = aliases[key]
    current_to = aliases.get(to_alias.upper())
    if current_to and current_to.upper() == target_version.upper():
        logger.info("promote_alias: no-op (%s already == %s)", to_alias, target_version)
        return target_version
    set_alias(conn, agent_fqn, target_version, to_alias)
    return target_version


def _cmd_log(args) -> int:
    """CLI: show recent deploy events (joined with current aliases/comments)."""
    from agent_management.version_log import list_log

    config = load_env_config(args.env)
    conn = connect(config)
    try:
        agent_filter = None
        if args.agent:
            agent_filter = args.agent if "." in args.agent else get_agent_fqn(config, args.agent)

        rows = list_log(
            conn,
            database=config["deployment"]["database"],
            schema=config["deployment"]["agents_schema"],
            agent_fqn=agent_filter,
            limit=args.limit,
        )
        if args.json:
            print(json.dumps(rows, indent=2, default=str))
            return 0

        if not rows:
            print("(no deploy events found — audit table may not exist yet)")
        else:
            header = f"{'event_ts':25} {'agent':45} {'version':11} {'alias':10} {'sha':8} {'pr':5} {'actor':18} {'summary'}"
            print(header)
            print("-" * len(header))
            for r in rows:
                ts = str(r.get("event_ts") or "")[:24]
                fqn = str(r.get("agent_fqn") or "")[:45]
                v = str(r.get("version_name") or "")[:11]
                alias = str(r.get("alias_set") or "")[:10]
                sha = (str(r.get("git_sha") or "") or "")[:7]
                pr = str(r.get("pr_number") or "") or ""
                actor = str(r.get("actor") or "")[:18]
                summary = str(r.get("spec_summary") or "")[:60]
                print(f"{ts:25} {fqn:45} {v:11} {alias:10} {sha:8} {pr:5} {actor:18} {summary}")

        # Also surface the *current* state (SHOW VERSIONS)
        if agent_filter:
            print()
            print("Current state (SHOW VERSIONS):")
            versions = list_versions(conn, agent_filter)
            aliases = get_aliases(conn, agent_filter)
            for v in versions:
                # map this version to any alias that currently points here
                alias_here = next((a for a, tgt in aliases.items() if tgt.upper() == v.name.upper()), "")
                print(f"  {v.name:12} alias={alias_here:10} {v.comment or '(no comment)'}")
    finally:
        conn.close()
    return 0


def _cmd_promote(args) -> int:
    from agent_management.utils.config import get_all_configured_agents
    from agent_management.version_log import discover_identity, record_deploy

    config = load_env_config(args.env)
    conn = connect(config)
    try:
        agents: Iterable[str]
        if args.agent:
            agents = [args.agent if "." in args.agent else get_agent_fqn(config, args.agent)]
        else:
            agents = [get_agent_fqn(config, name) for name in get_all_configured_agents()]

        identity = discover_identity(args.env)
        promoted: dict[str, str] = {}
        for fqn in agents:
            # Capture previous holder of to_alias before move, for audit.
            before = get_aliases(conn, fqn)
            prev_on_to = before.get(args.to_alias.upper())
            version = promote_alias(
                conn, fqn, from_alias=args.from_alias, to_alias=args.to_alias
            )
            promoted[fqn] = version
            # Append audit row so `versioning log` shows the promotion.
            try:
                record_deploy(
                    conn,
                    database=config["deployment"]["database"],
                    schema=config["deployment"]["agents_schema"],
                    agent_fqn=fqn,
                    version_name=version,
                    alias_set=args.to_alias,
                    identity=identity,
                    first_deploy=False,
                    version_before=prev_on_to,
                    spec_summary=(
                        f"PROMOTE: {args.from_alias} -> {args.to_alias} "
                        f"({prev_on_to or '<unset>'} -> {version})"
                    ),
                    extra={"event_type": "promote",
                           "from_alias": args.from_alias,
                           "to_alias": args.to_alias},
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("promote audit append failed (non-fatal): %s", exc)
        print(json.dumps(promoted, indent=2))
    finally:
        conn.close()
    return 0


def _cmd_list(args) -> int:
    config = load_env_config(args.env)
    conn = connect(config)
    try:
        fqn = args.agent if "." in args.agent else get_agent_fqn(config, args.agent)
        versions = list_versions(conn, fqn, include_live=args.include_live)
        aliases = get_aliases(conn, fqn)
        out = {
            "agent": fqn,
            "versions": [v.__dict__ for v in versions],
            "aliases": aliases,
        }
        print(json.dumps(out, indent=2, default=str))
    finally:
        conn.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cortex Agent Versioning helpers.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("promote", help="Reassign an alias to the version under another alias.")
    p.add_argument("--env", required=True)
    p.add_argument("--from", dest="from_alias", required=True)
    p.add_argument("--to", dest="to_alias", required=True)
    p.add_argument("--agent", help="Agent FQN or short name; all if omitted.")
    p.set_defaults(func=_cmd_promote)

    list_p = sub.add_parser("list", help="List versions and aliases of an agent.")
    list_p.add_argument("--env", required=True)
    list_p.add_argument("--agent", required=True)
    list_p.add_argument("--include-live", action="store_true")
    list_p.set_defaults(func=_cmd_list)

    log_p = sub.add_parser("log", help="Show deploy audit log (from CORTEX_AGENT_VERSION_LOG).")
    log_p.add_argument("--env", required=True)
    log_p.add_argument("--agent", help="Filter to one agent (short name or FQN).")
    log_p.add_argument("--limit", type=int, default=25)
    log_p.add_argument("--json", action="store_true")
    log_p.set_defaults(func=_cmd_log)

    parser.add_argument("-v", "--verbose", action="count", default=0)
    args = parser.parse_args(argv)
    setup_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
