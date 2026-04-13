"""Environment and project configuration loader.

Loads project.yml (project-wide defaults) and per-environment configs from
environments/ to provide a typed interface for deployment settings, thresholds,
and Snowflake connection params.

Implements REQ-001: Environment Configuration System.
Implements REQ-010: Library Configuration.
"""
from __future__ import annotations

import os
from typing import Any

import yaml

from agent_management.paths import environments_dir, project_config_path

REQUIRED_FIELDS = [
    "environment",
    "snowflake.role",
    "snowflake.warehouse",
    "deployment.database",
    "deployment.semantic_schema",
    "deployment.agents_schema",
]


def _get_nested(d: dict, dotpath: str) -> Any:
    parts = dotpath.split(".")
    val = d
    for p in parts:
        if not isinstance(val, dict) or p not in val:
            return None
        val = val[p]
    return val


def _validate(config: dict) -> None:
    missing = [f for f in REQUIRED_FIELDS if _get_nested(config, f) is None]
    if missing:
        raise ValueError(
            f"Missing required fields in env config: {', '.join(missing)}"
        )


def load_project_config() -> dict:
    path = project_config_path()
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def load_env_config(env: str | None = None) -> dict:
    env = env or os.environ.get("SNOWFLAKE_ENV", "dev")
    path = environments_dir() / f"{env}.env.yml"
    if not path.exists():
        raise FileNotFoundError(f"Environment config not found: {path}")
    with open(path) as f:
        config = yaml.safe_load(f)
    _validate(config)
    return config


def get_database(config: dict) -> str:
    return config["deployment"]["database"]


def get_semantic_schema(config: dict) -> str:
    return f"{get_database(config)}.{config['deployment']['semantic_schema']}"


def get_agents_schema(config: dict) -> str:
    return f"{get_database(config)}.{config['deployment']['agents_schema']}"


def get_agent_fqn(config: dict, agent_name: str) -> str:
    suffix = _resolve_name_suffix(config)
    name = f"{agent_name.upper()}{suffix.upper()}"
    return f"{get_agents_schema(config)}.{name}"


def _resolve_name_suffix(config: dict) -> str:
    suffix = config.get("agent", {}).get("name_suffix")
    if suffix is not None:
        return suffix
    project = load_project_config()
    env_name = config.get("environment", "")
    return project.get("environments", {}).get(env_name, {}).get("name_suffix", "")


def get_deployment_mode() -> str:
    project = load_project_config()
    return project.get("deployment", {}).get("mode", "single_account")


def get_data_source_env() -> str:
    project = load_project_config()
    return project.get("deployment", {}).get("data_source", "prod")


def get_sv_fqn(config: dict, view_name: str) -> str:
    return f"{get_semantic_schema(config)}.{view_name.upper()}"


def get_thresholds(config: dict) -> dict:
    return config.get("eval", {}).get("thresholds", {})


def get_model(config: dict) -> str:
    return config.get("model", {}).get("orchestration", "claude-sonnet-4-5")


def get_budget(config: dict) -> dict:
    return config.get("orchestration", {}).get("budget", {"seconds": 300, "tokens": 50000})


def get_expected_databases() -> dict[str, str]:
    project = load_project_config()
    envs = project.get("environments", {})
    return {env_name: env_cfg["database"] for env_name, env_cfg in envs.items()}


def get_expected_schemas() -> dict[str, dict[str, str]]:
    project = load_project_config()
    defaults = project.get("defaults", {}).get("schemas", {})
    envs = project.get("environments", {})
    result = {}
    for env_name, env_cfg in envs.items():
        result[env_name] = {
            "semantic": env_cfg.get("semantic_schema", defaults.get("semantic", "SEMANTIC")),
            "agents": env_cfg.get("agents_schema", defaults.get("agents", "AGENTS")),
        }
    return result


def get_eval_source_database(env_name: str | None = None) -> str:
    project = load_project_config()
    db = project.get("eval", {}).get("source_database", "")
    if not db and env_name:
        db = project.get("environments", {}).get(env_name, {}).get("database", "")
    return db


def get_eval_config(config: dict) -> dict:
    project = load_project_config()
    eval_cfg = project.get("eval", {})
    db = eval_cfg.get("source_database") or get_database(config)
    source_agents = eval_cfg.get("source_schemas", {}).get("agents", "AGENTS")
    return {
        "source_database": db,
        "source_marts_schema": f"{db}.{eval_cfg.get('source_schemas', {}).get('marts', 'MARTS')}",
        "source_agents_schema": f"{db}.{source_agents}",
        "stage": f"{db}.{source_agents}.{eval_cfg.get('stage', 'eval_config_stage')}",
        "file_format": f"{db}.{source_agents}.{eval_cfg.get('file_format', 'yaml_file_format')}",
        "warehouse": config["snowflake"]["warehouse"],
    }


def get_raw_tables() -> list[str]:
    project = load_project_config()
    return project.get("raw_tables", [])


def get_project_schemas() -> dict[str, str]:
    project = load_project_config()
    return project.get("defaults", {}).get("schemas", {
        "raw": "RAW",
        "staging": "STAGING",
        "marts": "MARTS",
        "semantic": "SEMANTIC",
        "agents": "AGENTS",
    })
