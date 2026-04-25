# Cortex Agent Versioning

This repository uses **Cortex Agent Versioning** (Snowflake Private Preview) for
all agent deploys and rollbacks. This document describes the actual DDL and
REST behavior as verified against Snowflake 10.14.103 (April 2026).

## Concepts

| Term | Meaning |
|------|---------|
| `VERSION$N` | An immutable, numbered snapshot of an agent's spec inside Snowflake. Created by `ALTER AGENT ... COMMIT`. Once created, never mutated. |
| `LIVE` | The editable draft. You modify LIVE, then COMMIT to seal it into a new `VERSION$N`. |
| alias | A named pointer that routes requests. System aliases: `FIRST`, `LAST`, `DEFAULT`, `LATEST`. User aliases: `validated`, `production`, etc. User aliases are stored **uppercase** by the server. |

### Each version holds at most ONE user alias

**Important semantic**: `ALTER AGENT ... MODIFY VERSION <v> SET ALIAS = <name>`
moves the named alias to `<v>` **and** replaces whatever alias was previously
on `<v>`. You cannot have `validated` and `production` on the same version
simultaneously.

This shapes the promotion flow: when we promote, `validated` is effectively
consumed — it disappears until the next main-merge re-creates it on a new
committed version.

```
before deploy 2:  V$1 = (none)   V$2 = VALIDATED   V$3 = PRODUCTION
main-merge N+1:   deploy commits V$4, SET validated=V$4:
                  V$1 = (none)   V$2 = (none)   V$3 = PRODUCTION   V$4 = VALIDATED
promote:          SET production=V$4 (the version under VALIDATED):
                  V$1 = (none)   V$2 = (none)   V$3 = (none)   V$4 = PRODUCTION
                  (VALIDATED disappears until the next main-merge recreates it)
```

### Version pruning is NOT supported

`ALTER AGENT ... DROP VERSION VERSION$N` fails with *"Version cannot be
dropped if it is a base for another version"*. Since `ADD LIVE VERSION
FROM LAST` creates a linear chain, every version except the tip is a base
for the next. In practice, **version history accumulates indefinitely** —
this is a feature (permanent audit trail), not a bug. `project.yml`'s
`keep_last_n_versions` is informational only.

## DDL reference (verified)

```sql
-- Create agent (first time). This auto-creates an empty VERSION$1 and a
-- LIVE draft. Don't call ADD LIVE after this; jump straight to MODIFY LIVE.
CREATE AGENT IF NOT EXISTS <fqn> [COMMENT = '...'] [PROFILE = '<json>'];

-- Seed a fresh LIVE draft from the most recent committed version.
-- Fails if a LIVE already exists.
ALTER AGENT <fqn> ADD LIVE VERSION FROM LAST;

-- Overwrite the LIVE spec. Multi-line YAML goes between $$...$$.
ALTER AGENT <fqn> MODIFY LIVE VERSION SET SPECIFICATION = $$
<yaml>
$$;

-- Commit LIVE into a new VERSION$N+1. "LIVE VERSION" is NOT in the syntax.
ALTER AGENT <fqn> COMMIT;

-- Move (or create) an alias. Atomic. Target version's prior user alias
-- is replaced. Reserved alias names: FIRST, LAST, LIVE, DEFAULT.
ALTER AGENT <fqn> MODIFY VERSION <VERSION$N> SET ALIAS = <user_alias>;

-- Inspect.
SHOW VERSIONS IN AGENT <fqn>;
DESC AGENT <fqn>;  -- returns `aliases` as a JSON dict
```

## Deploy (single path)

The library emits this sequence on every deploy. `seed_from_last=False` is
used only when the agent was just created (CREATE AGENT already made an empty
LIVE draft).

```python
if first_time_create:
    CREATE AGENT IF NOT EXISTS ...    # auto-creates VERSION$1 + empty LIVE
    MODIFY LIVE VERSION SET SPECIFICATION = $$<yaml>$$
    COMMIT                             # creates VERSION$2
    SET ALIAS = latest on VERSION$2
else:
    ADD LIVE VERSION FROM LAST         # seed LIVE from the latest committed
    MODIFY LIVE VERSION SET SPECIFICATION = $$<yaml>$$
    COMMIT                             # creates VERSION$N+1
    SET ALIAS = <deploy_alias> on VERSION$N+1
```

## Rollback (one statement)

```sql
ALTER AGENT <fqn> MODIFY VERSION <target> SET ALIAS = <alias>;
```

Target comes from the last snapshot pointer (`snapshot_state.py`), or the
operator can supply `--to VERSION$N`.

## REST invocation (verified)

Agent chat is REST-only. There is no SQL function. Version / alias routing
is via a URL path segment:

```
POST https://<org>-<account>.snowflakecomputing.com
     /api/v2/databases/<db>/schemas/<schema>/agents/<name>/versions/<selector>:run
```

`<selector>` is one of:

- a user alias in **uppercase** (`LATEST`, `VALIDATED`, `PRODUCTION`)
- a reserved alias (`DEFAULT`, `FIRST`, `LAST`)
- a URL-encoded `VERSION$N` (use `VERSION%24N`)

Omit the `/versions/<selector>` segment to hit the DEFAULT alias (= most
recent committed version):

```
POST .../agents/<name>:run
```

This is the path `agent_management.smoke_test` uses.

## Version identity: "what is VERSION$5?"

`VERSION$N` is opaque on its own. The library answers the identity question
two ways:

### 1. Comment pinned to the version (from SHOW VERSIONS)

Every deploy sets a one-line comment on the new version:

```
<short-sha>[ PR#<n>] <env> <iso-ts> by <actor>: <agent_name>: <one-line-summary>
```

Example:

```
77ace7c PR#19 prod 2026-04-24T23:49Z by jdemlow: resort_executive: Comprehensive BI partner
```

This shows up directly in `SHOW VERSIONS IN AGENT` and in the library's
`versioning list` command — no external lookup needed for basic identification.

### 2. Audit table (CORTEX_AGENT_VERSION_LOG)

Each deploy and rollback also appends a structured row to
``<db>.<agents_schema>.CORTEX_AGENT_VERSION_LOG``:

| column | meaning |
|--------|---------|
| `event_ts` | When the deploy ran |
| `agent_fqn` | Agent that was deployed |
| `version_name` | `VERSION$N` that was created or re-aliased |
| `alias_set` | Alias moved by this event (latest/validated/production) |
| `git_sha` | Full 40-char commit SHA |
| `git_ref` | Branch or tag name |
| `pr_number` | GitHub PR number if run under a PR |
| `actor` | GitHub actor or local user |
| `env` | dev / prod |
| `first_deploy` | True if this was the agent's first commit |
| `version_before` | Previous version that alias pointed at |
| `spec_summary` | Short hint from the spec (or "ROLLBACK: …" for rollback events) |
| `extra` | VARIANT for ad-hoc metadata (tool_count, event_type, eval scores, etc.) |

The table is append-only; rollbacks add new rows rather than editing old ones.

### 3. CLI

```
python -m agent_management.versioning log --env prod --agent resort_executive --limit 20
```

Renders the most recent deploy/rollback events plus the current version
state with comments. Full history is queryable as a normal Snowflake table:

```sql
SELECT *
FROM AM_SKI_RESORT.AGENTS.CORTEX_AGENT_VERSION_LOG
WHERE agent_fqn = 'AM_SKI_RESORT.AGENTS.RESORT_EXECUTIVE'
  AND event_ts > CURRENT_TIMESTAMP - INTERVAL '30 days'
ORDER BY event_ts DESC;
```

### Rich snapshots

For full spec capture (audit/forensics), use
`agent_management.snapshot_agent` — it writes the complete spec + metadata
to a local JSON file. Distinct from the lightweight `snapshot_state` pointer
that rollback reads.



## Alias routing in evals

**Important limitation (verified live):** `EXECUTE_AI_EVALUATION` does NOT
accept `!alias` or `!VERSION$N` in `agent_name`. Attempting it returns
*"Cortex Agent 'DB.SCHEMA.\"NAME!LATEST\"' does not exist or not authorized"*.

Eval always targets the **default version** (= most recent committed). This
is usually fine: right after `deploy_agents` commits a new version, that
version IS the default. So evaluating "validated" is equivalent to
evaluating the default until another deploy shifts default forward.

```bash
# CI invocations. The selector is informational for logging; the SP ignores it.
python -m agent_management.run_ci_eval --env prod --alias validated
python -m agent_management.run_ci_eval --env prod --alias production
```

`run_eval.py` prints a warning when `--alias` or `--version` is supplied so
it's clear the eval SP won't honor it. Smoke tests (`smoke_test.py`) DO
support version/alias selectors — only the eval SP is limited.

## Env → alias matrix (Option B)

| env | deploy_alias | aliases this env manages |
|-----|--------------|-------------------------|
| `dev` | `latest` | `latest` |
| `prod` | `validated` | `validated`, `production` |

`production` is moved only by `promote-validated-to-production.yml`, behind
the GitHub `production-promote` environment's required-reviewer gate.
