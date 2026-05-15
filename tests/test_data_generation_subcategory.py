"""Regression test for CUSTOMER_FEEDBACK.SUBCATEGORY type drift.

The bootstrap generator (generate_complete_ski_data.py) previously emitted
'subcategory': None which made write_pandas(auto_create_table=True) infer the
column type as NUMBER(38,0). The daily incremental generator emits string
subcategories, which then failed to cast on append:

    snowflake.connector.errors.ProgrammingError: 100071 (22000): Failed to
    cast variant value "value" to FIXED

This test pins:
  1. The bootstrap module exposes FEEDBACK_SUBCATEGORIES with non-empty strings.
  2. The bootstrap seed dict path emits a string subcategory, never None or numeric.
"""
import importlib.util
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_PATH = REPO_ROOT / "data-generation" / "generate_complete_ski_data.py"
DAILY_PATH = REPO_ROOT / "data-generation" / "generate_daily_increment.py"


def _load_module(name: str, path: Path):
    """Load a script-style module without executing main() at import time."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    # Both files guard with `if __name__ == "__main__": main()`, so import-only
    # execution stops at module level (constants + function defs).
    spec.loader.exec_module(mod)
    return mod


def test_seed_module_exposes_subcategories():
    pytest.importorskip("pandas", reason="data-generation modules import pandas")
    pytest.importorskip("snowflake.snowpark", reason="data-generation modules import snowpark")
    seed = _load_module("seed_gen_complete", SEED_PATH)
    assert hasattr(seed, "FEEDBACK_SUBCATEGORIES"), (
        "FEEDBACK_SUBCATEGORIES list must exist so subcategory bootstraps as VARCHAR"
    )
    subs = seed.FEEDBACK_SUBCATEGORIES
    assert isinstance(subs, list) and len(subs) > 0
    for value in subs:
        assert isinstance(value, str) and value, (
            f"Every subcategory must be a non-empty string, got {value!r}"
        )


def test_daily_incremental_subcategories_are_strings():
    """Daily generator emits strings - guards against future regression.

    The daily generator now uses a category-aware subcategory map (so
    a 'lift_operations' row gets 'lift_lines' rather than a generic
    'speed'). This test pins string-typed subcategories without coupling
    to specific values.
    """
    daily_src = DAILY_PATH.read_text()
    assert "'SUBCATEGORY': subcategory" in daily_src, (
        "Daily generator must emit a SUBCATEGORY field"
    )
    assert "subcategories_by_category" in daily_src, (
        "Daily generator must use the category-aware subcategory map "
        "(replaces the prior flat string list)"
    )
    # Spot-check a few category-appropriate subcategories.
    for needle in ("'lift_lines'", "'food_quality'", "'instructor_quality'", "'snow_quality'"):
        assert needle in daily_src, (
            f"Expected category-aware subcategory token {needle} in daily source"
        )


def test_seed_subcategory_field_is_not_none():
    """Read the seed source and confirm the subcategory dict literal is a real value.

    We don't execute the heavy generator path; we grep the dict line to make
    sure no one re-introduces 'subcategory': None.
    """
    seed_src = SEED_PATH.read_text()
    assert "'subcategory': None" not in seed_src, (
        "Bootstrap must not emit 'subcategory': None - that drives write_pandas "
        "to infer NUMBER(38,0). Use FEEDBACK_SUBCATEGORIES instead."
    )
    assert "'subcategory': rng.choice(FEEDBACK_SUBCATEGORIES)" in seed_src, (
        "Bootstrap must emit a real string subcategory so the column is "
        "inferred as VARCHAR by write_pandas(auto_create_table=True)."
    )
