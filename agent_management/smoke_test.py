"""Smoke-test a deployed Cortex Agent via the real REST API.

The Cortex Agent chat endpoint is:

    POST https://<org>-<account>.snowflakecomputing.com
        /api/v2/databases/<db>/schemas/<schema>/agents/<agent_name>:run

It returns a Server-Sent Events (SSE) stream. See
``agent-evaluation/scripts/invoke_agent.py`` for the reference implementation
this module is patterned on.

Version / alias selectors: the REST payload supports targeting a specific
version by appending ``!<alias>`` or ``!<VERSION$N>`` to the agent name in the
URL (the Private Preview accepts ``AGENT_NAME!alias``). The library handles
the URL construction.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

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
    tool_uses: list[str] = field(default_factory=list)
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


def _split_fqn(agent_fqn: str) -> tuple[str, str, str]:
    parts = agent_fqn.split(".")
    if len(parts) != 3:
        raise ValueError(f"Expected DB.SCHEMA.AGENT, got {agent_fqn!r}")
    return parts[0], parts[1], parts[2]


def _base_url(conn) -> str:
    cur = conn.cursor()
    cur.execute("SELECT CURRENT_ORGANIZATION_NAME(), CURRENT_ACCOUNT_NAME()")
    org, account = cur.fetchone()
    account_fixed = account.replace("_", "-").lower()
    org_fixed = org.lower()
    return f"https://{org_fixed}-{account_fixed}.snowflakecomputing.com"


def _build_url(base_url: str, agent_fqn: str, *, alias: str | None, version: str | None) -> str:
    """Build the REST URL for an agent invocation.

    The Cortex Agent REST API exposes version / alias routing via a path
    segment: ``/agents/<name>/versions/<selector>:run``. The ``selector`` can
    be a user alias (``latest``, ``validated``, ``production``), a reserved
    alias (``LATEST``, ``LAST``, ``FIRST``, ``DEFAULT``), or an explicit
    ``VERSION$N`` (the ``$`` must be URL-encoded).

    Without a selector we hit ``/agents/<name>:run``, which routes to the
    DEFAULT alias (the most recent committed version).
    """
    db, schema, name = _split_fqn(agent_fqn)
    name_q = quote(name, safe="")
    selector = version or alias
    if selector:
        # VERSION$N contains $ which must be percent-encoded.
        # Aliases are stored uppercase by Snowflake; the URL is case-sensitive.
        normalized = selector.upper() if alias and not version else selector
        selector_q = quote(normalized, safe="")
        return (
            f"{base_url}/api/v2/databases/{db}/schemas/{schema}"
            f"/agents/{name_q}/versions/{selector_q}:run"
        )
    return (
        f"{base_url}/api/v2/databases/{db}/schemas/{schema}"
        f"/agents/{name_q}:run"
    )


def _invoke_once(
    conn,
    base_url: str,
    agent_fqn: str,
    prompt: str,
    *,
    alias: str | None,
    version: str | None,
    latency_ceiling_s: float,
    session: Any | None = None,
    max_attempts: int = 2,
    retry_sleep_s: float = 30.0,
) -> PromptResult:
    """Send a single prompt with 2-attempt retry on transient 5xx / request errors.

    Cortex Agent REST sometimes returns HTTP 500 INTERNAL_ERROR or connection
    drops on the first call immediately after deploy. A short sleep + one
    retry reliably papers over this without masking real failures.
    """
    last: PromptResult | None = None
    for attempt in range(1, max_attempts + 1):
        result = _invoke_once_raw(
            conn, base_url, agent_fqn, prompt,
            alias=alias, version=version,
            latency_ceiling_s=latency_ceiling_s, session=session,
        )
        if result.ok:
            return result
        # Retry only on transient-looking failures (HTTP 5xx or request exceptions)
        err = (result.error or "").lower()
        transient = (
            "request_exception" in err
            or "http 5" in err
            or "timeout" in err
            or "internal_error" in err
        )
        last = result
        if not transient or attempt >= max_attempts:
            return result
        logger.warning(
            "smoke prompt transient failure on attempt %d/%d: %s — retrying in %.0fs",
            attempt, max_attempts, result.error, retry_sleep_s,
        )
        time.sleep(retry_sleep_s)
    return last  # type: ignore[return-value]


def _invoke_once_raw(
    conn,
    base_url: str,
    agent_fqn: str,
    prompt: str,
    *,
    alias: str | None,
    version: str | None,
    latency_ceiling_s: float,
    session: Any | None = None,
) -> PromptResult:
    import requests  # local import; keeps module import-lightweight

    url = _build_url(base_url, agent_fqn, alias=alias, version=version)
    token = conn.rest.token
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f'Snowflake Token="{token}"',
    }
    payload = {
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": prompt}]}
        ]
    }

    start = time.perf_counter()
    http = session or requests
    try:
        response = http.post(url, headers=headers, json=payload, stream=True, timeout=latency_ceiling_s + 5)
    except Exception as exc:  # noqa: BLE001
        return PromptResult(
            prompt=prompt, ok=False,
            latency_ms=(time.perf_counter() - start) * 1000,
            response_chars=0,
            error=f"request_exception: {type(exc).__name__}: {exc}",
        )

    if response.status_code != 200:
        latency_ms = (time.perf_counter() - start) * 1000
        return PromptResult(
            prompt=prompt, ok=False, latency_ms=latency_ms, response_chars=0,
            error=f"HTTP {response.status_code}: {response.text[:300]}",
        )

    answer_parts: list[str] = []
    tool_uses: list[str] = []
    version_served: str | None = None
    current_event: str | None = None

    for raw in response.iter_lines():
        if not raw:
            continue
        line = raw.decode("utf-8")
        if line.startswith("event: "):
            current_event = line[7:].strip()
            continue
        if not line.startswith("data: "):
            continue
        data = line[6:].strip()
        if data == "[DONE]":
            break
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError:
            continue

        if current_event == "response.tool_use" and parsed.get("name"):
            tool_uses.append(parsed["name"])
        elif current_event == "response.text.delta" and "text" in parsed:
            answer_parts.append(parsed["text"])
        elif current_event == "response.text" and "text" in parsed and not answer_parts:
            answer_parts.append(parsed["text"])
        # Some payloads expose the served version on the final event.
        if "version" in parsed and not version_served:
            version_served = str(parsed["version"])

    latency_ms = (time.perf_counter() - start) * 1000
    text = "".join(answer_parts)
    ok = bool(text) and latency_ms <= latency_ceiling_s * 1000
    err = None
    if not text:
        err = "empty response text"
    elif latency_ms > latency_ceiling_s * 1000:
        err = f"latency {latency_ms:.0f}ms exceeded ceiling {latency_ceiling_s}s"

    return PromptResult(
        prompt=prompt, ok=ok, latency_ms=latency_ms,
        response_chars=len(text),
        tool_uses=tool_uses, version_served=version_served, error=err,
    )


def _preflight_selector(
    conn,
    agent_fqn: str,
    *,
    alias: str | None,
    version: str | None,
) -> None:
    """Validate that the requested alias/version exists BEFORE hitting REST.

    Uses ``DESCRIBE AGENT`` to read the canonical alias dict. Raises
    ``RuntimeError`` with a precise message when:
      - the agent exists but the requested alias is not set
      - neither alias nor version is given but DEFAULT alias is missing
        (bare ``/agents/X:run`` would then fail with the ``Version 'live'
        not found`` error the deploy pipeline hit in earlier runs)

    Keeps smoke tests from masking post-deploy alias issues as generic
    Cortex API errors.
    """
    # Local import avoids circular dependency with versioning.
    from agent_management.versioning import get_aliases, list_versions

    try:
        aliases = get_aliases(conn, agent_fqn)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"smoke preflight: DESCRIBE AGENT {agent_fqn} failed: {exc}") from exc

    if version:
        versions = {v.name.upper() for v in list_versions(conn, agent_fqn)}
        if version.upper() not in versions:
            raise RuntimeError(
                f"smoke preflight: version {version!r} does not exist on "
                f"{agent_fqn}. known versions: {sorted(versions)}"
            )
        return

    if alias:
        key = alias.upper()
        # LIVE/FIRST/LAST/DEFAULT are always computed; user aliases (latest,
        # validated, production) must be explicitly set.
        if key in {"FIRST", "LAST", "DEFAULT", "LIVE"}:
            if key == "LIVE":
                # LIVE only exists while an uncommitted draft exists, which is
                # almost never what smoke tests want.
                from agent_management.versioning import has_live_draft
                if not has_live_draft(conn, agent_fqn):
                    raise RuntimeError(
                        f"smoke preflight: alias 'LIVE' requested but no LIVE "
                        f"draft exists on {agent_fqn}. Smoke should point at a "
                        f"user alias (latest/validated/production), not LIVE."
                    )
            return
        if key not in aliases:
            raise RuntimeError(
                f"smoke preflight: alias {alias!r} is not set on {agent_fqn}. "
                f"current aliases: {sorted(aliases)!r}. Deploy must set this "
                f"alias before smoke-testing."
            )
        return

    # No alias, no version: rely on DEFAULT.
    if "DEFAULT" not in aliases:
        raise RuntimeError(
            f"smoke preflight: no alias/version specified and DEFAULT alias "
            f"is missing on {agent_fqn}. Bare /agents/{agent_fqn}:run would "
            f"hit the 'Version live not found' path. Pass --alias latest "
            f"(or equivalent) or make sure deploy set DEFAULT."
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
    session=None,
) -> SmokeResult:
    """Invoke a deployed agent a few times and report pass/fail per prompt."""
    prompts = list(prompts or DEFAULT_PROMPTS)
    close_after = False
    conn = connection
    if conn is None:
        config = load_env_config(env)
        conn = connect(config)
        close_after = True

    try:
        # Pre-flight: verify the target selector resolves to a real version
        # BEFORE hitting the Cortex REST path. A missing alias produces a
        # cryptic "Version 'X' not found" from the agent runtime; we can
        # name the problem here instead.
        _preflight_selector(conn, agent_fqn, alias=alias, version=version)
        base_url = _base_url(conn)
        selector = f"{agent_fqn}!{version or alias}" if (version or alias) else agent_fqn
        logger.info("smoke-test target=%s prompts=%d", selector, len(prompts))
        per_prompt = [
            _invoke_once(
                conn, base_url, agent_fqn, prompt,
                alias=alias, version=version,
                latency_ceiling_s=latency_ceiling_s,
                session=session,
            )
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
    parser.add_argument("--env", required=True, choices=["dev", "prod"])
    parser.add_argument("--agent", help="Agent FQN; all configured if omitted.")
    parser.add_argument("--alias", help="Alias selector (validated, production, latest).")
    parser.add_argument("--version", help="Explicit VERSION$N selector.")
    parser.add_argument("--latency-ceiling", type=float, default=DEFAULT_LATENCY_CEILING_S)
    parser.add_argument("--prompt", action="append", dest="prompts",
                        help="Repeatable. Defaults to a built-in set.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("-v", "--verbose", action="count", default=0)
    args = parser.parse_args(argv)
    setup_logging(args.verbose)

    agents = [args.agent] if args.agent else _agents_in_env(args.env)
    overall_ok = True
    results: list[SmokeResult] = []
    for fqn in agents:
        result = run_smoke_test(
            fqn, env=args.env, prompts=args.prompts,
            alias=args.alias, version=args.version,
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
