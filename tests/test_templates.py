"""Template rendering + spec format enforcement tests.

Uses agent_management.validate_spec_format as the source of truth for tool
description formatting rules; tests here are thin assertions on top.
"""
import pytest

from agent_management.render_template import render_file
from agent_management.utils.config import (
    load_env_config, get_expected_databases, get_expected_schemas,
    get_semantic_schema,
)
from agent_management.validate_spec_format import validate_spec_format

EXPECTED_DBS = get_expected_databases()
EXPECTED_SCHEMAS = get_expected_schemas()
ENVS = ("dev", "prod")

AGENT_SPECS = [
    "agents/specs/resort_executive.yml",
    "agents/specs/ski_ops_assistant.yml",
]

SV_DEFS = [
    "semantic-views/definitions/sem_customer_behavior.yaml",
    "semantic-views/definitions/sem_customer_satisfaction.yaml",
    "semantic-views/definitions/sem_daily_summary.yaml",
    "semantic-views/definitions/sem_lessons_analytics.yaml",
    "semantic-views/definitions/sem_marketing_analytics.yaml",
    "semantic-views/definitions/sem_operations.yaml",
    "semantic-views/definitions/sem_passholder_analytics.yaml",
    "semantic-views/definitions/sem_revenue.yaml",
    "semantic-views/definitions/sem_safety_incidents.yaml",
    "semantic-views/definitions/sem_staffing_analytics.yaml",
    "semantic-views/definitions/sem_weather_analytics.yaml",
]


class TestAgentSpecRendering:
    @pytest.mark.parametrize("env_name", ENVS)
    @pytest.mark.parametrize("spec_path", AGENT_SPECS)
    def test_agent_spec_renders(self, env_name, spec_path):
        config = load_env_config(env_name)
        rendered = render_file(spec_path, config)
        sem_fqn = get_semantic_schema(config)
        assert sem_fqn in rendered
        assert "{{ env." not in rendered


class TestSVDefinitionRendering:
    @pytest.mark.parametrize("env_name", ENVS)
    @pytest.mark.parametrize("sv_path", SV_DEFS)
    def test_sv_definition_renders(self, env_name, sv_path):
        config = load_env_config(env_name)
        rendered = render_file(sv_path, config)
        expected_db = EXPECTED_DBS[env_name]
        assert f"database: {expected_db}" in rendered
        assert "{{ env." not in rendered


class TestToolDescriptionFormat:
    """Thin wrapper around validate_spec_format."""

    @pytest.mark.parametrize("spec_path", AGENT_SPECS)
    def test_spec_passes_validator(self, spec_path):
        errors = validate_spec_format(spec_path, env="dev")
        assert errors == [], (
            f"{spec_path} failed validation:\n"
            + "\n".join(f"  {e}" for e in errors)
        )
