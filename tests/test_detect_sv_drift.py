"""Unit test for the detect_sv_drift paren-balancing parser.

This tests the regression where extract_block used a naive regex that closed
on the first inner `)` of a DIV0(...) expression, truncating the METRICS
block and reporting false drift on every multi-line metric.
"""
from __future__ import annotations

from pathlib import Path

from agent_management.detect_sv_drift import parse_dbt_sv


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
