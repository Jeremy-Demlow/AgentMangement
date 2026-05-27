"""Tests for package-style explicit config path loading.

The library should work after `pip install` without relying on running from the
reference repo root. These tests exercise explicit config file paths and env-var
based config paths.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_management import paths
from agent_management.utils.config import get_database, load_env_config, load_project_config


PROJECT_YAML = """
project:
  name: path-test

environments:
  dev:
    database: TMP_DEV
    role: TMP_ROLE_DEV
    warehouse: TMP_WH_DEV
    semantic_schema: SEMANTIC
    agents_schema: AGENTS
    name_suffix: _DEV
"""

ENV_YAML = """
environment: dev
snowflake:
  role: TMP_ROLE_DEV
  warehouse: TMP_WH_DEV
deployment:
  database: TMP_DEV
  semantic_schema: SEMANTIC
  agents_schema: AGENTS
agent:
  name_suffix: _DEV
  deploy_alias: latest
  aliases: [latest]
"""


def test_load_project_config_from_explicit_path(tmp_path: Path):
    project_file = tmp_path / "custom_project.yml"
    project_file.write_text(PROJECT_YAML)

    cfg = load_project_config(project_file)

    assert cfg["project"]["name"] == "path-test"
    assert cfg["environments"]["dev"]["database"] == "TMP_DEV"


def test_load_env_config_from_explicit_path(tmp_path: Path):
    env_file = tmp_path / "custom_dev.env.yml"
    env_file.write_text(ENV_YAML)

    cfg = load_env_config(path=env_file)

    assert cfg["environment"] == "dev"
    assert get_database(cfg) == "TMP_DEV"


def test_load_env_config_from_env_var(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    env_file = tmp_path / "custom_dev.env.yml"
    env_file.write_text(ENV_YAML)
    monkeypatch.setenv("AGENT_MGMT_ENV_CONFIG", str(env_file))

    cfg = load_env_config()

    assert get_database(cfg) == "TMP_DEV"


def test_project_root_can_be_inferred_from_project_config_env_var(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    project_file = tmp_path / "custom_project.yml"
    project_file.write_text(PROJECT_YAML)
    monkeypatch.setenv("AGENT_MGMT_PROJECT_CONFIG", str(project_file))
    paths.project_root.cache_clear()

    try:
        assert paths.project_root() == tmp_path
        assert paths.project_config_path() == project_file
    finally:
        paths.project_root.cache_clear()
