"""Jinja2 template renderer for agent specs, SV YAML, and eval configs.

Renders {{ env.* }} and {{ eval.* }} placeholders in YAML templates
using environment config and project-level eval settings.

Implements REQ-001: Environment Configuration System.
Implements REQ-011: Eval Template Rendering.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import jinja2

from agent_management.utils.config import (
    get_agents_schema,
    get_budget,
    get_database,
    get_eval_config,
    get_model,
    get_semantic_schema,
)


def build_context(config: dict, run_date: str | None = None) -> dict[str, Any]:
    from datetime import date as _date

    eval_cfg = get_eval_config(config)
    return {
        "env": {
            "environment": config["environment"],
            "database": get_database(config),
            "semantic_schema": get_semantic_schema(config),
            "agents_schema": get_agents_schema(config),
            "warehouse": config["snowflake"]["warehouse"],
            "role": config["snowflake"]["role"],
            "model": get_model(config),
            "budget_seconds": get_budget(config).get("seconds", 300),
            "budget_tokens": get_budget(config).get("tokens", 50000),
            "name_suffix": config.get("agent", {}).get("name_suffix", ""),
            "stage": config["deployment"].get("stage", "EVAL_CONFIG_STAGE"),
        },
        "eval": {
            "source_database": eval_cfg["source_database"],
            "agents_schema": eval_cfg["source_agents_schema"].split(".")[-1],
            "marts_schema": eval_cfg["source_marts_schema"].split(".")[-1],
            "stage": eval_cfg["stage"],
            "file_format": eval_cfg["file_format"],
            "warehouse": eval_cfg["warehouse"],
            "run_date": run_date or _date.today().strftime("%Y%m%d"),
        },
    }


def render_string(template_str: str, config: dict) -> str:
    env = jinja2.Environment(undefined=jinja2.StrictUndefined)
    tmpl = env.from_string(template_str)
    ctx = build_context(config)
    return tmpl.render(**ctx)


def render_file(template_path: str | Path, config: dict) -> str:
    path = Path(template_path)
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {path}")
    return render_string(path.read_text(), config)
