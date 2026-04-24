"""Unit tests for agent_management.smoke_test."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

from agent_management import smoke_test as st


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
    def __init__(self):
        self.rest = MagicMock()
        self.rest.token = "fake-token"

    def cursor(self):
        cur = MagicMock()
        cur.execute.return_value = None
        cur.fetchone.return_value = ("ORG", "ACCT")
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
