"""Deploy Cortex Agents from YAML specs using Cortex Agent Versioning.

This is the single deployment path. Every deploy:

  1. snapshots the agent state  (see agent_management.snapshot_state)
  2. ADD LIVE VERSION FROM LAST (or ADD LIVE VERSION on first-time create)
  3. MODIFY LIVE VERSION SET SPEC FROM '<yaml>'
  4. COMMIT LIVE VERSION        (creates VERSION$N)
  5. MODIFY VERSION LAST SET ALIAS = <deploy_alias>
  6. prune_versions(keep_last_n)

There is intentionally NO legacy CREATE OR ALTER AGENT path and NO feature
flag. If the Cortex Agent Versioning Private Preview is not enabled on the
account, the SQL will raise and the deploy will fail loudly.

Implements REQ-003: Agent CI/CD Pipeline (versioning era).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from agent_management import setup_logging
from agent_management.paths import generated_dir, specs_dir
from agent_management.render_template import render_file
from agent_management.utils.config import (
    get_agents_schema,
    get_budget,
    get_model,
    load_env_config,
    load_project_config,
)
from agent_management.utils.snowflake_client import connect
from agent_management.agents.versioning import (
    assert_alias_points_to,
    commit_version,
    has_live_draft,
    list_versions,
    set_alias,
    set_version_comment,
)
from agent_management.agents.version_log import (
    DeployIdentity,
    discover_identity,
    format_version_comment,
    record_deploy,
)

logger = logging.getLogger(__name__)


@dataclass
class DeployResult:
    agent_fqn: str
    env: str
    version_before: str | None
    version_after: str
    alias_moved: str
    was_first_deploy: bool
    identity: DeployIdentity | None = None
    version_comment: str | None = None


def find_agent_files(agent: str | None) -> list[Path]:
    if agent:
        path = specs_dir() / f"{agent}.yml"
        if not path.exists():
            path = specs_dir() / f"{agent}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Agent spec not found: {agent}")
        return [path]
    files = sorted(specs_dir().glob("*.y*ml"))
    if not files:
        logger.warning("No agent specs found in %s", specs_dir())
        sys.exit(0)
    return files


def build_spec(agent: dict, config: dict) -> dict:
    """Build the Cortex Agent spec dict from a parsed YAML agent definition."""
    model = get_model(config)
    budget = get_budget(config)

    tools = []
    tool_resources: dict = {}

    for tool in agent.get("tools", []):
        tool_name = tool["name"]
        tool_type = tool["type"]
        description = tool.get("description", "").strip()
        warehouse = tool.get("warehouse", config["snowflake"]["warehouse"])

        tools.append({
            "tool_spec": {
                "type": tool_type,
                "name": tool_name,
                "description": description,
            }
        })

        if tool_type == "cortex_analyst_text_to_sql":
            tool_resources[tool_name] = {
                "semantic_view": tool["semantic_view"],
                "execution_environment": {
                    "type": "warehouse",
                    "warehouse": warehouse,
                    "query_timeout": tool.get("query_timeout", 299),
                },
            }
        elif tool_type == "cortex_search":
            tool_resources[tool_name] = {
                "search_service": tool["search_service"],
                "execution_environment": {
                    "type": "warehouse",
                    "warehouse": warehouse,
                    "query_timeout": tool.get("query_timeout", 299),
                },
            }
        elif tool_type == "generic":
            tool_resources[tool_name] = {
                "type": "procedure",
                "identifier": tool["identifier"],
                "execution_environment": {
                    "type": "warehouse",
                    "warehouse": warehouse,
                    "query_timeout": tool.get("query_timeout", 300),
                },
            }

    instructions = agent.get("instructions", {}) or {}
    spec_instructions: dict = {}
    if instructions.get("orchestration"):
        spec_instructions["orchestration"] = instructions["orchestration"].strip()
    if instructions.get("response"):
        spec_instructions["response"] = instructions["response"].strip()
    sample_qs = agent.get("sample_questions", [])
    if sample_qs:
        spec_instructions["sample_questions"] = [{"question": q} for q in sample_qs]

    return {
        "models": {"orchestration": model},
        "orchestration": {"budget": {
            "seconds": budget.get("seconds", 300),
            "tokens": budget.get("tokens", 50000),
        }},
        "instructions": spec_instructions,
        "tools": tools,
        "tool_resources": tool_resources,
    }


def resolve_agent_identity(agent: dict, config: dict) -> tuple[str, str, str]:
    metadata = agent.get("metadata", {})
    agent_name = metadata["name"].upper()
    suffix = config.get("agent", {}).get("name_suffix", "")
    if suffix:
        agent_name = f"{agent_name}{suffix.upper()}"
    schema_fqn = get_agents_schema(config)
    fqn = f"{schema_fqn}.{agent_name}"
    return agent_name, schema_fqn, fqn


def resolve_profile(agent: dict, config: dict) -> dict:
    profile = dict(agent.get("profile", {}))
    suffix = config.get("agent", {}).get("name_suffix", "")
    if suffix and "display_name" in profile:
        env_label = suffix.strip("_").upper()
        profile["display_name"] = f"{profile['display_name']} [{env_label}]"
    return profile


def agent_exists(cur, agent_name: str, schema_fqn: str) -> bool:
    try:
        cur.execute(f"SHOW AGENTS LIKE '{agent_name}' IN SCHEMA {schema_fqn}")
        return cur.fetchone() is not None
    except Exception:
        return False


def _create_agent_shell(cur, fqn: str, agent: dict, profile: dict | None) -> None:
    """First-time only: create an empty agent so ADD LIVE VERSION can seed it."""
    description = agent.get("description", "").strip()[:200].replace("'", "''")
    parts = [f"CREATE AGENT IF NOT EXISTS {fqn}"]
    if description:
        parts.append(f"COMMENT = '{description}'")
    if profile:
        profile_json = json.dumps(profile).replace("'", "''")
        parts.append(f"PROFILE = '{profile_json}'")
    cur.execute("\n".join(parts))


def _apply_metadata(cur, fqn: str, agent: dict, profile: dict | None) -> None:
    parts = []
    description = agent.get("description", "").strip()[:200].replace("'", "''")
    if description:
        parts.append(f"COMMENT = '{description}'")
    if profile:
        profile_json = json.dumps(profile).replace("'", "''")
        parts.append(f"PROFILE = '{profile_json}'")
    if not parts:
        return
    cur.execute(f"ALTER AGENT {fqn} SET\n" + ",\n".join(f"  {p}" for p in parts))


def _save_generated(agent_name: str, env_name: str, spec: dict) -> Path:
    out_dir = generated_dir() / env_name
    out_dir.mkdir(parents=True, exist_ok=True)
    spec_path = out_dir / f"{agent_name}_spec.json"
    spec_path.write_text(json.dumps(spec, indent=2) + "\n")
    return spec_path


def _deploy_alias(config: dict) -> str:
    agent_cfg = config.get("agent", {}) or {}
    alias = agent_cfg.get("deploy_alias")
    if not alias:
        raise ValueError(
            "Env config is missing agent.deploy_alias. "
            "Set to 'latest' for dev or 'validated' for prod."
        )
    return alias


def _keep_last_n(config: dict) -> int:
    # Retained config hook, but version pruning is not possible under Cortex
    # Agent Versioning Private Preview (see agent_management/versioning.py).
    # Value is reported in deploy logs only.
    project = load_project_config()
    versioning_cfg = project.get("agent_versioning", {})
    return int(
        config.get("agent", {}).get("keep_last_n_versions")
        or versioning_cfg.get("keep_last_n_versions", 10)
    )


def deploy_agent(
    agent_fqn: str,
    spec_path: Path | str,
    *,
    env: str,
    deploy_alias: str | None = None,
    connection=None,
    dry_run: bool = False,
) -> DeployResult:
    """Deploy a single agent via the versioning path.

    Args:
        agent_fqn: target agent FQN (DB.SCHEMA.AGENT).
        spec_path: path to the YAML spec file.
        env: environment name (dev/prod) for config + connection.
        deploy_alias: alias to move after commit. Defaults to env's
            ``agent.deploy_alias``.
        connection: optional pre-opened Snowflake connection (tests).
        dry_run: if True, renders SQL and returns without executing.

    Raises when the underlying Cortex Agent Versioning DDL fails — there is no
    fallback path.
    """
    config = load_env_config(env)
    if deploy_alias is None:
        deploy_alias = _deploy_alias(config)

    rendered_yaml = render_file(str(spec_path), config)
    agent_dict = yaml.safe_load(rendered_yaml)
    spec = build_spec(agent_dict, config)
    spec_json = json.dumps(spec, indent=2)
    if "$$" in spec_json:
        raise ValueError("Agent spec contains '$$' delimiter")
    # The spec is emitted as YAML inside a $$...$$ block in MODIFY LIVE
    # VERSION SET SPECIFICATION. Strip the outermost quotes Snowflake expects.
    spec_yaml = yaml.safe_dump(spec, sort_keys=False)
    if "$$" in spec_yaml:
        raise ValueError("Rendered spec YAML contains '$$' delimiter")

    agent_name, schema_fqn, _computed_fqn = resolve_agent_identity(agent_dict, config)
    profile = resolve_profile(agent_dict, config)
    _save_generated(agent_name, config["environment"], spec)

    if dry_run:
        logger.info(
            "[DRY RUN] would deploy %s (alias=%s):\n%s",
            agent_fqn,
            deploy_alias,
            "\n".join([
                f"  -- IF AGENT ALREADY HAS A COMMITTED VERSION:",
                f"  ALTER AGENT {agent_fqn} ADD LIVE VERSION FROM LAST;",
                f"  ALTER AGENT {agent_fqn} MODIFY LIVE VERSION SET SPECIFICATION = $$<yaml>$$;",
                f"  ALTER AGENT {agent_fqn} COMMIT;",
                f"  -- ELSE (first-time deploy, CREATE AGENT auto-creates empty VERSION$1 + LIVE):",
                f"  CREATE AGENT IF NOT EXISTS {agent_fqn};",
                f"  ALTER AGENT {agent_fqn} MODIFY LIVE VERSION SET SPECIFICATION = $$<yaml>$$;",
                f"  ALTER AGENT {agent_fqn} COMMIT;",
                f"  -- THEN (both paths):",
                f"  ALTER AGENT {agent_fqn} MODIFY VERSION <new> SET ALIAS = {deploy_alias};",
            ])
        )
        return DeployResult(
            agent_fqn=agent_fqn,
            env=env,
            version_before=None,
            version_after="DRY_RUN",
            alias_moved=deploy_alias,
            was_first_deploy=False,
        )

    close_after = False
    conn = connection
    if conn is None:
        conn = connect(config, schema=config["deployment"]["agents_schema"])
        close_after = True

    try:
        cur = conn.cursor()
        existed = agent_exists(cur, agent_name, schema_fqn)
        if not existed:
            _create_agent_shell(cur, agent_fqn, agent_dict, profile)

        # Decide whether we need to seed a fresh LIVE.
        # - Fresh CREATE AGENT: already has empty VERSION$1 + LIVE draft. Don't ADD.
        # - Existing agent with no pending LIVE: ADD LIVE FROM LAST.
        # - Existing agent with a pending LIVE (operator left it mid-edit): reuse it.
        was_first_deploy = not existed
        committed_versions = list_versions(conn, agent_fqn)
        version_before = committed_versions[-1].name if committed_versions else None
        live_draft_exists = has_live_draft(conn, agent_fqn)

        if was_first_deploy or live_draft_exists:
            seed_from_last = False
        else:
            seed_from_last = True

        version_after = commit_version(
            conn, agent_fqn, spec_yaml, seed_from_last=seed_from_last,
        )
        _apply_metadata(cur, agent_fqn, agent_dict, profile)
        set_alias(conn, agent_fqn, version_after, deploy_alias)

        # Post-deploy invariant: the deploy alias points at the version we
        # just committed AND a DEFAULT alias exists. Without DEFAULT, the bare
        # REST path /agents/<name>:run fails with "Version 'live' not found"
        # and smoke tests become misleading.
        assert_alias_points_to(conn, agent_fqn, deploy_alias, version_after)

        # Attach identity metadata to the new version so "what is VERSION$N?"
        # is answerable from SHOW VERSIONS alone.
        identity = discover_identity(env)
        agent_short = agent_dict.get("metadata", {}).get("name", "agent")
        spec_summary_hint = agent_dict.get("description", "").strip().splitlines()[0][:80] \
            if agent_dict.get("description") else None
        summary = f"{agent_short}: {spec_summary_hint}" if spec_summary_hint else agent_short
        version_comment = format_version_comment(identity, summary=summary)
        try:
            set_version_comment(conn, agent_fqn, version_after, version_comment)
        except Exception as exc:  # noqa: BLE001 — comment is metadata, not critical
            logger.warning("could not set version comment on %s: %s", version_after, exc)

        # Append to the audit table (best-effort; never blocks deploy).
        record_deploy(
            conn,
            database=config["deployment"]["database"],
            schema=config["deployment"]["agents_schema"],
            agent_fqn=agent_fqn,
            version_name=version_after,
            alias_set=deploy_alias,
            identity=identity,
            first_deploy=was_first_deploy,
            version_before=version_before,
            spec_summary=spec_summary_hint,
            extra={
                "tool_count": len(agent_dict.get("tools", [])),
                "sample_question_count": len(agent_dict.get("sample_questions", [])),
            },
        )

        # No prune_versions: the Private Preview forbids dropping versions that
        # are a base for another (i.e. all versions in the linear chain).
        keep_last_n = _keep_last_n(config)
        logger.info(
            "deployed %s: %s -> %s (alias=%s, first_deploy=%s, comment=%r)",
            agent_fqn,
            version_before or "<none>",
            version_after,
            deploy_alias,
            was_first_deploy,
            version_comment,
        )
        return DeployResult(
            agent_fqn=agent_fqn,
            env=env,
            version_before=version_before,
            version_after=version_after,
            alias_moved=deploy_alias,
            was_first_deploy=was_first_deploy,
            identity=identity,
            version_comment=version_comment,
        )
    finally:
        if close_after:
            conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deploy Cortex Agents (versioning path).")
    parser.add_argument("--env", "-e", required=True)
    parser.add_argument("--agent", "-a", help="Deploy a single agent by short name.")
    parser.add_argument("--alias", help="Override the deploy_alias from env config.")
    parser.add_argument("--dry-run", "-n", action="store_true")
    parser.add_argument("-v", "--verbose", action="count", default=1)
    args = parser.parse_args(argv)
    setup_logging(args.verbose)

    config = load_env_config(args.env)
    agent_files = find_agent_files(args.agent)

    logger.info("Environment: %s", config["environment"])
    logger.info("Target schema: %s", get_agents_schema(config))
    logger.info("Agents: %d  Alias: %s", len(agent_files), args.alias or _deploy_alias(config))
    logger.info("=" * 60)

    success = 0
    failed = 0
    results: list[DeployResult] = []
    for path in agent_files:
        rendered_yaml = render_file(str(path), config)
        agent_dict = yaml.safe_load(rendered_yaml)
        _, _, fqn = resolve_agent_identity(agent_dict, config)
        try:
            result = deploy_agent(
                agent_fqn=fqn,
                spec_path=path,
                env=args.env,
                deploy_alias=args.alias,
                dry_run=args.dry_run,
            )
            results.append(result)
            success += 1
        except Exception as exc:  # noqa: BLE001
            logger.error("FAILED %s — %s", fqn, exc)
            failed += 1

    logger.info("\n%s", "=" * 60)
    logger.info("Deployed: %d  Failed: %d  Environment: %s", success, failed, config["environment"])
    if results:
        for r in results:
            logger.info(
                "  %s: %s -> %s (alias=%s)",
                r.agent_fqn, r.version_before or "<none>", r.version_after, r.alias_moved,
            )
    return 1 if failed > 0 else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
