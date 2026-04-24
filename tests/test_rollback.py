"""Unit tests for agent_management.rollback (alias reassignment only)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from agent_management import rollback as rb


class FakeConn:
    def cursor(self):
        raise RuntimeError("patched; cursor unused")


def _write_snapshot(path: Path, alias_before: dict, version_before: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "agent_fqn": "DB.SCH.AGENT",
        "env": "prod",
        "snapshot_time": "2026-04-24T00:00:00Z",
        "version_before": version_before,
        "alias_before": alias_before,
        "all_versions": ["VERSION$1", "VERSION$2", "VERSION$3"],
    }))


def test_rollback_reads_snapshot_and_reassigns_alias(tmp_path):
    snapshot = tmp_path / "snap.json"
    _write_snapshot(snapshot, {"production": "VERSION$1"}, "VERSION$3")

    with patch.object(rb, "load_env_config", return_value={
            "deployment": {"agents_schema": "AGENTS"}}), \
         patch.object(rb, "version_exists", return_value=True), \
         patch.object(rb, "get_aliases", return_value={"production": "VERSION$3"}), \
         patch.object(rb, "set_alias") as mock_set:
        result = rb.rollback_agent(
            "DB.SCH.AGENT",
            env="prod",
            alias="production",
            snapshot_path=snapshot,
            connection=FakeConn(),
        )

    mock_set.assert_called_once()
    args, kwargs = mock_set.call_args
    # set_alias(conn, fqn, version, alias)
    assert args[1] == "DB.SCH.AGENT"
    assert args[2] == "VERSION$1"
    assert args[3] == "production"
    assert result.target_version == "VERSION$1"
    assert result.previous_version == "VERSION$3"


def test_rollback_noop_guard_raises(tmp_path):
    snapshot = tmp_path / "snap.json"
    _write_snapshot(snapshot, {"production": "VERSION$3"}, "VERSION$3")
    with patch.object(rb, "load_env_config", return_value={
            "deployment": {"agents_schema": "AGENTS"}}), \
         patch.object(rb, "version_exists", return_value=True), \
         patch.object(rb, "get_aliases", return_value={"production": "VERSION$3"}):
        with pytest.raises(RuntimeError, match="already at"):
            rb.rollback_agent(
                "DB.SCH.AGENT",
                env="prod",
                alias="production",
                snapshot_path=snapshot,
                connection=FakeConn(),
            )


def test_rollback_missing_target_version_raises(tmp_path):
    snapshot = tmp_path / "snap.json"
    _write_snapshot(snapshot, {"production": "VERSION$99"}, "VERSION$99")
    with patch.object(rb, "load_env_config", return_value={
            "deployment": {"agents_schema": "AGENTS"}}), \
         patch.object(rb, "version_exists", return_value=False):
        with pytest.raises(RuntimeError, match="not found"):
            rb.rollback_agent(
                "DB.SCH.AGENT",
                env="prod",
                alias="production",
                snapshot_path=snapshot,
                connection=FakeConn(),
            )


def test_rollback_explicit_to_overrides_snapshot(tmp_path):
    snapshot = tmp_path / "snap.json"
    _write_snapshot(snapshot, {"production": "VERSION$1"}, "VERSION$5")
    with patch.object(rb, "load_env_config", return_value={
            "deployment": {"agents_schema": "AGENTS"}}), \
         patch.object(rb, "version_exists", return_value=True), \
         patch.object(rb, "get_aliases", return_value={"production": "VERSION$5"}), \
         patch.object(rb, "set_alias") as mock_set:
        result = rb.rollback_agent(
            "DB.SCH.AGENT",
            env="prod",
            alias="production",
            target_version="VERSION$2",
            snapshot_path=snapshot,
            connection=FakeConn(),
        )
    assert result.target_version == "VERSION$2"
    assert mock_set.call_args[0][2] == "VERSION$2"
