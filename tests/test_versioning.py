"""Unit tests for agent_management.versioning."""
from __future__ import annotations

import pytest

from agent_management import versioning


class FakeCursor:
    def __init__(self):
        self.executed: list[tuple[str, tuple | None]] = []
        self._rows: list[tuple] = []
        self._description: list[tuple] = []

    def set_result(self, description, rows):
        self._description = description
        self._rows = rows

    @property
    def description(self):
        return self._description

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


class FakeConn:
    def __init__(self, cursor: FakeCursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


def test_set_alias_emits_expected_sql():
    cur = FakeCursor()
    conn = FakeConn(cur)
    versioning.set_alias(conn, "DB.SCH.AGENT", "VERSION$3", "production")
    sql, _ = cur.executed[0]
    assert sql == "ALTER AGENT DB.SCH.AGENT MODIFY VERSION VERSION$3 SET ALIAS = production"


def test_set_alias_rejects_bad_version_name():
    conn = FakeConn(FakeCursor())
    with pytest.raises(ValueError):
        versioning.set_alias(conn, "DB.SCH.AGENT", "V3", "production")


def test_set_alias_rejects_reserved_alias():
    conn = FakeConn(FakeCursor())
    for reserved in ("LAST", "FIRST", "LIVE", "DEFAULT"):
        with pytest.raises(ValueError):
            versioning.set_alias(conn, "DB.SCH.AGENT", "VERSION$1", reserved)


def test_set_alias_rejects_bad_fqn():
    conn = FakeConn(FakeCursor())
    with pytest.raises(ValueError):
        versioning.set_alias(conn, "DB.SCH.AGENT;DROP", "VERSION$1", "production")


def test_list_versions_parses_and_sorts_oldest_first():
    cur = FakeCursor()
    # SHOW VERSIONS returns newest-first, library should reverse to oldest-first.
    cur.set_result(
        description=[("created_on",), ("name",), ("alias",), ("spec_file_path",),
                     ("is_default",), ("comment",), ("profile",)],
        rows=[
            ("2026-01-02", "VERSION$2", None, "p", True, "", ""),
            ("2026-01-01", "VERSION$1", "LATEST", "p", False, "", ""),
        ],
    )
    conn = FakeConn(cur)
    versions = versioning.list_versions(conn, "DB.SCH.AGENT")
    assert [v.name for v in versions] == ["VERSION$1", "VERSION$2"]
    assert versions[0].alias == "LATEST"
    assert versions[1].is_default is True


def test_list_versions_skips_live_draft_by_default():
    cur = FakeCursor()
    cur.set_result(
        description=[("created_on",), ("name",), ("alias",), ("spec_file_path",),
                     ("is_default",), ("comment",), ("profile",)],
        rows=[
            ("2026-01-02", "", None, "p", False, "", ""),   # empty = LIVE draft
            ("2026-01-01", "VERSION$1", None, "p", True, "", ""),
        ],
    )
    conn = FakeConn(cur)
    versions = versioning.list_versions(conn, "DB.SCH.AGENT")
    assert [v.name for v in versions] == ["VERSION$1"]


def test_get_aliases_reads_from_describe_agent_json():
    """get_aliases() reads alias dict from DESCRIBE AGENT 'aliases' JSON column.

    Regression: SHOW VERSIONS alias column is unreliable (often empty even when
    aliases exist). DESCRIBE AGENT exposes the canonical alias->version map as
    a JSON object on the 'aliases' column.
    """
    cur = FakeCursor()
    cur.set_result(
        description=[("name",), ("aliases",)],
        rows=[("AGENT", '{"DEFAULT": "VERSION$2", "LATEST": "VERSION$1", "LAST": "VERSION$2"}')],
    )
    conn = FakeConn(cur)
    assert versioning.get_aliases(conn, "DB.SCH.AGENT") == {
        "DEFAULT": "VERSION$2",
        "LATEST": "VERSION$1",
        "LAST": "VERSION$2",
    }


def test_has_live_draft_true_when_empty_name_row_present():
    cur = FakeCursor()
    cur.set_result(
        description=[("created_on",), ("name",)],
        rows=[("2026-01-02", ""), ("2026-01-01", "VERSION$1")],
    )
    conn = FakeConn(cur)
    assert versioning.has_live_draft(conn, "DB.SCH.AGENT") is True


def test_modify_live_spec_uses_specification_and_doubledollar():
    cur = FakeCursor()
    conn = FakeConn(cur)
    versioning.modify_live_spec(conn, "DB.SCH.AGENT", "models: {}\n")
    sql, _ = cur.executed[0]
    assert "MODIFY LIVE VERSION SET SPECIFICATION = $$" in sql
    assert "$$" in sql
    assert "models: {}" in sql


def test_commit_live_sequence_and_returns_newest():
    cur = FakeCursor()
    conn = FakeConn(cur)

    def exec_spy(sql, params=None):
        cur.executed.append((sql, params))
        if "SHOW VERSIONS" in sql:
            cur._description = [
                ("created_on",), ("name",), ("alias",), ("spec_file_path",),
                ("is_default",), ("comment",), ("profile",),
            ]
            cur._rows = [
                ("2026-01-02", "VERSION$2", None, "p", True, "", ""),
                ("2026-01-01", "VERSION$1", None, "p", False, "", ""),
            ]

    cur.execute = exec_spy  # type: ignore[assignment]
    result = versioning.commit_live(conn, "DB.SCH.AGENT")
    assert result == "VERSION$2"
    sqls = [s for s, _ in cur.executed]
    assert sqls[0] == "ALTER AGENT DB.SCH.AGENT COMMIT"


def test_commit_version_seed_from_last_and_full_flow():
    cur = FakeCursor()
    conn = FakeConn(cur)

    call_index = {"n": 0}

    def exec_spy(sql, params=None):
        cur.executed.append((sql, params))
        call_index["n"] += 1
        if "SHOW VERSIONS" in sql:
            # First SHOW (from has_live_draft): no LIVE, some versions.
            # Subsequent SHOW (from commit_live): add a new committed row.
            if call_index["n"] <= 1:
                cur._description = [
                    ("created_on",), ("name",), ("alias",), ("spec_file_path",),
                    ("is_default",), ("comment",), ("profile",),
                ]
                cur._rows = [("2026-01-01", "VERSION$1", None, "p", True, "", "")]
            else:
                cur._rows = [
                    ("2026-01-02", "VERSION$2", None, "p", True, "", ""),
                    ("2026-01-01", "VERSION$1", None, "p", False, "", ""),
                ]

    cur.execute = exec_spy  # type: ignore[assignment]
    result = versioning.commit_version(conn, "DB.SCH.AGENT", "models: {}\n")
    assert result == "VERSION$2"

    sqls = [s for s, _ in cur.executed]
    # First SHOW (has_live_draft), then ADD LIVE FROM LAST, MODIFY LIVE, COMMIT,
    # then SHOW VERSIONS again from commit_live.
    assert any("SHOW VERSIONS" in s for s in sqls)
    assert any("ADD LIVE VERSION FROM LAST" in s for s in sqls)
    assert any("MODIFY LIVE VERSION SET SPECIFICATION" in s for s in sqls)
    assert any(s.endswith("COMMIT") or " COMMIT" in s for s in sqls)


def test_commit_version_first_deploy_without_seed():
    cur = FakeCursor()
    conn = FakeConn(cur)

    def exec_spy(sql, params=None):
        cur.executed.append((sql, params))
        if "SHOW VERSIONS" in sql:
            cur._description = [
                ("created_on",), ("name",), ("alias",), ("spec_file_path",),
                ("is_default",), ("comment",), ("profile",),
            ]
            # Include LIVE draft row so seed_from_last=False path works.
            cur._rows = [
                ("2026-01-01T01", "VERSION$2", None, "p", True, "", ""),
                ("2026-01-01T00", "", None, "p", False, "", ""),
                ("2026-01-01", "VERSION$1", None, "p", False, "", ""),
            ]

    cur.execute = exec_spy  # type: ignore[assignment]
    result = versioning.commit_version(
        conn, "DB.SCH.AGENT", "models: {}\n", seed_from_last=False,
    )
    assert result == "VERSION$2"
    sqls = [s for s, _ in cur.executed]
    # Should NOT emit ADD LIVE FROM LAST on first deploy
    assert not any("ADD LIVE VERSION FROM LAST" in s for s in sqls)


def test_promote_alias_no_op_when_target_already_correct():
    """promote_alias is a no-op when from_alias and to_alias point at the same version."""
    cur = FakeCursor()
    cur.set_result(
        description=[("name",), ("aliases",)],
        rows=[("AGENT", '{"DEFAULT": "VERSION$5", "VALIDATED": "VERSION$5", "PRODUCTION": "VERSION$5"}')],
    )
    conn = FakeConn(cur)
    result = versioning.promote_alias(
        conn, "DB.SCH.AGENT", from_alias="validated", to_alias="production",
    )
    assert result == "VERSION$5"
    # No ALTER AGENT statement emitted (no-op guard)
    assert not any("MODIFY VERSION" in sql for sql, _ in cur.executed)


def test_promote_alias_missing_source_raises():
    cur = FakeCursor()
    cur.set_result(
        description=[("name",), ("aliases",)],
        rows=[("AGENT", '{"DEFAULT": "VERSION$1", "PRODUCTION": "VERSION$1"}')],
    )
    conn = FakeConn(cur)
    with pytest.raises(RuntimeError, match="not set"):
        versioning.promote_alias(
            conn, "DB.SCH.AGENT", from_alias="validated", to_alias="production"
        )
