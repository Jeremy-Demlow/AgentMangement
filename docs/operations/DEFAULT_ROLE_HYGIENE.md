# DEFAULT_ROLE Hygiene

## The bug that motivated this doc

During session 26 of the Agent Management project, an eval run silently succeeded against tables owned by `MCP_OPERATOR` because `JDEMLOW`'s `DEFAULT_ROLE` was set to `MCP_OPERATOR`. Multiple scripts called `connect()` without passing `role=`, which silently inherited `MCP_OPERATOR`. Result: evaluations ran with unexpected privileges, tables were created in the wrong schema with the wrong owner, and the root cause took several PRs and a teardown+rebuild to diagnose.

## The guarantee

All Snowflake clients used by this repository MUST NOT silently inherit a user's `DEFAULT_ROLE`. Role resolution is enforced through `agent_management.snowflake_config.SnowflakeConfig.resolve()` which raises `ConfigError` if role is unresolved from explicit kwargs / env vars / `environments/*.env.yml`.

As of PR #30 this is enforced in code. This doc captures the operational guidance to avoid bringing back the bug from the Snowflake side.

## Operational rules

1. **Service accounts (`JD_SERVICE_ACCOUNT_ADMIN`) should have `DEFAULT_ROLE = PUBLIC`** (or `NULL`). Never let a service account default to a role with any privileges — CI must always pass `role=` explicitly.
2. **Personal accounts (`JDEMLOW`) should have `DEFAULT_ROLE = PUBLIC`** or a safely-scoped role that would make any accidental inheritance *obvious* rather than silent. Never set `DEFAULT_ROLE` to a role that owns sensitive production objects.
3. **Every script that calls `snowflake.connector.connect()` MUST import and use `SnowflakeConfig.resolve()`** — never call `connect()` with just user+password/key and expect a useful role.
4. **Every CI workflow sets `SNOWFLAKE_ROLE` as an environment variable** (from the GH Environment's `vars`). Workflows that call Python code that builds a connection rely on `SnowflakeConfig` picking up the env var.

## Verification

```sql
-- Check default roles of users you care about:
SHOW USERS LIKE 'JD%';
-- Look for the "default_role" column. Should be PUBLIC or NULL for
-- service accounts and ideally for personal accounts too.

-- If not, fix with:
ALTER USER JD_SERVICE_ACCOUNT_ADMIN SET DEFAULT_ROLE = PUBLIC;
```

## Why we don't enforce this via DCM

DCM runs as a single role (`ACCOUNTADMIN` in our setup). `ALTER USER ... SET DEFAULT_ROLE` requires `MANAGE GRANTS` and is an account-level concern unrelated to database infrastructure. Putting it in DCM would couple unrelated concerns and make DCM harder to reason about. Instead we rely on:

- Library enforcement (`SnowflakeConfig.resolve()` — always fails if no role)
- This doc + new-user onboarding runbook
- Periodic audit query (TODO: add to `scripts/` as `audit_default_roles.py`)
