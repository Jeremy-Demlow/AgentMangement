"""Load project configuration for data generation scripts.

Reads database, warehouse, and schema names from the project-level
project.yml so data generation scripts don't hardcode Snowflake object names.

Supports environment-aware database resolution via get_database_for_env().
The module-level DATABASE constant defaults to prod for backward compatibility.
"""
from __future__ import annotations

from pathlib import Path

import yaml

_PROJECT_PATH = Path(__file__).resolve().parent.parent / "project.yml"


def _load() -> dict:
    if not _PROJECT_PATH.exists():
        return {}
    with open(_PROJECT_PATH) as f:
        return yaml.safe_load(f) or {}


_CFG = _load()
_DEFAULTS = _CFG.get("defaults", {})
_SF = _DEFAULTS.get("snowflake", {})
_SCHEMAS = _DEFAULTS.get("schemas", {})
_ENVS = _CFG.get("environments", {})

DATABASE = _ENVS.get("prod", {}).get("database", "SKI_RESORT_DB")
WAREHOUSE = _SF.get("warehouse", "COMPUTE_WH")
RAW_SCHEMA = _SCHEMAS.get("raw", "RAW")
STAGING_SCHEMA = _SCHEMAS.get("staging", "STAGING")
MARTS_SCHEMA = _SCHEMAS.get("marts", "MARTS")
DOCS_SCHEMA = "DOCS"

VALID_ENVS = list(_ENVS.keys())


def get_database_for_env(env: str) -> str:
    if env not in _ENVS:
        raise ValueError(f"Unknown environment '{env}'. Valid: {VALID_ENVS}")
    return _ENVS[env].get("database", DATABASE)


def get_warehouse_for_env(env: str) -> str:
    return _ENVS.get(env, {}).get("warehouse", WAREHOUSE)


def get_role_for_env(env: str) -> str:
    return _ENVS.get(env, {}).get("role", "ACCOUNTADMIN")
