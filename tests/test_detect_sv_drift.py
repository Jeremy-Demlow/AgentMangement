"""Unit test for detect_sv_drift parser + dbt/yaml source detection.

Covers:
  1. Paren-balancing parser for multi-line metrics (regression test for the
     DIV0 truncation bug).
  2. YAML-only source mode (for repos that ship SV YAMLs without dbt).
  3. Auto-detection: prefer dbt if present, fall back to yaml.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from agent_management.detect_sv_drift import (
    _find_source,
    list_sv_models,
    parse_dbt_sv,
    parse_source_yaml,
)


SV_WITH_MULTILINE_METRICS = """
CREATE SEMANTIC VIEW {{ ref('sem_test') }}

TABLES (
    FACT_X AS {{ ref('fact_x') }}
)

DIMENSIONS (
    FACT_X.COL1 AS DIM1
)

FACTS (
    FACT_X.COL2 AS FACT1
)

METRICS (
    FACT_X.SIMPLE_METRIC AS SUM(FACT_X.AMOUNT)
      COMMENT = 'single line',
    FACT_X.MULTILINE_DIV AS DIV0(
        SUM(FACT_X.NUMERATOR),
        NULLIF(COUNT(FACT_X.DENOM), 0)
    )
      COMMENT = 'two-line DIV0 — used to break the parser',
    FACT_X.DEEP_NESTED AS DIV0(
        COUNT(CASE WHEN FACT_X.COND THEN 1 END),
        NULLIF(SUM(CASE WHEN FACT_X.COND THEN FACT_X.AMOUNT END), 0)
    ) * 100
      COMMENT = 'nested DIV0 with percent multiplier',
    FACT_X.LAST_METRIC AS COUNT(FACT_X.SALE_KEY)
      COMMENT = 'must appear after the multi-line blocks'
)

COMMENT = 'test';
"""


SV_YAML_SHAPE = """name: sem_test
description: "YAML-sourced SV"
tables:
  - name: FACT_X
    base_table:
      database: AM_TEST_DB
      schema: MARTS
      table: FACT_X
    primary_key:
      columns:
        - ID
    dimensions:
      - name: DIM1
        expr: COL1
        data_type: VARCHAR(50)
    facts:
      - name: FACT1
        expr: COL2
        data_type: NUMBER(10,0)
    metrics:
      - name: TOTAL_AMOUNT
        expr: SUM(AMOUNT)
      - name: AVG_AMOUNT
        expr: AVG(AMOUNT)
"""


def test_parser_captures_all_metrics_despite_inner_parens(tmp_path: Path):
    sql_file = tmp_path / "sem_test.sql"
    sql_file.write_text(SV_WITH_MULTILINE_METRICS)
    parsed = parse_dbt_sv(sql_file)
    assert parsed["metrics"] == {
        "SIMPLE_METRIC",
        "MULTILINE_DIV",
        "DEEP_NESTED",
        "LAST_METRIC",
    }
    assert parsed["tables"] == {"FACT_X"}
    assert parsed["dimensions"] == {"DIM1"}
    assert parsed["facts"] == {"FACT1"}


def test_yaml_source_parser(tmp_path: Path):
    yaml_file = tmp_path / "sem_test.yaml"
    yaml_file.write_text(SV_YAML_SHAPE)
    # parse_source_yaml Jinja-renders via render_file; patch to return raw content.
    with patch(
        "agent_management.detect_sv_drift.render_file",
        return_value=SV_YAML_SHAPE,
    ):
        parsed = parse_source_yaml(yaml_file, config={})
    assert parsed["tables"] == {"FACT_X"}
    assert parsed["dimensions"] == {"DIM1"}
    assert parsed["facts"] == {"FACT1"}
    assert parsed["metrics"] == {"TOTAL_AMOUNT", "AVG_AMOUNT"}


def test_find_source_prefers_dbt(tmp_path: Path, monkeypatch):
    # Create both a dbt model and a yaml definition with the same SV name.
    dbt_dir = tmp_path / "dbt" / "models" / "marts" / "semantic"
    yaml_dir = tmp_path / "semantic-views" / "definitions"
    dbt_dir.mkdir(parents=True)
    yaml_dir.mkdir(parents=True)
    (dbt_dir / "sem_both.sql").write_text("-- dbt")
    (yaml_dir / "sem_both.yaml").write_text("name: sem_both")

    monkeypatch.setattr("agent_management.detect_sv_drift.SV_MODEL_DIR", dbt_dir)
    monkeypatch.setattr(
        "agent_management.detect_sv_drift.sv_definitions_dir",
        lambda: yaml_dir,
    )

    kind, path = _find_source("sem_both", source="auto")
    assert kind == "dbt"
    assert path.name == "sem_both.sql"


def test_find_source_falls_back_to_yaml_when_no_dbt(tmp_path: Path, monkeypatch):
    # YAML only: repo ships SV definitions without a dbt project.
    dbt_dir = tmp_path / "nonexistent_dbt"
    yaml_dir = tmp_path / "semantic-views" / "definitions"
    yaml_dir.mkdir(parents=True)
    (yaml_dir / "sem_only_yaml.yaml").write_text("name: sem_only_yaml")

    monkeypatch.setattr("agent_management.detect_sv_drift.SV_MODEL_DIR", dbt_dir)
    monkeypatch.setattr(
        "agent_management.detect_sv_drift.sv_definitions_dir",
        lambda: yaml_dir,
    )

    kind, path = _find_source("sem_only_yaml", source="auto")
    assert kind == "yaml"
    assert path.name == "sem_only_yaml.yaml"


def test_find_source_neither_returns_none(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "agent_management.detect_sv_drift.SV_MODEL_DIR",
        tmp_path / "no_dbt",
    )
    monkeypatch.setattr(
        "agent_management.detect_sv_drift.sv_definitions_dir",
        lambda: tmp_path / "no_yaml",
    )
    kind, path = _find_source("sem_missing", source="auto")
    assert kind is None
    assert path is None


def test_list_sv_models_yaml_only(tmp_path: Path, monkeypatch):
    dbt_dir = tmp_path / "no_dbt"
    yaml_dir = tmp_path / "yaml"
    yaml_dir.mkdir()
    (yaml_dir / "sem_a.yaml").write_text("")
    (yaml_dir / "sem_b.yml").write_text("")
    (yaml_dir / "not_an_sv.yaml").write_text("")

    monkeypatch.setattr("agent_management.detect_sv_drift.SV_MODEL_DIR", dbt_dir)
    monkeypatch.setattr(
        "agent_management.detect_sv_drift.sv_definitions_dir",
        lambda: yaml_dir,
    )
    assert list_sv_models(source="yaml") == ["sem_a", "sem_b"]
    assert list_sv_models(source="auto") == ["sem_a", "sem_b"]
    assert list_sv_models(source="dbt") == []
