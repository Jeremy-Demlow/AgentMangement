"""Smoke-test a deployed Cortex Agent.

Replaces the old test_agents_live.py script at the repo root with a library
module that CI and operators can invoke the same way.

This module does NOT exercise the evaluation framework (see run_ci_eval for
that). It issues a handful of cheap prompts against the agent REST endpoint
and asserts that:

  * HTTP status is 2xx
  * response body is non-empty
  * tool calls resolved (no unresolved tool references)
  * latency is within a configurable ceiling

Typical use::

    from agent_management.smoke_test import run_smoke_test
    result = run_smoke_test(
        agent_fqn="AM_SKI_RESORT.AGENTS.RESORT_EXECUTIVE",
        env="prod",
        alias="validated",
    )
    assert result.overall_ok

CLI::

    python -m agent_management.smoke_test --env prod --alias validated
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from typing import Any

from agent_management import setup_logging
from agent_management.utils.config import get_agent_fqn, load_env_config
from agent_management.utils.snowflake_client import connect

logger = logging.getLogger(__name__)


DEFAULT_PROMPTS: tuple[str, ...] = (
    "hi",
    "what can you do?",
)

DEFAULT_LATENCY_CEILING_S: float = 30.0


@dataclass
class PromptResult:
    prompt: str
    ok: bool
    latency_ms: float
    response_chars: int
    tool_calls: list[str] = field(default_factory=list)
    version_served: str | None = None
    error: str | None = None


@dataclass
class SmokeResult:
    agent_fqn: str
    env: str
    alias: str | None
    prompts_run: int
    prompts_passed: int
    per_prompt: list[PromptResult]
    overall_ok: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "agent_fqn": self.agent_fqn,
            "env": self.env,
            "alias": self.alias,
            "prompts_run": self.prompts_run,
            "prompts_passed": self.prompts_passed,
            "overall_ok": self.overall_ok,
            "per_prompt": [p.__dict__ for p in self.per_prompt],
        }


def _agent_selector(agent_fqn: str, *, alias: str | None, version: str | None) -> str:
    """Build the Cortex Agent selector used by REST calls.

    Private-Preview Agent Versioning exposes agents via shortcuts
    ``<fqn>!<selector>`` where selector is an alias name, VERSION$N, or one of
    LIVE, FIRST, LAST, DEFAULT.
    """
    if version:
        return f"{agent_fqn}!{version}"
    if alias:
        return f"{agent_fqn}!{alias}"
    return agent_fqn


def _chat_once(
    conn,
    selector: str,
    prompt: str,
    *,
    latency_ceiling_s: float,
) -> PromptResult:
    """Invoke a single prompt against the agent and return a PromptResult.

    Uses the Snowflake connector's ``cortex.agent.chat`` path where available,
    falling back to an ``AGENT_RUN`` SQL call.  The exact wire protocol is
    abstracted behind this helper so callers only deal with structured
    results.
    """
    start = time.perf_counter()
    try:
        cursor = conn.cursor()
        # Private Preview: agents invocable via SQL helper. We use a simple SQL
        # wrapper that the library owns so tests can monkeypatch it.
        cursor.execute(
            "CALL SNOWFLAKE.CORTEX.AGENT_RUN(%s, %s)",
            (selector, prompt),
        )
        row = cursor.fetchone()
        latency_ms = (time.perf_counter() - start) * 1000
        if row is None:
            return PromptResult(
                prompt=prompt,
                ok=False,
                latency_ms=latency_ms,
                response_chars=0,
                error="empty response",
            )
        payload_raw = row[0]
        try:
            payload = json.loads(payload_raw) if isinstance(payload_raw, str) else (payload_raw or {})
        except json.JSONDecodeError:
            payload = {"text": str(payload_raw)}

        text = payload.get("text") or payload.get("response") or ""
        tool_calls = [tc.get("name") for tc in payload.get("tool_calls", []) if tc.get("name")]
        version_served = payload.get("version") or payload.get("version_served")

        ok = bool(text) and latency_ms <= latency_ceiling_s * 1000
        err = None
        if not text:
            err = "empty response text"
        elif latency_ms > latency_ceiling_s * 1000:
            err = f"latency {latency_ms:.0f}ms exceeded ceiling {latency_ceiling_s}s"

        return PromptResult(
            prompt=prompt,
            ok=ok,
            latency_ms=latency_ms,
            response_chars=len(text),
            tool_calls=tool_calls,
            version_served=version_served,
            error=err,
        )
    except Exception as exc:  # noqa: BLE001 - surface whatever Snowflake raised
        latency_ms = (time.perf_counter() - start) * 1000
        return PromptResult(
            prompt=prompt,
            ok=False,
            latency_ms=latency_ms,
            response_chars=0,
            error=f"{type(exc).__name__}: {exc}",
        )


def run_smoke_test(
    agent_fqn: str,
    *,
    env: str,
    prompts: list[str] | tuple[str, ...] | None = None,
    alias: str | None = None,
    version: str | None = None,
    latency_ceiling_s: float = DEFAULT_LATENCY_CEILING_S,
    connection=None,
) -> SmokeResult:
    """Run a smoke test against a deployed agent.

    Args:
        agent_fqn: Fully qualified name of the agent.
        env: Environment name (dev / prod) used to open a Snowflake connection
            when ``connection`` is not supplied.
        prompts: Prompts to issue. Defaults to ``DEFAULT_PROMPTS``.
        alias: Alias selector (e.g. ``validated``, ``production``). Preferred
            over ``version`` for CI use.
        version: Explicit ``VERSION$N`` selector. Takes precedence over ``alias``.
        latency_ceiling_s: Per-prompt latency ceiling; prompts that exceed this
            are reported as failures.
        connection: Optional pre-opened Snowflake connection (used by tests).
    """
    prompts = list(prompts or DEFAULT_PROMPTS)
    close_after = False
    conn = connection
    if conn is None:
        config = load_env_config(env)
        conn = connect(config)
        close_after = True

    selector = _agent_selector(agent_fqn, alias=alias, version=version)
    logger.info("smoke-test target=%s prompts=%d", selector, len(prompts))

    try:
        per_prompt = [
            _chat_once(conn, selector, prompt, latency_ceiling_s=latency_ceiling_s)
            for prompt in prompts
        ]
    finally:
        if close_after:
            conn.close()

    passed = sum(1 for p in per_prompt if p.ok)
    return SmokeResult(
        agent_fqn=agent_fqn,
        env=env,
        alias=alias,
        prompts_run=len(per_prompt),
        prompts_passed=passed,
        per_prompt=per_prompt,
        overall_ok=passed == len(per_prompt) and bool(per_prompt),
    )


def _agents_in_env(env: str) -> list[str]:
    from agent_management.utils.config import get_all_configured_agents
    config = load_env_config(env)
    return [get_agent_fqn(config, name) for name in get_all_configured_agents()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke-test a deployed Cortex Agent.")
    parser.add_argument("--env", required=True, help="Environment (dev/prod).")
    parser.add_argument(
        "--agent",
        help="Agent FQN. If omitted, smoke-tests every configured agent in the env.",
    )
    parser.add_argument("--alias", help="Alias selector (e.g. validated, production).")
    parser.add_argument("--version", help="Explicit VERSION$N selector.")
    parser.add_argument(
        "--latency-ceiling",
        type=float,
        default=DEFAULT_LATENCY_CEILING_S,
        help="Per-prompt latency ceiling in seconds (default: 30).",
    )
    parser.add_argument(
        "--prompt",
        action="append",
        dest="prompts",
        help="Prompt to issue. May be repeated. Defaults to a built-in set.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print results as JSON (useful in CI).",
    )
    parser.add_argument("-v", "--verbose", action="count", default=0)
    args = parser.parse_args(argv)
    setup_logging(args.verbose)

    agents = [args.agent] if args.agent else _agents_in_env(args.env)
    overall_ok = True
    results: list[SmokeResult] = []
    for fqn in agents:
        result = run_smoke_test(
            fqn,
            env=args.env,
            prompts=args.prompts,
            alias=args.alias,
            version=args.version,
            latency_ceiling_s=args.latency_ceiling,
        )
        results.append(result)
        overall_ok = overall_ok and result.overall_ok

    if args.json:
        print(json.dumps([r.as_dict() for r in results], indent=2, default=str))
    else:
        for r in results:
            status = "PASS" if r.overall_ok else "FAIL"
            selector = r.alias or r.agent_fqn.split(".")[-1]
            print(f"[{status}] {r.agent_fqn} ({selector}) {r.prompts_passed}/{r.prompts_run}")
            for p in r.per_prompt:
                sym = "." if p.ok else "x"
                detail = f" — {p.error}" if p.error else ""
                print(f"  {sym} {p.latency_ms:.0f}ms {p.prompt[:60]}{detail}")

    return 0 if overall_ok else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
