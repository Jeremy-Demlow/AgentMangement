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


class TestToolDescriptionFormat:
    """Enforce the framework's tool description format.

    See framework/TOOL_DESCRIPTION_TEMPLATE.md for the full contract. Every
    tool description in agents/specs/*.yml must contain these section
    headers so the agent has a consistent mental model of every tool.
    """

    REQUIRED_SECTIONS = [
        "PURPOSE:",
        "DATA:",
        "KEY METRICS",
        "KEY DIMENSIONS",
        "USE FOR:",
        "NOT FOR:",
        "CROSS-REFERENCE WITH:",
    ]

    @pytest.mark.parametrize("spec_path", AGENT_SPECS)
    def test_every_tool_description_has_required_sections(self, spec_path):
        import yaml as pyyaml
        config = load_env_config("dev")
        rendered = render_file(spec_path, config)
        spec = pyyaml.safe_load(rendered)
        tools = spec.get("tools", [])
        assert tools, f"{spec_path} has no tools"

        missing = []
        for tool in tools:
            name = tool.get("name", "<unnamed>")
            desc = tool.get("description", "") or ""
            for section in self.REQUIRED_SECTIONS:
                if section not in desc:
                    missing.append((name, section))

        assert not missing, (
            f"{spec_path} tool descriptions missing required sections "
            f"(see framework/TOOL_DESCRIPTION_TEMPLATE.md):\n"
            + "\n".join(f"  - {name}: missing '{section}'" for name, section in missing)
        )

    @pytest.mark.parametrize("spec_path", AGENT_SPECS)
    def test_no_hardcoded_ski_seasons_in_spec(self, spec_path):
        """Spec must resolve seasons dynamically, not hardcode '2024-2025' etc."""
        import re
        config = load_env_config("dev")
        rendered = render_file(spec_path, config)
        # hardcoded season strings look like 2024-2025 or 2024-25
        hardcoded = re.findall(r"\b20\d{2}-20?\d{2}\b", rendered)
        # Allow in sample_questions and tool examples, but not in instructions
        # Pull the instructions block and check only that
        import yaml as pyyaml
        spec = pyyaml.safe_load(rendered)
        instructions = spec.get("instructions", {}) or {}
        orchestration = instructions.get("orchestration", "") or ""
        response = instructions.get("response", "") or ""
        combined = orchestration + "\n" + response
        hardcoded_in_instructions = re.findall(r"\b20\d{2}-20?\d{2}\b", combined)
        assert not hardcoded_in_instructions, (
            f"{spec_path} instructions contain hardcoded season strings "
            f"{hardcoded_in_instructions}. Resolve seasons dynamically via DIM_DATE "
            f"(see framework/AGENT_BEST_PRACTICES.md)."
        )
