"""Test template rendering for agent specs and SV YAML across all environments."""
import os

import pytest

from agent_management.render_template import render_file
from agent_management.utils.config import (
    load_env_config, get_expected_databases, get_expected_schemas,
    get_semantic_schema,
)

EXPECTED_DBS = get_expected_databases()
EXPECTED_SCHEMAS = get_expected_schemas()

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
    @pytest.mark.parametrize("env_name", ["dev", "qa", "prod"])
    @pytest.mark.parametrize("spec_path", AGENT_SPECS)
    def test_agent_spec_renders(self, env_name, spec_path):
        config = load_env_config(env_name)
        rendered = render_file(spec_path, config)
        sem_fqn = get_semantic_schema(config)
        assert sem_fqn in rendered
        assert "{{ env." not in rendered


class TestSVDefinitionRendering:
    @pytest.mark.parametrize("env_name", ["dev", "qa", "prod"])
    @pytest.mark.parametrize("sv_path", SV_DEFS)
    def test_sv_definition_renders(self, env_name, sv_path):
        config = load_env_config(env_name)
        rendered = render_file(sv_path, config)
        expected_db = EXPECTED_DBS[env_name]
        assert f"database: {expected_db}" in rendered
        assert "{{ env." not in rendered
