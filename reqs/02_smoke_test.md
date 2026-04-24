# 02 — agent_management.smoke_test

## Problem

`test_agents_live.py` at the repo root is a loose script. It hard-codes prompts, reads FQNs from `project.yml` via ad-hoc YAML loading, and can't be imported for programmatic use (e.g., a post-deploy sanity check in CI).

## Goal

A library module `agent_management/smoke_test.py` that:

- Exposes `run_smoke_test(agent_fqn, prompts=None, *, env=None, connection=None) -> SmokeResult`
- Wraps the Cortex Agent REST call (`/api/v2/databases/.../schemas/.../agents/.../chat:message` or the versioned equivalent)
- Works with alias shortcuts (`LIVE`, `production`, `dev`) when `agent_versioning.enabled`
- Returns structured result: pass/fail per prompt, latency, response text, version served
- Has a CLI: `python -m agent_management.smoke_test --env qa --agent RESORT_EXECUTIVE`

## Inputs

| Arg | Default | Source |
|-----|---------|--------|
| `agent_fqn` | required | resolved from `environments/<env>.env.yml` agents block |
| `prompts` | `["hi", "what can you do?"]` | optional override |
| `env` | `dev` | CLI `--env` |
| `connection` | active conn | `~/.snowflake/connections.toml` |
| `alias` | None | `--alias production` for version-pinned test |

## Output

```python
@dataclass
class SmokeResult:
    agent_fqn: str
    env: str
    prompts_run: int
    prompts_passed: int
    per_prompt: list[PromptResult]  # text, latency_ms, version, tool_calls
    overall_ok: bool
```

## CI usage

`validate-pr.yml` runs `python -m agent_management.smoke_test --env dev` after deploy to dev.
`deploy-qa-on-main.yml` runs it after QA alias flip.
`promote-prod.yml` runs it post-production alias flip.

## Failure modes

- Non-200 from agent API → fail with request_id captured
- Response text empty → fail
- Tool calls rejected → fail with the tool name
- Latency > 30s → fail with warning (configurable)
