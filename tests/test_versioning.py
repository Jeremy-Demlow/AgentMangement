"""Unit tests for agent_management.versioning."""
from __future__ import annotations

from unittest.mock import MagicMock

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
    cur = FakeCursor()
    conn = FakeConn(cur)
    with pytest.raises(ValueError):
        versioning.set_alias(conn, "DB.SCH.AGENT", "V3", "production")


def test_set_alias_rejects_bad_fqn():
    cur = FakeCursor()
    conn = FakeConn(cur)
    with pytest.raises(ValueError):
        versioning.set_alias(conn, "DB.SCH.AGENT;DROP", "VERSION$1", "production")


def test_list_versions_parses_rows():
    cur = FakeCursor()
    cur.set_result(
        description=[("name",), ("created_on",), ("comment",)],
        rows=[("VERSION$1", "2026-01-01", ""), ("VERSION$2", "2026-02-01", "note")],
    )
    conn = FakeConn(cur)
    versions = versioning.list_versions(conn, "DB.SCH.AGENT")
    assert [v.name for v in versions] == ["VERSION$1", "VERSION$2"]
    assert versions[1].comment == "note"


def test_version_exists_true_and_false():
    cur = FakeCursor()
    cur.set_result([("name",)], [("VERSION$1",), ("VERSION$2",)])
    conn = FakeConn(cur)
    assert versioning.version_exists(conn, "DB.SCH.AGENT", "VERSION$2")
    # reset rows but version_exists calls list_versions -> same SHOW result.
    assert not versioning.version_exists(conn, "DB.SCH.AGENT", "VERSION$99")


def test_commit_version_emits_four_step_sequence_and_returns_new_version():
    cur = FakeCursor()
    conn = FakeConn(cur)

    # After COMMIT LIVE, list_versions is called. Feed it two versions.
    def exec_spy(sql, params=None):
        cur.executed.append((sql, params))
        # After the third execute (COMMIT LIVE), subsequent SHOW VERSIONS
        # should see a new committed version.
        if "SHOW VERSIONS" in sql:
            cur._description = [("name",)]
            cur._rows = [("VERSION$1",), ("VERSION$2",)]

    cur.execute = exec_spy  # type: ignore[assignment]

    result = versioning.commit_version(conn, "DB.SCH.AGENT", "spec: yaml")
    assert result == "VERSION$2"

    sqls = [s for s, _ in cur.executed]
    assert sqls[0] == "ALTER AGENT DB.SCH.AGENT ADD LIVE VERSION FROM LAST"
    assert "MODIFY LIVE VERSION SET SPEC FROM" in sqls[1]
    assert sqls[2] == "ALTER AGENT DB.SCH.AGENT COMMIT LIVE VERSION"
    assert "SHOW VERSIONS" in sqls[3]


def test_commit_initial_uses_add_live_without_from_last():
    cur = FakeCursor()
    conn = FakeConn(cur)

    def exec_spy(sql, params=None):
        cur.executed.append((sql, params))
        if "SHOW VERSIONS" in sql:
            cur._description = [("name",)]
            cur._rows = [("VERSION$1",)]

    cur.execute = exec_spy  # type: ignore[assignment]
    versioning.commit_version(conn, "DB.SCH.AGENT", "spec: yaml", initial=True)
    sqls = [s for s, _ in cur.executed]
    assert sqls[0] == "ALTER AGENT DB.SCH.AGENT ADD LIVE VERSION"
    assert "FROM LAST" not in sqls[0]


def test_drop_version_refuses_aliased_unless_force():
    # SHOW ALIASES returns VERSION$3 on alias=production.
    cur = FakeCursor()

    def exec_spy(sql, params=None):
        cur.executed.append((sql, params))
        if "SHOW ALIASES" in sql:
            cur._description = [("alias",), ("version",)]
            cur._rows = [("production", "VERSION$3")]

    cur.execute = exec_spy  # type: ignore[assignment]
    conn = FakeConn(cur)

    with pytest.raises(RuntimeError, match="still holds alias"):
        versioning.drop_version(conn, "DB.SCH.AGENT", "VERSION$3")

    # with force=True it proceeds without checking aliases
    versioning.drop_version(conn, "DB.SCH.AGENT", "VERSION$3", force=True)
    dropped_sql = cur.executed[-1][0]
    assert dropped_sql == "ALTER AGENT DB.SCH.AGENT DROP VERSION VERSION$3"


def test_promote_alias_no_op_when_target_already_correct():
    cur = FakeCursor()
    cur.set_result(
        [("alias",), ("version",)],
        [("validated", "VERSION$5"), ("production", "VERSION$5")],
    )
    conn = FakeConn(cur)
    result = versioning.promote_alias(
        conn, "DB.SCH.AGENT", from_alias="validated", to_alias="production"
    )
    assert result == "VERSION$5"
    # Only one execute (the SHOW ALIASES); no ALTER AGENT emitted.
    assert not any("MODIFY VERSION" in sql for sql, _ in cur.executed)


def test_promote_alias_missing_source_raises():
    cur = FakeCursor()
    cur.set_result([("alias",), ("version",)], [("production", "VERSION$1")])
    conn = FakeConn(cur)
    with pytest.raises(RuntimeError, match="not set"):
        versioning.promote_alias(
            conn, "DB.SCH.AGENT", from_alias="validated", to_alias="production"
        )
