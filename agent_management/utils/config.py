"""Environment and project configuration loader.

Loads project.yml (project-wide defaults) and per-environment configs from
environments/ to provide a typed interface for deployment settings, thresholds,
and Snowflake connection params.

Implements REQ-001: Environment Configuration System.
Implements REQ-010: Library Configuration.
"""
from __future__ import annotations

import os
from pathlib import Path
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


def load_project_config(path: str | os.PathLike | None = None) -> dict:
    """Load project-level config.

    Resolution order:
      1. explicit ``path`` argument
      2. ``AGENT_MGMT_PROJECT_CONFIG`` env var (handled by ``project_config_path``)
      3. repo-root ``project.yml`` discovery (legacy compatibility)

    The explicit path keeps the package usable after ``pip install`` without
    requiring callers to run from this reference repository.
    """
    cfg_path = Path(path).expanduser().resolve() if path else project_config_path()
    if not cfg_path.exists():
        return {}
    with open(cfg_path) as f:
        return yaml.safe_load(f) or {}


def load_env_config(
    env: str | None = None,
    path: str | os.PathLike | None = None,
) -> dict:
    """Load an environment config.

    Resolution order:
      1. explicit ``path`` argument
      2. ``AGENT_MGMT_ENV_CONFIG`` env var
      3. ``environments/<env>.env.yml`` under ``AGENT_MGMT_ENVIRONMENTS_DIR``
         or the discovered project root

    ``env`` is only used for step 3. If an explicit path is supplied, the file's
    own ``environment`` field is authoritative.
    """
    if path:
        cfg_path = Path(path).expanduser().resolve()
    elif os.environ.get("AGENT_MGMT_ENV_CONFIG"):
        cfg_path = Path(os.environ["AGENT_MGMT_ENV_CONFIG"]).expanduser().resolve()
    else:
        env = env or os.environ.get("SNOWFLAKE_ENV", "dev")
        cfg_path = environments_dir() / f"{env}.env.yml"
    if not cfg_path.exists():
        raise FileNotFoundError(f"Environment config not found: {cfg_path}")
    with open(cfg_path) as f:
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


def discover_vqr_views() -> list[str]:
    from agent_management.paths import sv_verified_queries_dir
    vqr_dir = sv_verified_queries_dir()
    return sorted(p.stem.upper() for p in vqr_dir.glob("sem_*.yaml"))


def get_agent_semantic_views(agent_name: str) -> list[str]:
    project = load_project_config()
    agents = project.get("agents", {})
    agent = agents.get(agent_name.lower()) or agents.get(agent_name.upper()) or {}
    return [sv.upper() for sv in agent.get("semantic_views", [])]


def get_svs_for_agents(agent_names: list[str]) -> list[str]:
    svs: set[str] = set()
    for name in agent_names:
        svs.update(get_agent_semantic_views(name))
    return sorted(svs)


def get_all_configured_agents() -> list[str]:
    project = load_project_config()
    return list(project.get("agents", {}).keys())


def get_sv_eval_config(config: dict) -> dict:
    project = load_project_config()
    sv_eval = project.get("eval", {}).get("sv_eval", {})
    db = get_database(config)
    semantic_schema = config["deployment"].get("semantic_schema", "SEMANTIC")
    return {
        "stage": f"{db}.{semantic_schema}.{sv_eval.get('stage', 'sv_eval_stage')}",
        "file_format": f"{db}.{semantic_schema}.{sv_eval.get('file_format', 'yaml_file_format')}",
        "default_scope": sv_eval.get("default_scope", "all"),
    }


def get_sv_source(config: dict) -> str:
    source = config.get("semantic_views", {}).get("source")
    if source:
        return source.lower()
    project = load_project_config()
    return project.get("semantic_views", {}).get("source", "yaml").lower()
