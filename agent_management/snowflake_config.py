"""SnowflakeConfig: single source of truth for connection parameters.

Philosophy (fast.ai-style): sensible defaults that can be overridden, never
silently fall back to the authenticating user's DEFAULT_ROLE. Every caller
must resolve a SnowflakeConfig and pass it explicitly to connect().

Precedence (highest to lowest):
    1. Explicit kwargs passed to SnowflakeConfig.resolve()
    2. Environment variables (SNOWFLAKE_ROLE, SNOWFLAKE_WAREHOUSE, ...)
    3. environments/<env>.env.yml (snowflake.* and deployment.*)
    4. Hardcoded account defaults (never role - role MUST be set)

If `role` is missing after all precedence layers, raise ConfigError. The
authenticating user's DEFAULT_ROLE is NEVER used implicitly - that is the
single most expensive bug we've hit (silent fallback to MCP_OPERATOR).

Implements REQ-020: Explicit Snowflake Connection Config.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import snowflake.connector

from agent_management.utils.config import load_env_config


class ConfigError(ValueError):
    """Raised when required Snowflake connection fields are missing."""


@dataclass(frozen=True)
class SnowflakeConfig:
    """Typed, immutable Snowflake connection configuration.

    role, warehouse, database are REQUIRED. If any of these are absent after
    precedence resolution, resolve() raises ConfigError. NEVER relies on the
    authenticating user's DEFAULT_ROLE / DEFAULT_WAREHOUSE / DEFAULT_NAMESPACE.
    """

    account: str
    user: str
    role: str
    warehouse: str
    database: str
    schema: str | None = None
    private_key_path: str | None = None
    private_key_passphrase: str | None = None
    password: str | None = None
    authenticator: str | None = None
    connection_name: str | None = None
    env_label: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    REQUIRED_FIELDS = ("account", "user", "role", "warehouse", "database")

    def __post_init__(self):
        missing = [f for f in self.REQUIRED_FIELDS if not getattr(self, f)]
        if missing:
            raise ConfigError(
                "SnowflakeConfig missing required field(s): "
                f"{', '.join(missing)}. Never rely on DEFAULT_ROLE/WAREHOUSE - "
                "set them explicitly via kwargs, env vars, or environments/*.env.yml."
            )

    @classmethod
    def resolve(
        cls,
        env: str | None = None,
        *,
        account: str | None = None,
        user: str | None = None,
        role: str | None = None,
        warehouse: str | None = None,
        database: str | None = None,
        schema: str | None = None,
        connection_name: str | None = None,
        private_key_path: str | None = None,
        private_key_passphrase: str | None = None,
        password: str | None = None,
        authenticator: str | None = None,
    ) -> "SnowflakeConfig":
        """Resolve effective config with explicit kwargs > env vars > yaml > defaults.

        env: name of environments/<env>.env.yml to load (e.g. 'dev', 'prod').
             Optional - if not provided and SNOWFLAKE_ENV env var is also unset,
             only kwargs and env vars are considered.
        """
        yaml_cfg: dict = {}
        if env or os.environ.get("SNOWFLAKE_ENV"):
            try:
                yaml_cfg = load_env_config(env) or {}
            except FileNotFoundError:
                yaml_cfg = {}
        sf = yaml_cfg.get("snowflake", {}) or {}
        deploy = yaml_cfg.get("deployment", {}) or {}

        def pick(kw, env_var, yaml_path):
            if kw is not None and kw != "":
                return kw
            ev = os.environ.get(env_var)
            if ev:
                return ev
            # yaml_path is a tuple (dict, key)
            d, k = yaml_path
            return d.get(k)

        eff_account = pick(account, "SNOWFLAKE_ACCOUNT", (sf, "account"))
        eff_user = pick(user, "SNOWFLAKE_USER", (sf, "user"))
        eff_role = pick(role, "SNOWFLAKE_ROLE", (sf, "role"))
        eff_warehouse = pick(warehouse, "SNOWFLAKE_WAREHOUSE", (sf, "warehouse"))
        eff_database = pick(database, "SNOWFLAKE_DATABASE", (deploy, "database"))
        eff_schema = pick(schema, "SNOWFLAKE_SCHEMA", (deploy, "semantic_schema"))
        eff_conn_name = pick(connection_name, "SNOWFLAKE_CONNECTION_NAME", (sf, "connection_name"))
        eff_key_path = pick(private_key_path, "SNOWFLAKE_PRIVATE_KEY_PATH", (sf, "private_key_path"))
        eff_key_pass = pick(private_key_passphrase, "SNOWFLAKE_PRIVATE_KEY_PASSPHRASE", (sf, "private_key_passphrase"))
        eff_password = pick(password, "SNOWFLAKE_PASSWORD", (sf, "password"))
        eff_auth = pick(authenticator, "SNOWFLAKE_AUTHENTICATOR", (sf, "authenticator"))

        return cls(
            account=eff_account or "",
            user=eff_user or "",
            role=eff_role or "",
            warehouse=eff_warehouse or "",
            database=eff_database or "",
            schema=eff_schema,
            connection_name=eff_conn_name,
            private_key_path=eff_key_path,
            private_key_passphrase=eff_key_pass,
            password=eff_password,
            authenticator=eff_auth,
            env_label=env or os.environ.get("SNOWFLAKE_ENV"),
        )

    def to_connect_kwargs(self) -> dict:
        """Convert to snowflake.connector.connect(**kwargs) dict.

        Explicit role/warehouse/database are always set. Auth method picked
        by precedence: connection_name > private_key_path > password > authenticator.
        """
        kwargs: dict[str, Any] = {
            "account": self.account,
            "user": self.user,
            "role": self.role,
            "warehouse": self.warehouse,
            "database": self.database,
        }
        if self.schema:
            kwargs["schema"] = self.schema

        if self.connection_name:
            kwargs["connection_name"] = self.connection_name
            return kwargs

        if self.private_key_path:
            from cryptography.hazmat.primitives import serialization
            key_path = Path(self.private_key_path).expanduser()
            with open(key_path, "rb") as f:
                private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=(self.private_key_passphrase.encode()
                              if self.private_key_passphrase else None),
                )
            kwargs["private_key"] = private_key.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
            return kwargs

        if self.password:
            kwargs["password"] = self.password
            return kwargs

        if self.authenticator:
            kwargs["authenticator"] = self.authenticator
            return kwargs

        # If we got here, no auth method is set. Default to externalbrowser
        # (interactive dev use only — CI always has private_key_path or password).
        kwargs["authenticator"] = "externalbrowser"
        return kwargs


def connect(cfg: SnowflakeConfig) -> snowflake.connector.SnowflakeConnection:
    """Open a Snowflake connection using an explicit SnowflakeConfig.

    This is the ONLY place the snowflake.connector.connect() call should
    happen in the codebase. If you find yourself calling connect() directly
    with role omitted, stop and use SnowflakeConfig.resolve() instead.
    """
    return snowflake.connector.connect(**cfg.to_connect_kwargs())
