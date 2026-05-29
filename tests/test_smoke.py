"""Quick smoke tests for config, rendering, and deploy_agents helper logic.

Updated for the versioning-only world:
- QA env no longer exists; matrix is [dev, prod].
- deploy_agents no longer exports build_alter_spec_sql / build_create_sql.
  The exercised surface is the helper functions that remain: build_spec,
  resolve_agent_identity, resolve_profile.
"""
import os

import jinja2
import pytest

from agent_management.utils.config import (
    load_env_config, get_database, get_semantic_schema,
    get_agents_schema, get_agent_fqn, get_sv_fqn, get_thresholds,
    get_expected_databases, get_expected_schemas,
    get_eval_config, get_deployment_mode, get_data_source_env,
)
from agent_management.render_template import render_string, build_context
from agent_management.agents.deploy import (
    build_spec, resolve_agent_identity, resolve_profile,
)


EXPECTED_DBS = get_expected_databases()
EXPECTED_SCHEMAS = get_expected_schemas()
ENVS = ("dev", "prod")


class TestConfigLoader:
    @pytest.mark.parametrize("env_name", ENVS)
    def test_config_loads(self, env_name):
        c = load_env_config(env_name)
        assert get_database(c) == EXPECTED_DBS[env_name]
        sem = EXPECTED_SCHEMAS[env_name]["semantic"]
        agt = EXPECTED_SCHEMAS[env_name]["agents"]
        assert get_semantic_schema(c) == f"{EXPECTED_DBS[env_name]}.{sem}"
        assert get_agents_schema(c) == f"{EXPECTED_DBS[env_name]}.{agt}"

    @pytest.mark.parametrize("env_name,expected_suffix", [
        ("dev", "_DEV"),
        ("prod", ""),
    ])
    def test_fqn_helpers(self, env_name, expected_suffix):
        c = load_env_config(env_name)
        db = EXPECTED_DBS[env_name]
        sem = EXPECTED_SCHEMAS[env_name]["semantic"]
        agt = EXPECTED_SCHEMAS[env_name]["agents"]
        assert get_agent_fqn(c, "resort_executive") == f"{db}.{agt}.RESORT_EXECUTIVE{expected_suffix}"
        assert get_sv_fqn(c, "sem_revenue") == f"{db}.{sem}.SEM_REVENUE"

    @pytest.mark.parametrize("env_name", ENVS)
    def test_thresholds_present(self, env_name):
        c = load_env_config(env_name)
        t = get_thresholds(c)
        assert "answer_correctness" in t
        assert isinstance(t["answer_correctness"], float)

    def test_snowflake_env_override(self):
        os.environ["SNOWFLAKE_ENV"] = "prod"
        try:
            c = load_env_config()
            assert get_database(c) == EXPECTED_DBS["prod"]
        finally:
            del os.environ["SNOWFLAKE_ENV"]

    def test_missing_env_raises(self):
        with pytest.raises(FileNotFoundError):
            load_env_config("nonexistent")

    def test_deployment_mode(self):
        assert get_deployment_mode() == "single_account"

    def test_data_source_env(self):
        assert get_data_source_env() == "prod"


class TestEnvAliases:
    """Option B: dev has deploy_alias=latest; prod has [validated, production]."""

    def test_dev_has_latest_alias(self):
        c = load_env_config("dev")
        assert c["agent"]["deploy_alias"] == "latest"
        assert "latest" in c["agent"]["aliases"]

    def test_prod_has_validated_and_production(self):
        c = load_env_config("prod")
        assert c["agent"]["deploy_alias"] == "validated"
        assert set(c["agent"]["aliases"]) >= {"validated", "production"}


class TestRenderTemplate:
    def test_build_context_dev(self):
        config = load_env_config("dev")
        ctx = build_context(config)
        expected_db = EXPECTED_DBS["dev"]
        sem = EXPECTED_SCHEMAS["dev"]["semantic"]
        agt = EXPECTED_SCHEMAS["dev"]["agents"]
        assert ctx["env"]["database"] == expected_db
        assert ctx["env"]["semantic_schema"] == f"{expected_db}.{sem}"
        assert ctx["env"]["agents_schema"] == f"{expected_db}.{agt}"

    @pytest.mark.parametrize("env_name", ENVS)
    def test_sv_fqn_rendering(self, env_name):
        cfg = load_env_config(env_name)
        result = render_string("{{ env.semantic_schema }}.SEM_REVENUE", cfg)
        sem = EXPECTED_SCHEMAS[env_name]["semantic"]
        assert result == f"{EXPECTED_DBS[env_name]}.{sem}.SEM_REVENUE"

    @pytest.mark.parametrize("env_name", ENVS)
    def test_agent_fqn_rendering(self, env_name):
        cfg = load_env_config(env_name)
        result = render_string("{{ env.agents_schema }}.RESORT_EXECUTIVE", cfg)
        agt = EXPECTED_SCHEMAS[env_name]["agents"]
        assert result == f"{EXPECTED_DBS[env_name]}.{agt}.RESORT_EXECUTIVE"

    def test_strict_undefined_raises(self):
        config = load_env_config("dev")
        with pytest.raises(jinja2.UndefinedError):
            render_string("{{ env.nonexistent_field }}", config)


class TestDeployAgentsHelpers:
    @pytest.fixture
    def mock_agent(self):
        sem = EXPECTED_SCHEMAS["dev"]["semantic"]
        return {
            "metadata": {"name": "test_agent"},
            "description": "Test agent for smoke test",
            "profile": {"display_name": "Test", "color": "blue"},
            "tools": [
                {
                    "name": "AnalystTool",
                    "type": "cortex_analyst_text_to_sql",
                    "semantic_view": f"{EXPECTED_DBS['dev']}.{sem}.SEM_REVENUE",
                    "description": "Revenue analysis",
                }
            ],
            "instructions": {
                "orchestration": "Route revenue questions to AnalystTool",
                "response": "Be concise",
            },
            "sample_questions": ["What was total revenue?"],
        }

    @pytest.fixture
    def dev_config(self):
        return load_env_config("dev")

    def test_build_spec(self, mock_agent, dev_config):
        spec = build_spec(mock_agent, dev_config)
        assert spec["models"]["orchestration"] is not None
        assert len(spec["tools"]) == 1
        assert spec["tools"][0]["tool_spec"]["name"] == "AnalystTool"

    def test_resolve_agent_identity(self, mock_agent, dev_config):
        agent_name, schema_fqn, fqn = resolve_agent_identity(mock_agent, dev_config)
        agt = EXPECTED_SCHEMAS["dev"]["agents"]
        assert fqn == f"{EXPECTED_DBS['dev']}.{agt}.TEST_AGENT_DEV"
        assert agent_name == "TEST_AGENT_DEV"

    def test_resolve_agent_identity_prod_no_suffix(self, mock_agent):
        prod_config = load_env_config("prod")
        _, _, fqn = resolve_agent_identity(mock_agent, prod_config)
        agt = EXPECTED_SCHEMAS["prod"]["agents"]
        assert fqn == f"{EXPECTED_DBS['prod']}.{agt}.TEST_AGENT"

    def test_resolve_profile_dev_has_label(self, mock_agent, dev_config):
        profile = resolve_profile(mock_agent, dev_config)
        assert profile["display_name"] == "Test [DEV]"

    def test_resolve_profile_prod_no_label(self, mock_agent):
        prod_config = load_env_config("prod")
        profile = resolve_profile(mock_agent, prod_config)
        assert profile["display_name"] == "Test"


class TestEvalRendering:
    def test_build_context_includes_eval_namespace(self):
        config = load_env_config("dev")
        ctx = build_context(config)
        assert "eval" in ctx
        assert "source_database" in ctx["eval"]
        assert "agents_schema" in ctx["eval"]
        assert "run_date" in ctx["eval"]

    def test_eval_source_database(self):
        ctx = build_context(load_env_config("dev"))
        assert ctx["eval"]["source_database"] == "AM_SKI_RESORT_DEV"

    def test_eval_agents_schema_is_source_not_deployment(self):
        ctx = build_context(load_env_config("dev"))
        assert ctx["eval"]["agents_schema"] == "AGENTS"
        assert ctx["eval"]["agents_schema"] != "AGENTS_DEV"

    @pytest.mark.parametrize("env_name", ENVS)
    def test_eval_context_uses_env_database(self, env_name):
        ctx = build_context(load_env_config(env_name))
        expected_db = get_expected_databases()[env_name]
        assert ctx["eval"]["source_database"] == expected_db
        assert ctx["eval"]["agents_schema"] == "AGENTS"
