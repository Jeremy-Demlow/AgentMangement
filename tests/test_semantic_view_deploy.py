"""Semantic View deploy command behavior."""
from __future__ import annotations

from unittest.mock import patch

from agent_management.semantic_views.deploy import run_dbt_path


def test_dbt_dry_run_does_not_require_snowflake_connection():
    config = {"environment": "dev", "deployment": {"semantic_schema": "SEMANTIC"}}

    with patch("agent_management.semantic_views.deploy.connect") as connect:
        result = run_dbt_path(config, "DB.SEMANTIC", dry_run=True)

    assert result == 0
    connect.assert_not_called()
