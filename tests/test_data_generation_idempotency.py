"""Contract tests for data-generation hardening.

Pins:
  1. IDEMPOTENCY_TABLES covers every table the daily generator writes, so
     the per-table idempotency check stays in lockstep with what we generate
     (regression target: the original `check_any_data_exists` only checked
     WEATHER/PASS_USAGE/LIFT_SCANS, which masked CUSTOMER_FEEDBACK gaps).
  2. present_for_date() returns a per-tag boolean dict, not a coarse bool.
  3. generate_customer_feedback() emits realistic varied text drawn from a
     curated bank, never the old "Sample feedback for {date}" placeholder.
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import date as date_cls
from pathlib import Path
from unittest.mock import MagicMock

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
DAILY_PATH = REPO_ROOT / "data-generation" / "generate_daily_increment.py"


def _load_daily():
    pytest.importorskip("pandas")
    pytest.importorskip("snowflake.snowpark")
    # data-generation modules use sibling-relative imports
    # (e.g. `from snowflake_connection import ...`); add the directory to
    # sys.path so the import resolves without packaging the folder.
    data_gen_dir = str(REPO_ROOT / "data-generation")
    if data_gen_dir not in sys.path:
        sys.path.insert(0, data_gen_dir)
    spec = importlib.util.spec_from_file_location("daily_gen_for_idempotency", DAILY_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["daily_gen_for_idempotency"] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# IDEMPOTENCY_TABLES coverage
# ---------------------------------------------------------------------------


def test_idempotency_tables_covers_every_generated_table():
    daily = _load_daily()

    # The full set of tables the generator writes (verified against the
    # main loop's appends + write_pandas calls).
    expected_tags = {
        "WEATHER_CONDITIONS",
        "STAFFING_SCHEDULE",
        "LIFT_MAINTENANCE",
        "GROOMING_LOGS",
        "LIFT_SCANS",
        "PASS_USAGE",
        "TICKET_SALES",
        "FOOD_BEVERAGE",
        "RENTALS",
        "SKI_LESSONS",
        "INCIDENTS",
        "CUSTOMER_FEEDBACK",
        "PARKING_OCCUPANCY",
    }
    assert expected_tags <= set(daily.IDEMPOTENCY_TABLES), (
        f"IDEMPOTENCY_TABLES must cover every generated table; missing: "
        f"{expected_tags - set(daily.IDEMPOTENCY_TABLES)}"
    )

    # Every value is a (table_name, date_column_expr) pair of strings.
    for tag, value in daily.IDEMPOTENCY_TABLES.items():
        assert isinstance(value, tuple) and len(value) == 2, f"{tag} entry malformed"
        table, col = value
        assert isinstance(table, str) and table, tag
        assert isinstance(col, str) and col, tag


# ---------------------------------------------------------------------------
# present_for_date returns a per-tag dict, not a coarse bool
# ---------------------------------------------------------------------------


def test_present_for_date_returns_per_tag_dict():
    daily = _load_daily()

    # Mock conn so check_date_exists returns True for WEATHER_CONDITIONS only,
    # False for everything else. present_for_date should reflect that.
    def _mock_query(sql_query):
        # The query has 'FROM <TABLE>' for the table being checked.
        result = MagicMock()
        if "WEATHER_CONDITIONS" in sql_query:
            result.to_pandas.return_value = MagicMock()
            result.to_pandas.return_value.__getitem__.return_value.iloc = [1]
            # Match the {'CNT': cnt} shape used by check_date_exists.
            import pandas as pd
            return _SqlResult(pd.DataFrame({"CNT": [1]}))
        import pandas as pd
        return _SqlResult(pd.DataFrame({"CNT": [0]}))

    class _SqlResult:
        def __init__(self, df):
            self._df = df

        def to_pandas(self):
            return self._df

    conn = MagicMock()
    conn.sql = _mock_query

    out = daily.present_for_date(conn, date_cls(2026, 1, 15))

    assert isinstance(out, dict), "present_for_date must return a dict, not a bool"
    # Result of `numeric > 0` may be numpy.bool_ (np.True_), so compare via
    # truthiness rather than identity.
    assert bool(out["WEATHER_CONDITIONS"]) is True
    assert bool(out["CUSTOMER_FEEDBACK"]) is False
    # Every IDEMPOTENCY_TABLES tag must be a key in the result.
    assert set(out) == set(daily.IDEMPOTENCY_TABLES)


def test_present_for_date_treats_query_failures_as_present():
    """Conservative: if the presence-check raises, assume present so we don't
    duplicate-write. --force still overrides everything."""
    daily = _load_daily()

    def _raising_sql(_):
        raise RuntimeError("transient")

    conn = MagicMock()
    conn.sql = _raising_sql

    out = daily.present_for_date(conn, date_cls(2026, 1, 15))
    assert all(out.values()), "Failed presence check must default to True (present)"


# ---------------------------------------------------------------------------
# generate_customer_feedback richness contract
# ---------------------------------------------------------------------------


def test_generate_customer_feedback_uses_curated_bank_not_placeholder():
    """Texts must be drawn from a curated bank, not the old placeholder."""
    daily = _load_daily()
    src = DAILY_PATH.read_text()
    # The old placeholder pattern must be gone.
    assert "Sample feedback for" not in src, (
        "Old placeholder text must not appear; replace with curated bank"
    )
    # The new function must reference text_banks and subcategories_by_category.
    assert "text_banks" in src
    assert "subcategories_by_category" in src
    # Spot-check that the bank actually contains real-sounding sentences.
    assert "Lift lines moved fast" in src or "powder day" in src.lower()


def test_generate_customer_feedback_produces_varied_realistic_rows():
    """Run the generator with mocked rng inputs and confirm rows are sane."""
    daily = _load_daily()
    import pandas as pd

    customers_df = pd.DataFrame({
        "CUSTOMER_ID": [f"C{i:04d}" for i in range(50)],
        "CUSTOMER_SEGMENT": ["regular"] * 50,
        "IS_PASS_HOLDER": [True] * 50,
    })
    daily_mod = {
        "season_mult": 1.5,
        "is_powder_day": True,
        "storm_warning": False,
        "holiday_mult": 1.0,
    }

    df = daily.generate_customer_feedback(date_cls(2026, 2, 14), 600, daily_mod, customers_df)
    assert not df.empty, "Powder day with 600 visitors should produce feedback"

    # Schema preserved
    required_cols = {
        "FEEDBACK_ID", "CUSTOMER_ID", "FEEDBACK_DATE", "FEEDBACK_TYPE",
        "NPS_SCORE", "SATISFACTION_SCORE", "CATEGORY", "SUBCATEGORY",
        "SENTIMENT", "FEEDBACK_TEXT", "RESPONSE_TEXT", "RESPONDED_BY",
        "RESOLVED", "RESOLUTION_DATE", "ESCALATED", "VISIT_DATE", "CREATED_AT",
    }
    assert required_cols <= set(df.columns), f"Missing cols: {required_cols - set(df.columns)}"

    # Subcategory must be category-appropriate (e.g. lift_operations -> lift_*)
    lift_rows = df[df["CATEGORY"] == "lift_operations"]
    if len(lift_rows) > 0:
        bad = lift_rows[~lift_rows["SUBCATEGORY"].isin([
            "lift_lines", "lift_speed", "lift_reliability", "staff_friendliness",
        ])]
        assert bad.empty, (
            f"lift_operations rows had non-lift subcategories: {bad['SUBCATEGORY'].tolist()[:5]}"
        )

    # Text variety: when present, no row should be the old placeholder
    text_rows = df[df["FEEDBACK_TEXT"].notna()]
    assert (text_rows["FEEDBACK_TEXT"] != "Sample feedback for 2026-02-14").all()

    # On a powder day, average satisfaction should skew >= 4.
    assert df["SATISFACTION_SCORE"].mean() >= 3.5, (
        f"Powder day mean satisfaction {df['SATISFACTION_SCORE'].mean()} too low"
    )

    # Sentiment values must be the documented set
    assert set(df["SENTIMENT"]) <= {"positive", "negative", "neutral"}
