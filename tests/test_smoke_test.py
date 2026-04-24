"""Unit tests for agent_management.smoke_test."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

from agent_management import smoke_test as st


class FakeCursor:
    def __init__(self, payload):
        self._payload = payload
        self.description = []
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        return (self._payload,)


class FakeConn:
    def __init__(self, payload):
        self._cur = FakeCursor(payload)
        self.closed = False

    def cursor(self):
        return self._cur

    def close(self):
        self.closed = True


def test_selector_with_alias():
    assert st._agent_selector("A.B.C", alias="validated", version=None) == "A.B.C!validated"


def test_selector_with_version_takes_precedence():
    assert st._agent_selector("A.B.C", alias="validated", version="VERSION$3") == "A.B.C!VERSION$3"


def test_selector_none_returns_bare_fqn():
    assert st._agent_selector("A.B.C", alias=None, version=None) == "A.B.C"


def test_run_smoke_test_happy_path():
    payload = json.dumps({"text": "hello", "tool_calls": [{"name": "foo"}], "version": "VERSION$2"})
    conn = FakeConn(payload)
    result = st.run_smoke_test(
        "DB.SCH.AGENT",
        env="dev",
        prompts=("ping",),
        alias="latest",
        connection=conn,
    )
    assert result.overall_ok
    assert result.prompts_passed == 1
    assert result.per_prompt[0].tool_calls == ["foo"]
    # connection was provided; library should not close it.
    assert not conn.closed


def test_run_smoke_test_empty_text_fails():
    payload = json.dumps({"text": ""})
    conn = FakeConn(payload)
    result = st.run_smoke_test(
        "DB.SCH.AGENT",
        env="dev",
        prompts=("ping",),
        alias="latest",
        connection=conn,
    )
    assert not result.overall_ok
    assert result.per_prompt[0].error == "empty response text"
