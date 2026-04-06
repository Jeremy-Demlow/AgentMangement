"""Quick smoke tests for config, rendering, and deploy_agents SQL generation."""
import json
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
from agent_management.deploy_agents import (
    build_spec, resolve_agent_identity, resolve_profile,
    build_alter_spec_sql, build_alter_metadata_sql,
    build_create_sql, build_force_create_sql,
)


EXPECTED_DBS = get_expected_databases()
EXPECTED_SCHEMAS = get_expected_schemas()


class TestConfigLoader:
    @pytest.mark.parametrize("env_name", ["dev", "qa", "prod"])
    def test_config_loads(self, env_name):
        c = load_env_config(env_name)
        assert get_database(c) == EXPECTED_DBS[env_name]
        sem = EXPECTED_SCHEMAS[env_name]["semantic"]
        agt = EXPECTED_SCHEMAS[env_name]["agents"]
        assert get_semantic_schema(c) == f"{EXPECTED_DBS[env_name]}.{sem}"
        assert get_agents_schema(c) == f"{EXPECTED_DBS[env_name]}.{agt}"

    @pytest.mark.parametrize("env_name,expected_suffix", [
        ("dev", "_DEV"),
        ("qa", "_QA"),
        ("prod", ""),
    ])
    def test_fqn_helpers(self, env_name, expected_suffix):
        c = load_env_config(env_name)
        db = EXPECTED_DBS[env_name]
        sem = EXPECTED_SCHEMAS[env_name]["semantic"]
        agt = EXPECTED_SCHEMAS[env_name]["agents"]
        assert get_agent_fqn(c, "resort_executive") == f"{db}.{agt}.RESORT_EXECUTIVE{expected_suffix}"
        assert get_sv_fqn(c, "sem_revenue") == f"{db}.{sem}.SEM_REVENUE"

    @pytest.mark.parametrize("env_name", ["dev", "qa", "prod"])
    def test_thresholds_present(self, env_name):
        c = load_env_config(env_name)
        t = get_thresholds(c)
        assert "answer_correctness" in t
        assert isinstance(t["answer_correctness"], float)

    def test_snowflake_env_override(self):
        os.environ["SNOWFLAKE_ENV"] = "qa"
        try:
            c = load_env_config()
            assert get_database(c) == EXPECTED_DBS["qa"]
        finally:
            del os.environ["SNOWFLAKE_ENV"]

    def test_missing_env_raises(self):
        with pytest.raises(FileNotFoundError):
            load_env_config("nonexistent")

    def test_deployment_mode(self):
        assert get_deployment_mode() == "single_account"

    def test_data_source_env(self):
        assert get_data_source_env() == "prod"


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

    @pytest.mark.parametrize("env_name", ["dev", "qa", "prod"])
    def test_sv_fqn_rendering(self, env_name):
        cfg = load_env_config(env_name)
        result = render_string("{{ env.semantic_schema }}.SEM_REVENUE", cfg)
        sem = EXPECTED_SCHEMAS[env_name]["semantic"]
        assert result == f"{EXPECTED_DBS[env_name]}.{sem}.SEM_REVENUE"

    @pytest.mark.parametrize("env_name", ["dev", "qa", "prod"])
    def test_agent_fqn_rendering(self, env_name):
        cfg = load_env_config(env_name)
        result = render_string("{{ env.agents_schema }}.RESORT_EXECUTIVE", cfg)
        agt = EXPECTED_SCHEMAS[env_name]["agents"]
        assert result == f"{EXPECTED_DBS[env_name]}.{agt}.RESORT_EXECUTIVE"

    def test_strict_undefined_raises(self):
        config = load_env_config("dev")
        with pytest.raises(jinja2.UndefinedError):
            render_string("{{ env.nonexistent_field }}", config)


class TestDeployAgentsSQLGen:
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
        agent_name, schema_fqn, fqn = resolve_agent_identity(mock_agent, prod_config)
        agt = EXPECTED_SCHEMAS["prod"]["agents"]
        assert fqn == f"{EXPECTED_DBS['prod']}.{agt}.TEST_AGENT"
        assert agent_name == "TEST_AGENT"

    def test_resolve_profile_dev_has_label(self, mock_agent, dev_config):
        profile = resolve_profile(mock_agent, dev_config)
        assert profile["display_name"] == "Test [DEV]"

    def test_resolve_profile_prod_no_label(self, mock_agent):
        prod_config = load_env_config("prod")
        profile = resolve_profile(mock_agent, prod_config)
        assert profile["display_name"] == "Test"

    def test_alter_spec_sql(self, mock_agent, dev_config):
        spec = build_spec(mock_agent, dev_config)
        _, _, fqn = resolve_agent_identity(mock_agent, dev_config)
        spec_json = json.dumps(spec, indent=2)
        sql = build_alter_spec_sql(fqn, spec_json)
        assert "ALTER AGENT" in sql
        assert "MODIFY LIVE VERSION SET SPECIFICATION" in sql
        assert "CREATE" not in sql

    def test_alter_metadata_sql(self, mock_agent, dev_config):
        _, _, fqn = resolve_agent_identity(mock_agent, dev_config)
        sql = build_alter_metadata_sql(fqn, mock_agent)
        assert sql is not None
        assert "ALTER AGENT" in sql
        assert "COMMENT" in sql
        assert "PROFILE" in sql

    def test_create_sql(self, mock_agent, dev_config):
        spec = build_spec(mock_agent, dev_config)
        _, _, fqn = resolve_agent_identity(mock_agent, dev_config)
        spec_json = json.dumps(spec, indent=2)
        sql = build_create_sql(fqn, mock_agent, spec_json)
        assert "CREATE AGENT IF NOT EXISTS" in sql
        assert "FROM SPECIFICATION" in sql

    def test_force_create_sql(self, mock_agent, dev_config):
        spec = build_spec(mock_agent, dev_config)
        _, _, fqn = resolve_agent_identity(mock_agent, dev_config)
        spec_json = json.dumps(spec, indent=2)
        sql = build_force_create_sql(fqn, mock_agent, spec_json)
        assert "CREATE OR REPLACE AGENT" in sql


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

    def test_eval_stage_uses_source_schema(self):
        ctx = build_context(load_env_config("dev"))
        assert ".AGENTS." in ctx["eval"]["stage"]
        assert ".AGENTS_DEV." not in ctx["eval"]["stage"]

    @pytest.mark.parametrize("env_name", ["dev", "qa", "prod"])
    def test_eval_context_uses_env_database(self, env_name):
        ctx = build_context(load_env_config(env_name))
        expected_db = get_expected_databases()[env_name]
        assert ctx["eval"]["source_database"] == expected_db
        assert ctx["eval"]["agents_schema"] == "AGENTS"

    def test_eval_run_date_override(self):
        ctx = build_context(load_env_config("dev"), run_date="20260101")
        assert ctx["eval"]["run_date"] == "20260101"

    def test_eval_template_rendering(self):
        tmpl = '{{ eval.source_database }}.{{ eval.agents_schema }}.RESORT_EXECUTIVE'
        result = render_string(tmpl, load_env_config("dev"))
        assert result == "AM_SKI_RESORT_DEV.AGENTS.RESORT_EXECUTIVE"

    def test_preserve_undefined_passthrough(self):
        from agent_management.render_eval_templates import _PreserveUndefined
        env = jinja2.Environment(undefined=_PreserveUndefined)
        result = env.from_string("{{ output }}").render()
        assert result == "{{ output }}"

    def test_preserve_undefined_with_eval_vars(self):
        from agent_management.render_eval_templates import _PreserveUndefined
        config = load_env_config("dev")
        ctx = build_context(config)
        env = jinja2.Environment(undefined=_PreserveUndefined)
        tmpl = '{{ eval.source_database }} and {{ ground_truth }}'
        result = env.from_string(tmpl).render(**ctx)
        assert "AM_SKI_RESORT_DEV" in result
        assert "{{ ground_truth }}" in result

    def test_find_eval_files(self):
        from agent_management.render_eval_templates import find_eval_files
        files = find_eval_files(None)
        assert len(files) >= 3
        names = [f.name for f in files]
        assert "resort_executive_eval.yaml" in names or any("resort_executive" in n for n in names)
