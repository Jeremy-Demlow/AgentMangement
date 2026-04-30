"""Snowflake connection helper - now a thin wrapper around SnowflakeConfig.

Historical: this module used to silently allow role to be None and fall back
to the user's DEFAULT_ROLE. That caused repeated production bugs (MCP_OPERATOR
crash). The real implementation lives in agent_management.snowflake_config
which REQUIRES role/warehouse/database explicitly.

This file is kept for backward compatibility with callers that pass a dict
config. New code should use SnowflakeConfig.resolve() + connect() directly
from agent_management.snowflake_config.

Implements REQ-001: Environment Configuration System.
Implements REQ-020: Explicit Snowflake Connection Config.
"""
from __future__ import annotations

from typing import Any

import snowflake.connector

from agent_management.snowflake_config import SnowflakeConfig, connect as _connect_from_config


def connect(config: dict, **overrides: Any) -> snowflake.connector.SnowflakeConnection:
    """Legacy shim: accept dict-style config and route through SnowflakeConfig.

    Callers should migrate to:
        cfg = SnowflakeConfig.resolve(env=..., role=..., ...)
        conn = connect_from_config(cfg)
    """
    sf = config.get("snowflake", {}) or {}
    deploy = config.get("deployment", {}) or {}

    cfg = SnowflakeConfig.resolve(
        env=config.get("environment"),
        account=overrides.get("account", sf.get("account")),
        user=overrides.get("user", sf.get("user")),
        role=overrides.get("role", sf.get("role")),
        warehouse=overrides.get("warehouse", sf.get("warehouse")),
        database=overrides.get("database", deploy.get("database")),
        schema=overrides.get("schema", deploy.get("semantic_schema")),
        connection_name=overrides.get("connection_name"),
        private_key_path=overrides.get("private_key_path"),
        private_key_passphrase=overrides.get("private_key_passphrase"),
        password=overrides.get("password"),
        authenticator=overrides.get("authenticator", sf.get("authenticator")),
    )
    return _connect_from_config(cfg)
