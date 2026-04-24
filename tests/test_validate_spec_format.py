"""Unit tests for agent_management.validate_spec_format."""
from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from agent_management import validate_spec_format as vsf


@pytest.fixture
def sample_spec_content() -> str:
    # Minimal agent spec with one compliant tool description.
    return """metadata:
  name: widget
description: demo
tools:
  - name: AnalystTool
    type: cortex_analyst_text_to_sql
    semantic_view: DB.SCHEMA.SEM
    description: |
      PURPOSE: query revenue.
      DATA: revenue fact table.
      KEY METRICS: total_revenue.
      KEY DIMENSIONS: date, region.
      USE FOR: revenue questions.
      NOT FOR: weather questions.
      CROSS-REFERENCE WITH: SEM_DAILY_SUMMARY.
instructions:
  orchestration: Route revenue to AnalystTool.
  response: Answer concisely.
"""


def _call_with_rendered(content: str) -> list:
    """Patch render_file so we don't need a real env config."""
    with mock.patch.object(vsf, "render_file", return_value=content), \
         mock.patch.object(vsf, "load_env_config", return_value={}):
        return vsf.validate_spec_format("fake/path.yml")


def test_valid_spec_returns_no_errors(sample_spec_content):
    errs = _call_with_rendered(sample_spec_content)
    assert errs == []


def test_missing_section_is_reported(sample_spec_content):
    bad = sample_spec_content.replace("KEY METRICS", "KLEY METRICS")
    errs = _call_with_rendered(bad)
    rules = {e.rule for e in errs}
    assert "template_section_missing" in rules
    assert any("KEY METRICS" in e.message for e in errs)


def test_out_of_order_sections_reported():
    # All sections present but scrambled order.
    bad_tool_desc = (
        "DATA: x\nPURPOSE: y\nKEY METRICS: z\nKEY DIMENSIONS: a\n"
        "USE FOR: b\nNOT FOR: c\nCROSS-REFERENCE WITH: d\n"
    )
    content = (
        "metadata:\n  name: w\ndescription: d\n"
        "tools:\n  - name: T\n    type: cortex_analyst_text_to_sql\n"
        "    semantic_view: A.B.C\n    description: |\n"
        + "\n".join(f"      {line}" for line in bad_tool_desc.splitlines())
        + "\ninstructions:\n  orchestration: x\n  response: y\n"
    )
    errs = _call_with_rendered(content)
    rules = {e.rule for e in errs}
    assert "template_section_order" in rules


def test_hardcoded_season_reported(sample_spec_content):
    content = sample_spec_content.replace(
        "orchestration: Route revenue to AnalystTool.",
        "orchestration: For the 2024-2025 season, route revenue to AnalystTool.",
    )
    errs = _call_with_rendered(content)
    rules = {e.rule for e in errs}
    assert "no_hardcoded_seasons" in rules
