"""Unit tests for agent_management.snapshot_state (pointer-only)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from agent_management import snapshot_state as ss
from agent_management import versioning


class FakeConn:
    def __init__(self, versions, aliases):
        self._versions = versions
        self._aliases = aliases

    def cursor(self):
        raise RuntimeError("versioning helpers are patched; cursor unused")


def test_snapshot_captures_version_and_aliases(tmp_path: Path):
    conn = FakeConn(
        versions=[versioning.VersionInfo("VERSION$1", None, None, False, None),
                  versioning.VersionInfo("VERSION$2", None, None, True, None)],
        aliases={"production": "VERSION$1", "validated": "VERSION$2"},
    )
    with patch.object(ss, "load_env_config", return_value={
            "deployment": {"agents_schema": "AGENTS"}}), \
         patch.object(ss, "list_versions", return_value=conn._versions), \
         patch.object(ss, "get_aliases", return_value=conn._aliases):
        out = tmp_path / "ptr.json"
        ptr = ss.snapshot_state(
            "DB.SCH.AGENT",
            env="prod",
            out_path=out,
            connection=conn,
        )
    assert ptr.version_before == "VERSION$2"
    assert ptr.alias_before["production"] == "VERSION$1"
    assert ptr.all_versions == ["VERSION$1", "VERSION$2"]

    payload = json.loads(out.read_text())
    assert payload["agent_fqn"] == "DB.SCH.AGENT"
    # No full spec payload — pointer-only.
    assert "spec_yaml" not in payload
    assert "spec" not in payload


def test_snapshot_handles_first_time_agent(tmp_path: Path):
    conn = FakeConn(versions=[], aliases={})
    with patch.object(ss, "load_env_config", return_value={
            "deployment": {"agents_schema": "AGENTS"}}), \
         patch.object(ss, "list_versions", side_effect=Exception("no versions yet")), \
         patch.object(ss, "get_aliases", side_effect=Exception("no aliases yet")):
        out = tmp_path / "ptr.json"
        ptr = ss.snapshot_state(
            "DB.SCH.AGENT",
            env="dev",
            out_path=out,
            connection=conn,
        )
    assert ptr.version_before is None
    assert ptr.alias_before == {}
    assert ptr.all_versions == []
