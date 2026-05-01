"""Tests for SnowflakeConfig.resolve() precedence and guardrails.

The core guarantee: role/warehouse/database are REQUIRED and come from
explicit kwargs > env vars > environments/<env>.env.yml. We never silently
fall back to the authenticating user's DEFAULT_ROLE.
"""
from __future__ import annotations

import os
import pytest
from unittest.mock import patch

from agent_management.snowflake_config import SnowflakeConfig, ConfigError


def _clean_env(keys):
    """Ensure no SNOWFLAKE_* env vars leak into tests."""
    return {k: None for k in keys}


SNOWFLAKE_ENV_VARS = [
    "SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_ROLE",
    "SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_DATABASE", "SNOWFLAKE_SCHEMA",
    "SNOWFLAKE_CONNECTION_NAME", "SNOWFLAKE_PRIVATE_KEY_PATH",
    "SNOWFLAKE_PRIVATE_KEY_PASSPHRASE", "SNOWFLAKE_PASSWORD",
    "SNOWFLAKE_AUTHENTICATOR", "SNOWFLAKE_ENV",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in SNOWFLAKE_ENV_VARS:
        monkeypatch.delenv(k, raising=False)


def test_resolve_kwargs_happy_path():
    cfg = SnowflakeConfig.resolve(
        account="acct", user="u", role="AM_DEPLOY_ROLE",
        warehouse="WH", database="DB",
    )
    assert cfg.role == "AM_DEPLOY_ROLE"
    assert cfg.warehouse == "WH"
    assert cfg.database == "DB"


def test_resolve_missing_role_raises():
    with pytest.raises(ConfigError) as exc:
        SnowflakeConfig.resolve(
            account="acct", user="u",
            warehouse="WH", database="DB",
        )
    assert "role" in str(exc.value).lower()
    assert "DEFAULT_ROLE" in str(exc.value)


def test_resolve_missing_warehouse_raises():
    with pytest.raises(ConfigError):
        SnowflakeConfig.resolve(
            account="acct", user="u", role="R", database="DB",
        )


def test_resolve_missing_database_raises():
    with pytest.raises(ConfigError):
        SnowflakeConfig.resolve(
            account="acct", user="u", role="R", warehouse="W",
        )


def test_env_vars_fill_gaps(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "env_acct")
    monkeypatch.setenv("SNOWFLAKE_USER", "env_user")
    monkeypatch.setenv("SNOWFLAKE_ROLE", "env_role")
    monkeypatch.setenv("SNOWFLAKE_WAREHOUSE", "env_wh")
    monkeypatch.setenv("SNOWFLAKE_DATABASE", "env_db")
    cfg = SnowflakeConfig.resolve()
    assert cfg.account == "env_acct"
    assert cfg.role == "env_role"


def test_explicit_kwargs_override_env_vars(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ROLE", "env_role")
    monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "env_acct")
    monkeypatch.setenv("SNOWFLAKE_USER", "env_user")
    monkeypatch.setenv("SNOWFLAKE_WAREHOUSE", "env_wh")
    monkeypatch.setenv("SNOWFLAKE_DATABASE", "env_db")
    cfg = SnowflakeConfig.resolve(role="explicit_role")
    assert cfg.role == "explicit_role"
    assert cfg.account == "env_acct"  # not overridden


def test_yaml_used_when_no_kwargs_or_env(monkeypatch, tmp_path):
    # Point env loader at a tmp yaml
    env_file = tmp_path / "test.env.yml"
    env_file.write_text("""
environment: test
snowflake:
  account: yaml_acct
  user: yaml_user
  role: yaml_role
  warehouse: yaml_wh
deployment:
  database: yaml_db
  semantic_schema: YAML_SCHEMA
  agents_schema: AGENTS
""")
    with patch("agent_management.snowflake_config.load_env_config") as mock_load:
        mock_load.return_value = {
            "snowflake": {"account": "yaml_acct", "user": "yaml_user", "role": "yaml_role", "warehouse": "yaml_wh"},
            "deployment": {"database": "yaml_db", "semantic_schema": "YAML_SCHEMA"},
        }
        cfg = SnowflakeConfig.resolve(env="test")
    assert cfg.role == "yaml_role"
    assert cfg.database == "yaml_db"


def test_kwargs_override_yaml(monkeypatch):
    with patch("agent_management.snowflake_config.load_env_config") as mock_load:
        mock_load.return_value = {
            "snowflake": {"account": "y", "user": "y", "role": "yaml_role", "warehouse": "y"},
            "deployment": {"database": "y", "semantic_schema": "s"},
        }
        cfg = SnowflakeConfig.resolve(env="test", role="explicit")
    assert cfg.role == "explicit"


def test_env_vars_override_yaml(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ROLE", "env_role")
    with patch("agent_management.snowflake_config.load_env_config") as mock_load:
        mock_load.return_value = {
            "snowflake": {"account": "y", "user": "y", "role": "yaml_role", "warehouse": "y"},
            "deployment": {"database": "y", "semantic_schema": "s"},
        }
        cfg = SnowflakeConfig.resolve(env="test")
    assert cfg.role == "env_role"


def test_to_connect_kwargs_always_includes_role():
    cfg = SnowflakeConfig.resolve(
        account="a", user="u", role="AM_DEPLOY_ROLE",
        warehouse="W", database="D",
    )
    kw = cfg.to_connect_kwargs()
    assert kw["role"] == "AM_DEPLOY_ROLE"
    assert kw["warehouse"] == "W"
    assert kw["database"] == "D"


def test_to_connect_kwargs_connection_name_wins():
    cfg = SnowflakeConfig.resolve(
        account="a", user="u", role="R", warehouse="W", database="D",
        connection_name="myconn", password="p",
    )
    kw = cfg.to_connect_kwargs()
    assert kw.get("connection_name") == "myconn"
    assert "password" not in kw


def test_to_connect_kwargs_password_auth():
    cfg = SnowflakeConfig.resolve(
        account="a", user="u", role="R", warehouse="W", database="D",
        password="test-only-not-real",  # pragma: allowlist secret
    )
    kw = cfg.to_connect_kwargs()
    assert kw.get("password") == "test-only-not-real"  # pragma: allowlist secret


def test_to_connect_kwargs_fallback_externalbrowser():
    cfg = SnowflakeConfig.resolve(
        account="a", user="u", role="R", warehouse="W", database="D",
    )
    kw = cfg.to_connect_kwargs()
    assert kw.get("authenticator") == "externalbrowser"


def test_immutable_frozen():
    cfg = SnowflakeConfig.resolve(
        account="a", user="u", role="R", warehouse="W", database="D",
    )
    with pytest.raises(Exception):
        cfg.role = "HACK"  # type: ignore
