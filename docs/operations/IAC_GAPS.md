# IaC Gaps — things that are NOT currently in code

Living inventory of manual steps that had to be performed during the teardown/rebuild exercise. Each entry lists the current workaround and the proposed codification.

## 1. Snowflake user -> role grants post-DCM

**Gap**: DCM creates the roles (`AM_DEPLOY_ROLE`, `AM_DEPLOY_ROLE_DEV`, `AM_SKI_RESORT_WH_USER`, `AM_SKI_RESORT_WH_USER_DEV`), but DCM does NOT grant them to users. Without this grant, `USE ROLE AM_DEPLOY_ROLE` fails for CI and for personal developer use.

**Current workaround**: manual `GRANT ROLE <role> TO USER <user>` after each DCM deploy (captured in `scripts/grant_roles_to_users.sql` during the rebuild).

**Impact**: Forgetting this step is exactly how the MCP_OPERATOR silent-fallback bug hid for multiple PRs.

**Proposed fix**: add a post-deploy step to DCM project (`post_deploy.sql`) that grants the created roles to a configured list of users. User list should come from `environments/<env>.env.yml` under a new `access.users` key (e.g. `[JD_SERVICE_ACCOUNT_ADMIN, JDEMLOW]`). Alternative: Terraform module for user/role/grant relationships.

**Tracking**: issue TBD

## 2. GitHub Environment secrets

**Gap**: The `scripts/bootstrap_gh_environments.py` script sets environment variables but NOT secrets. The `SNOWFLAKE_PRIVATE_KEY` secret (repo-level), `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, etc. must be set manually via `gh secret set` or the GH UI.

**Current workaround**: document the required secrets in `BOOTSTRAP.md`; set manually on initial repo setup.

**Proposed fix**: either integrate with a secret manager (1Password CLI, AWS Secrets Manager) or accept that secrets stay manual and codify only their NAMES + required scope. Script could validate that required secrets exist (without reading their values) and fail loudly if missing.

**Tracking**: issue TBD

## 3. Snowflake user creation + key-pair auth

**Gap**: If the CI service user (`JD_SERVICE_ACCOUNT_ADMIN`) needs to be recreated or rotated, there's no codified procedure for:
  - Creating the user
  - Attaching a public key (`ALTER USER ... SET RSA_PUBLIC_KEY = '...'`)
  - Setting `DEFAULT_ROLE` to something safe like `PUBLIC` (NOT letting it default to a role with privileges)

**Current workaround**: users exist from a prior setup step; not touched during this teardown because the exercise was about recreating databases/roles, not users.

**Proposed fix**: Terraform module for user management, OR a documented `snow sql` bootstrap script committed to the repo that takes a public key path as input.

**Tracking**: issue TBD

## 4. User DEFAULT_ROLE hygiene

**Gap**: `JDEMLOW` has `DEFAULT_ROLE = MCP_OPERATOR`. This caused the silent-fallback bug that took multiple PRs to diagnose. The fix (PR #30, `SnowflakeConfig`) makes client code never rely on DEFAULT_ROLE — but the underlying hygiene issue remains: a personal user's DEFAULT_ROLE should probably be `PUBLIC` to force every tool to set role explicitly.

**Current workaround**: library-level enforcement via `SnowflakeConfig.resolve()` raising `ConfigError` if role is unresolved. This means no script can silently inherit DEFAULT_ROLE even if the user account still has one.

**Proposed fix**: none strictly needed in code; document as operational guidance in `BOOTSTRAP.md` ("set all users' DEFAULT_ROLE to PUBLIC"). Optionally add a pre-deploy check that warns if CI user's DEFAULT_ROLE is anything other than PUBLIC/NULL.

**Tracking**: issue TBD

## 5. DCM role-template variable naming

**Gap**: `dcm/sources/definitions/access.sql` uses `{{wh_role}}` template variable; actual created role name is `AM_SKI_RESORT_WH_USER` (not `_ROLE`). Anyone reading the code has to trace the templating config to find the real role name.

**Current workaround**: noted in teardown plan; worked around by matching live names during teardown.

**Proposed fix**: rename the template variable to `{{wh_user_role}}` or rename the created role to `AM_SKI_RESORT_WH_ROLE` — whichever matches the team's convention. Pick one and be consistent.

**Tracking**: issue TBD

## 6. Agent eval data table ownership (if not using SnowflakeConfig)

**Gap**: `RESORT_EXECUTIVE_EVAL_DATA` and `SKI_OPS_ASSISTANT_EVAL_DATA` tables are created ad-hoc by the first eval run. Ownership defaults to whichever role ran the first create. If a later run uses a different role, `CREATE OR REPLACE TABLE` fails with "Insufficient privileges to operate on schema" because drop requires ownership.

**Current status**: with PR #30 (`SnowflakeConfig` enforces explicit role), this shouldn't recur — every eval run uses the same `AM_DEPLOY_ROLE`. But if someone bypasses `SnowflakeConfig` this could regress.

**Proposed fix**: make the eval config's `snowflake_table` target a schema that only `AM_DEPLOY_ROLE` can write to (DCM-enforced), OR add a post-DCM step that ensures any existing eval tables are owned by `AM_DEPLOY_ROLE`.

**Tracking**: issue TBD

---

When this document stops growing, the infra is fully codified.

## 7. sync_env_data workflow doesn't bootstrap fresh envs

**Gap**: `sync_env_data.yml` uses `INSERT INTO <target>` which requires target
tables to exist. After a teardown, DEV has zero tables in RAW, so the workflow
fails on first run with "Table ... does not exist or not authorized".

**Current workaround**: run `generate_complete_ski_data.py` directly against
each target env to bootstrap, then `sync_env_data` handles subsequent refreshes.

**Proposed fix**: make the sync step a `CREATE OR REPLACE TABLE <target> AS
SELECT ... FROM <source>` instead of TRUNCATE + INSERT. Idempotent, handles
bootstrap, slightly heavier but DEV sync runs rarely.

## 8. Snowflake SV Optimization object requires warm-up after DROP/CREATE

**Gap**: `EXECUTE_AI_EVALUATION(sv_name, ...)` depends on a
`<schema>.SYSTEM_AI_OBS_ANALYST_EVAL_<sv_name>` optimization object. After
DROP + CREATE of a semantic view, this object is missing and all SV eval
runs fail with:

```
Semantic View Optimization 'AM_SKI_RESORT_DEV.SEMANTIC.SYSTEM_AI_OBS_ANALYST_EVAL_<sv>' does not exist or not authorized.
```

**Impact**: blocks SV Evaluation Gate in CI after any full rebuild. Also
appears to block agent evaluations that route to `cortex_analyst` tool.

**Current workaround**: wait or poke via a simple Cortex Analyst REST call
per SV; Snowflake's AI Observability service eventually auto-creates the
object. Needs more testing to find a reliable trigger.

**Proposed fix**: add a post-SV-deploy step that either
(a) warm-pings each SV via a single `POST /api/v2/cortex/analyst/message`
    call (Snowflake creates the AI OBS object on first query), or
(b) polls `SHOW SEMANTIC VIEWS` with a post-condition that the OBS object
    exists before proceeding to SV Eval Gate.

## 9. Agent smoke test is flaky on first deploy

**Gap**: Immediately after `deploy_agents.py` creates agents, the first
smoke test query gets `HTTP 500 INTERNAL_ERROR` with no details. Second
call usually succeeds.

**Proposed fix**: already have a 2-attempt retry on the eval step (PR #29).
Same pattern for smoke test: 2 attempts with a 30s gap.
