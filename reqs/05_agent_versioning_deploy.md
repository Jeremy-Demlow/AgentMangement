# 05 — Versioned deploy in deploy_agents.py

## Problem (today)

`deploy_agents.py` uses `CREATE OR ALTER AGENT <fqn> … WITH (…)` for every deploy. Each deploy mutates the live spec in place. There is no immutable history; rollback requires storing the previous spec in a snapshot, then re-applying it.

## Goal (target)

When `agent_versioning.enabled=true`, deploys follow the four-step pattern from the Cortex Agent Versioning Private Preview:

```sql
-- 1. Create a new LIVE version seeded from the last committed version
ALTER AGENT <fqn> ADD LIVE VERSION FROM LAST;

-- 2. Overwrite the LIVE version's spec with the new spec
ALTER AGENT <fqn> MODIFY LIVE VERSION SET SPEC FROM '<spec-yaml>';

-- 3. Commit LIVE to a numbered immutable version (VERSION$N)
ALTER AGENT <fqn> COMMIT LIVE VERSION;

-- 4. Point the environment's alias (deploy_alias) at the new version
ALTER AGENT <fqn> MODIFY VERSION LAST SET ALIAS = <deploy_alias>;
```

The `deploy_alias` for each env:

| env | alias |
|-----|-------|
| dev | `latest`   (every dev deploy moves the alias forward) |
| qa  | `validated` (QA moves the alias after eval passes) |
| prod | `production` (prod moves the alias after manual approval) |

## API

```python
def deploy_agent(
    agent_fqn: str,
    spec_path: Path,
    *,
    env: str,
    deploy_alias: str,
    use_versioning: bool,   # from agent_versioning.enabled
    fallback_to_spec_restore: bool = True,
) -> DeployResult

@dataclass
class DeployResult:
    agent_fqn: str
    path: Literal["versioned", "legacy"]
    version_before: str | None   # VERSION$N before
    version_after: str | None    # VERSION$N after
    alias_moved: str | None      # alias that was reassigned
    snapshot_pointer: dict       # for rollback
```

## Fallback logic

If the Cortex Agent Versioning API returns `feature not enabled` / `unknown syntax`, we log a warning, flip `path="legacy"`, and run the current `CREATE OR ALTER AGENT` path. Controlled by `fallback_to_spec_restore=True`.

## Drop policy

Keep last N versions (N=10 default, configurable in `project.yml`):

```sql
ALTER AGENT <fqn> DROP VERSION <n>;
```

Runs after successful commit+alias, skipping any version currently bearing an alias.

## Diagram

See `diagrams/02_deploy_flow_versioned.txt`.
