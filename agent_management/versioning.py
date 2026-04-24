"""Cortex Agent Versioning (Private Preview) DDL helpers.

This module is the single place that talks to the Snowflake Cortex Agent
versioning surface:

    ALTER AGENT <fqn> ADD LIVE VERSION FROM LAST
    ALTER AGENT <fqn> MODIFY LIVE VERSION SET SPEC FROM '<yaml>'
    ALTER AGENT <fqn> COMMIT LIVE VERSION
    ALTER AGENT <fqn> MODIFY VERSION <v> SET ALIAS = <alias>
    ALTER AGENT <fqn> DROP VERSION <v>
    SHOW VERSIONS ON AGENT <fqn>
    SHOW ALIASES ON AGENT <fqn>

Every other module (deploy_agents, rollback, snapshot_state, smoke_test)
should route through this module so the exact DDL is tested once and used
everywhere.

There is intentionally no feature flag and no fallback to the legacy
CREATE OR ALTER AGENT path. Accounts without the Private Preview enabled
will raise at the SQL layer.
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


@dataclass(frozen=True)
class VersionInfo:
    name: str            # "VERSION$3"
    created: str | None  # ISO string from SHOW VERSIONS
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
    # Defense in depth: the FQN comes from env config + spec file, but we
    # still refuse anything that doesn't look like a Snowflake identifier path.
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_$]*(\.[A-Za-z_][A-Za-z0-9_$]*)*$", name):
        raise ValueError(f"Invalid {kind}: {name!r}")


def list_versions(conn, agent_fqn: str) -> list[VersionInfo]:
    """Return the agent's committed versions (oldest first)."""
    _assert_identifier(agent_fqn, kind="agent fqn")
    cur = conn.cursor()
    cur.execute(f"SHOW VERSIONS ON AGENT {agent_fqn}")
    rows = _rows_as_dicts(cur)
    versions: list[VersionInfo] = []
    for row in rows:
        name = row.get("name") or row.get("version") or ""
        if not name:
            continue
        versions.append(
            VersionInfo(
                name=str(name),
                created=str(row.get("created_on") or row.get("created") or "") or None,
                comment=str(row.get("comment") or "") or None,
            )
        )
    return versions


def version_exists(conn, agent_fqn: str, version: str) -> bool:
    _assert_version_name(version)
    return any(v.name.upper() == version.upper() for v in list_versions(conn, agent_fqn))


def get_aliases(conn, agent_fqn: str) -> dict[str, str]:
    """Return a mapping of alias -> version name for the agent."""
    _assert_identifier(agent_fqn, kind="agent fqn")
    cur = conn.cursor()
    cur.execute(f"SHOW ALIASES ON AGENT {agent_fqn}")
    rows = _rows_as_dicts(cur)
    out: dict[str, str] = {}
    for row in rows:
        alias = row.get("alias") or row.get("name")
        target = row.get("version") or row.get("target")
        if alias and target:
            out[str(alias)] = str(target)
    return out


def set_alias(conn, agent_fqn: str, version: str, alias: str) -> None:
    """Point ``alias`` at ``version`` on the agent.

    ``alias`` should be one of the names defined in the env config's
    ``agent.aliases`` list (validated, production, latest, …). No implicit
    alias creation — the Private Preview has a fixed alias vocabulary.
    """
    _assert_identifier(agent_fqn, kind="agent fqn")
    _assert_version_name(version)
    _assert_identifier(alias, kind="alias")
    cur = conn.cursor()
    cur.execute(
        f"ALTER AGENT {agent_fqn} MODIFY VERSION {version} SET ALIAS = {alias}"
    )
    logger.info("alias set: %s -> %s on %s", alias, version, agent_fqn)


def drop_version(conn, agent_fqn: str, version: str, *, force: bool = False) -> None:
    """Drop ``version`` on the agent, refusing if it bears any alias unless ``force``."""
    _assert_identifier(agent_fqn, kind="agent fqn")
    _assert_version_name(version)
    if not force:
        aliases = get_aliases(conn, agent_fqn)
        bearing = [a for a, v in aliases.items() if v.upper() == version.upper()]
        if bearing:
            raise RuntimeError(
                f"Refusing to drop {version} on {agent_fqn}; still holds alias(es): {bearing}"
            )
    cur = conn.cursor()
    cur.execute(f"ALTER AGENT {agent_fqn} DROP VERSION {version}")
    logger.info("dropped version: %s on %s", version, agent_fqn)


def commit_version(
    conn,
    agent_fqn: str,
    spec_yaml: str,
    *,
    initial: bool = False,
) -> str:
    """Commit ``spec_yaml`` as a new immutable version. Returns the new VERSION$N.

    When ``initial`` is True we skip the ``FROM LAST`` seed because no prior
    version exists. Callers must supply the flag from their knowledge of
    ``list_versions``; the library does not auto-detect (keeps the function
    straightforward to reason about).
    """
    _assert_identifier(agent_fqn, kind="agent fqn")
    cur = conn.cursor()

    if not initial:
        cur.execute(f"ALTER AGENT {agent_fqn} ADD LIVE VERSION FROM LAST")
    else:
        cur.execute(f"ALTER AGENT {agent_fqn} ADD LIVE VERSION")

    # Use a parameterized SQL string for the spec YAML body.
    cur.execute(
        f"ALTER AGENT {agent_fqn} MODIFY LIVE VERSION SET SPEC FROM %s",
        (spec_yaml,),
    )
    cur.execute(f"ALTER AGENT {agent_fqn} COMMIT LIVE VERSION")

    versions = list_versions(conn, agent_fqn)
    if not versions:
        raise RuntimeError(
            f"commit_version: no versions visible after COMMIT LIVE on {agent_fqn}"
        )
    newest = versions[-1].name
    logger.info("committed new version: %s on %s", newest, agent_fqn)
    return newest


def promote_alias(
    conn,
    agent_fqn: str,
    *,
    from_alias: str,
    to_alias: str,
) -> str:
    """Reassign ``to_alias`` to the version currently under ``from_alias``.

    Returns the version that was promoted.
    """
    aliases = get_aliases(conn, agent_fqn)
    if from_alias not in aliases:
        raise RuntimeError(
            f"promote_alias: {from_alias!r} is not set on {agent_fqn}; "
            f"current aliases: {aliases!r}"
        )
    target_version = aliases[from_alias]
    current_to = aliases.get(to_alias)
    if current_to and current_to.upper() == target_version.upper():
        logger.info("promote_alias: no-op (%s already == %s)", to_alias, target_version)
        return target_version
    set_alias(conn, agent_fqn, target_version, to_alias)
    return target_version


def prune_versions(
    conn,
    agent_fqn: str,
    *,
    keep_last_n: int,
) -> list[str]:
    """Drop committed versions beyond ``keep_last_n`` (oldest first).

    Any version still bearing an alias is skipped. Returns the list of version
    names actually dropped.
    """
    if keep_last_n <= 0:
        raise ValueError("keep_last_n must be positive.")
    versions = list_versions(conn, agent_fqn)
    aliases = get_aliases(conn, agent_fqn)
    aliased = {v.upper() for v in aliases.values()}
    # Oldest first => drop from the front; protect aliased.
    to_consider = versions[:-keep_last_n] if len(versions) > keep_last_n else []
    dropped: list[str] = []
    for v in to_consider:
        if v.name.upper() in aliased:
            logger.info("prune_versions: keeping %s (aliased)", v.name)
            continue
        drop_version(conn, agent_fqn, v.name)
        dropped.append(v.name)
    return dropped


def _cmd_promote(args) -> int:
    """CLI: promote <from-alias> -> <to-alias> on one or all configured agents."""
    from agent_management.utils.config import get_all_configured_agents

    config = load_env_config(args.env)
    conn = connect(config)
    try:
        agents: Iterable[str]
        if args.agent:
            agents = [args.agent if "." in args.agent else get_agent_fqn(config, args.agent)]
        else:
            agents = [get_agent_fqn(config, name) for name in get_all_configured_agents()]
        promoted: dict[str, str] = {}
        for fqn in agents:
            version = promote_alias(conn, fqn, from_alias=args.from_alias, to_alias=args.to_alias)
            promoted[fqn] = version
        print(json.dumps(promoted, indent=2))
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

    list_p = sub.add_parser("list", help="List versions of an agent.")
    list_p.add_argument("--env", required=True)
    list_p.add_argument("--agent", required=True)

    def _cmd_list(args):
        config = load_env_config(args.env)
        conn = connect(config)
        try:
            fqn = args.agent if "." in args.agent else get_agent_fqn(config, args.agent)
            versions = list_versions(conn, fqn)
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

    list_p.set_defaults(func=_cmd_list)

    parser.add_argument("-v", "--verbose", action="count", default=0)
    args = parser.parse_args(argv)
    setup_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
