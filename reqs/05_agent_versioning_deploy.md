# 05 — Versioned deploy in deploy_agents.py

## Problem (today)

`deploy_agents.py` uses `CREATE OR ALTER AGENT <fqn> … WITH (…)` for every deploy. Each deploy mutates the live spec in place. There is no immutable history; rollback requires storing the previous spec in a snapshot, then re-applying it.

## Goal (target — single code path)

Deploys follow the four-step pattern from the Cortex Agent Versioning Private Preview. This is the **only** code path; there is no legacy fallback.

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

The `deploy_alias` for each env (2-env model):

| env | alias |
|-----|-------|
| dev | `latest` — every dev deploy moves the alias forward |
| prod | `validated` — main-merge deploys move this alias; approval flips `production` |

The `production` alias is only ever moved by the `promote-validated-to-production` workflow.

## API

```python
def deploy_agent(
    agent_fqn: str,
    spec_path: Path,
    *,
    env: str,
    deploy_alias: str,
) -> DeployResult

@dataclass
class DeployResult:
    agent_fqn: str
    env: str
    version_before: str | None   # VERSION$N before
    version_after: str           # VERSION$N after (always set on success)
    alias_moved: str             # the alias that was reassigned
    snapshot_pointer_path: Path  # for rollback
```

No `use_versioning`. No `fallback_to_spec_restore`. If the SQL fails, the exception propagates.

## Drop policy

Keep last N versions (N=10 default, configurable in `project.yml`):

```sql
ALTER AGENT <fqn> DROP VERSION <n>;
```

Runs after successful commit+alias. Skips any version currently bearing any alias.

## Diagram

See `diagrams/02_deploy_flow_versioned.txt`.
