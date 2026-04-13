"""Deploy Cortex Agents from YAML specs to Snowflake.

Renders Jinja2 templates with environment config, builds the agent spec JSON,
and deploys using ALTER AGENT ... MODIFY LIVE VERSION SET SPECIFICATION when
the agent already exists (preserving eval history and SI bindings), falling
back to CREATE AGENT IF NOT EXISTS for first-time creation.

Usage:
    python -m agent_management.deploy_agents --env dev
    python -m agent_management.deploy_agents --env dev --agent resort_executive
    python -m agent_management.deploy_agents --env dev --dry-run
    python -m agent_management.deploy_agents --env dev --force-create

Implements REQ-003: Agent CI/CD Pipeline.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import yaml

from agent_management import setup_logging
from agent_management.paths import generated_dir, specs_dir
from agent_management.render_template import render_file
from agent_management.utils.config import get_agents_schema, get_budget, get_model, load_env_config
from agent_management.utils.snowflake_client import connect

logger = logging.getLogger(__name__)


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
    model = get_model(config)
    budget = get_budget(config)

    tools = []
    tool_resources = {}

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

    instructions = agent.get("instructions", {})
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


def _validate_spec_json(spec_json: str) -> None:
    if "$$" in spec_json:
        raise ValueError("Agent spec contains '$$' delimiter")


def build_alter_spec_sql(fqn: str, spec_json: str) -> str:
    _validate_spec_json(spec_json)
    return (
        f"ALTER AGENT {fqn}\n"
        f"MODIFY LIVE VERSION SET SPECIFICATION =\n"
        f"$$\n{spec_json}\n$$"
    )


def build_alter_metadata_sql(fqn: str, agent: dict, profile: dict | None = None) -> str | None:
    parts = []
    description = agent.get("description", "").strip()[:200].replace("'", "''")
    if description:
        parts.append(f"COMMENT = '{description}'")
    prof = profile if profile is not None else agent.get("profile", {})
    if prof:
        profile_json = json.dumps(prof).replace("'", "''")
        parts.append(f"PROFILE = '{profile_json}'")
    if not parts:
        return None
    return f"ALTER AGENT {fqn} SET\n" + ",\n".join(f"  {p}" for p in parts)


def build_create_sql(fqn: str, agent: dict, spec_json: str, profile: dict | None = None) -> str:
    _validate_spec_json(spec_json)
    description = agent.get("description", "").strip()[:200].replace("'", "''")
    parts = [f"CREATE AGENT IF NOT EXISTS {fqn}"]
    parts.append(f"COMMENT = '{description}'")
    prof = profile if profile is not None else agent.get("profile", {})
    if prof:
        profile_json = json.dumps(prof).replace("'", "''")
        parts.append(f"PROFILE = '{profile_json}'")
    parts.append("FROM SPECIFICATION")
    parts.append(f"$$\n{spec_json}\n$$")
    return "\n".join(parts)


def build_force_create_sql(fqn: str, agent: dict, spec_json: str, profile: dict | None = None) -> str:
    _validate_spec_json(spec_json)
    description = agent.get("description", "").strip()[:200].replace("'", "''")
    parts = [f"CREATE OR REPLACE AGENT {fqn}"]
    parts.append(f"COMMENT = '{description}'")
    prof = profile if profile is not None else agent.get("profile", {})
    if prof:
        profile_json = json.dumps(prof).replace("'", "''")
        parts.append(f"PROFILE = '{profile_json}'")
    parts.append("FROM SPECIFICATION")
    parts.append(f"$$\n{spec_json}\n$$")
    return "\n".join(parts)


def save_generated(agent_name: str, env_name: str, sql_text: str, spec: dict) -> Path:
    out_dir = generated_dir() / env_name
    out_dir.mkdir(parents=True, exist_ok=True)
    sql_path = out_dir / f"{agent_name}.sql"
    sql_path.write_text(sql_text + "\n")
    spec_path = out_dir / f"{agent_name}_spec.json"
    spec_path.write_text(json.dumps(spec, indent=2) + "\n")
    return sql_path


def main():
    parser = argparse.ArgumentParser(description="Deploy Cortex Agents from YAML")
    parser.add_argument("--env", "-e", help="Environment (dev, qa, prod)")
    parser.add_argument("--agent", "-a", help="Deploy single agent by name")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Generate SQL only")
    parser.add_argument(
        "--force-create", action="store_true",
        help="Use CREATE OR REPLACE instead of ALTER (destroys eval history)",
    )
    args = parser.parse_args()

    setup_logging(1)

    config = load_env_config(args.env)
    agent_files = find_agent_files(args.agent)

    strategy = "CREATE OR REPLACE (forced)" if args.force_create else "ALTER if exists / CREATE if new"
    logger.info("Environment: %s", config['environment'])
    logger.info("Target: %s", get_agents_schema(config))
    logger.info("Agents: %d", len(agent_files))
    logger.info("Strategy: %s", strategy)
    logger.info("=" * 60)

    prepared = []
    for path in agent_files:
        rendered_yaml = render_file(path, config)
        agent = yaml.safe_load(rendered_yaml)
        spec = build_spec(agent, config)
        agent_name, schema_fqn, fqn = resolve_agent_identity(agent, config)
        profile = resolve_profile(agent, config)
        prepared.append({
            "agent": agent,
            "spec": spec,
            "spec_json": json.dumps(spec, indent=2),
            "agent_name": agent_name,
            "schema_fqn": schema_fqn,
            "fqn": fqn,
            "profile": profile,
        })

    if args.dry_run:
        logger.info("\n[DRY RUN] SQL written to %s/", generated_dir() / config['environment'])
        for item in prepared:
            fqn = item["fqn"]
            spec_json = item["spec_json"]
            agent = item["agent"]
            profile = item["profile"]

            if args.force_create:
                sql = build_force_create_sql(fqn, agent, spec_json, profile) + ";"
                label = "CREATE OR REPLACE"
            else:
                alter_sql = build_alter_spec_sql(fqn, spec_json)
                meta_sql = build_alter_metadata_sql(fqn, agent, profile)
                create_sql = build_create_sql(fqn, agent, spec_json, profile)
                sql = (
                    f"-- Strategy: ALTER if agent exists, CREATE if new\n"
                    f"-- === IF AGENT EXISTS ===\n{alter_sql};\n"
                )
                if meta_sql:
                    sql += f"\n{meta_sql};\n"
                sql += f"\n-- === IF AGENT DOES NOT EXIST ===\n{create_sql};"
                label = "ALTER/CREATE"

            out_path = save_generated(item["agent_name"], config["environment"], sql, item["spec"])
            logger.info("\n-- [%s] %s", label, fqn)
            logger.info("-- Written to: %s", out_path)
            print(f"{sql}\n")
        sys.exit(0)

    conn = connect(config, schema=config["deployment"]["agents_schema"])
    cur = conn.cursor()

    success = 0
    failed = 0
    for item in prepared:
        agent = item["agent"]
        spec_json = item["spec_json"]
        agent_name = item["agent_name"]
        schema_fqn = item["schema_fqn"]
        fqn = item["fqn"]
        profile = item["profile"]
        tool_count = len(agent.get("tools", []))

        try:
            if args.force_create:
                method = "CREATE OR REPLACE"
                logger.info("\n[%s] %s (%d tools)...", method, fqn, tool_count)
                cur.execute(build_force_create_sql(fqn, agent, spec_json, profile))
            elif agent_exists(cur, agent_name, schema_fqn):
                method = "ALTER"
                logger.info("\n[%s] %s (%d tools)...", method, fqn, tool_count)
                cur.execute(build_alter_spec_sql(fqn, spec_json))
                meta_sql = build_alter_metadata_sql(fqn, agent, profile)
                if meta_sql:
                    cur.execute(meta_sql)
            else:
                method = "CREATE"
                logger.info("\n[%s] %s (%d tools)...", method, fqn, tool_count)
                cur.execute(build_create_sql(fqn, agent, spec_json, profile))

            save_generated(agent_name, config["environment"],
                           build_alter_spec_sql(fqn, spec_json), item["spec"])
            logger.info("OK")
            success += 1
        except Exception as e:
            logger.error("FAILED — %s", e)
            failed += 1

    logger.info("\n%s", "=" * 60)
    logger.info("Deployed: %d  Failed: %d  Environment: %s", success, failed, config['environment'])

    cur.close()
    conn.close()
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
