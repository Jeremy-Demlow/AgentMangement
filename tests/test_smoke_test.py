"""Unit tests for agent_management.agents.smoke."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

from agent_management.agents import smoke as st


def test_build_url_with_alias():
    url = st._build_url(
        "https://org-acct.snowflakecomputing.com",
        "DB.SCH.AGENT",
        alias="validated",
        version=None,
    )
    assert url == "https://org-acct.snowflakecomputing.com/api/v2/databases/DB/schemas/SCH/agents/AGENT/versions/VALIDATED:run"


def test_build_url_with_version():
    url = st._build_url(
        "https://org-acct.snowflakecomputing.com",
        "DB.SCH.AGENT",
        alias=None,
        version="VERSION$3",
    )
    # $ is URL-encoded
    assert url.endswith("/agents/AGENT/versions/VERSION%243:run")


def test_build_url_no_selector():
    url = st._build_url(
        "https://org-acct.snowflakecomputing.com",
        "DB.SCH.AGENT",
        alias=None,
        version=None,
    )
    assert url.endswith("/agents/AGENT:run")


def test_split_fqn_rejects_bad_input():
    import pytest
    with pytest.raises(ValueError):
        st._split_fqn("AGENT")


def _sse_response(status: int, events: list[tuple[str, dict]]):
    """Build a mock Response whose iter_lines yields SSE-formatted bytes."""
    lines: list[bytes] = []
    for event, data in events:
        lines.append(f"event: {event}".encode())
        lines.append(f"data: {json.dumps(data)}".encode())
    resp = MagicMock()
    resp.status_code = status
    resp.text = ""
    resp.iter_lines.return_value = iter(lines)
    return resp


class FakeSession:
    def __init__(self, response):
        self._response = response
        self.calls = []

    def post(self, url, **kw):
        self.calls.append((url, kw))
        return self._response


class FakeConn:
    """Fake Snowflake connection that satisfies smoke_test's needs.

    smoke_test issues two queries via cursor():
      1. SELECT CURRENT_ORGANIZATION_NAME(), CURRENT_ACCOUNT_NAME()  -> org URL
      2. DESCRIBE AGENT <fqn>                                         -> alias JSON
    The second is consumed by versioning.get_aliases() inside
    smoke_test._preflight_selector(). Without alias data, preflight refuses to
    run because no committed version carries the alias under test.
    """

    def __init__(self, aliases: dict | None = None):
        self.rest = MagicMock()
        self.rest.token = "fake-token"
        if aliases is None:
            aliases = {"DEFAULT": "VERSION$1", "LATEST": "VERSION$1"}
        self._aliases_json = json.dumps(aliases)

    def cursor(self):
        cur = MagicMock()
        # Track which kind of query was last executed so the right fetchone()
        # / description shape is returned.
        state = {"kind": "org"}

        def execute(sql, *args, **kwargs):
            if "DESCRIBE AGENT" in sql.upper():
                state["kind"] = "describe_agent"
            else:
                state["kind"] = "org"
            return None

        def fetchone():
            if state["kind"] == "describe_agent":
                return ("AGENT", self._aliases_json)
            return ("ORG", "ACCT")

        # description is read after execute(); MagicMock attribute access works.
        def get_description():
            if state["kind"] == "describe_agent":
                return [("name",), ("aliases",)]
            return [("CURRENT_ORGANIZATION_NAME()",), ("CURRENT_ACCOUNT_NAME()",)]

        cur.execute.side_effect = execute
        cur.fetchone.side_effect = fetchone
        type(cur).description = property(lambda _self: get_description())
        return cur


def test_run_smoke_test_happy_path():
    events = [
        ("response.text.delta", {"text": "hello "}),
        ("response.text.delta", {"text": "world"}),
    ]
    resp = _sse_response(200, events)
    session = FakeSession(resp)
    result = st.run_smoke_test(
        "DB.SCH.AGENT",
        env="dev",
        prompts=("ping",),
        alias="latest",
        connection=FakeConn(),
        session=session,
    )
    assert result.overall_ok
    assert result.prompts_passed == 1
    assert result.per_prompt[0].response_chars == len("hello world")
    assert session.calls, "REST POST should have been issued"
    url, _ = session.calls[0]
    assert "/agents/AGENT/versions/LATEST:run" in url


def test_run_smoke_test_empty_text_fails():
    resp = _sse_response(200, [])
    session = FakeSession(resp)
    result = st.run_smoke_test(
        "DB.SCH.AGENT",
        env="dev",
        prompts=("ping",),
        alias="latest",
        connection=FakeConn(),
        session=session,
    )
    assert not result.overall_ok
    assert result.per_prompt[0].error == "empty response text"


def test_run_smoke_test_non_200_fails():
    resp = MagicMock()
    resp.status_code = 500
    resp.text = "boom"
    resp.iter_lines.return_value = iter([])
    session = FakeSession(resp)
    result = st.run_smoke_test(
        "DB.SCH.AGENT",
        env="dev",
        prompts=("ping",),
        alias="latest",
        connection=FakeConn(),
        session=session,
    )
    assert not result.overall_ok
    assert "HTTP 500" in result.per_prompt[0].error


def test_run_smoke_test_captures_tool_uses():
    events = [
        ("response.tool_use", {"name": "DailyKPIs", "type": "cortex_analyst_text_to_sql"}),
        ("response.text.delta", {"text": "done"}),
    ]
    resp = _sse_response(200, events)
    session = FakeSession(resp)
    result = st.run_smoke_test(
        "DB.SCH.AGENT", env="dev", prompts=("ping",), alias="latest",
        connection=FakeConn(), session=session,
    )
    assert result.per_prompt[0].tool_uses == ["DailyKPIs"]
