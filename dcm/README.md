# DCM Project — Snowflake Infrastructure as Code

This directory contains a [Snowflake DCM (Database Change Management)](https://docs.snowflake.com/en/user-guide/dcm-projects/dcm-projects-overview) project that provisions and manages all Snowflake infrastructure for the Agent Management CI/CD reference framework.

## What DCM Manages

DCM owns the **database, schemas, warehouse, roles, grants, and stages**. Everything else (tables, views, agents, semantic views) is created by dbt or deployment scripts that run _after_ DCM.

```
DCM creates this foundation (shown for DEV)
============================================

  AM_SKI_RESORT_DEV (database)
  ├── RAW              Landing zone for ingested data
  ├── STAGING          Type-safe views (dbt staging layer)
  ├── MARTS            Dimensional model (dbt marts layer)
  ├── DOCS             Document storage for Cortex Search
  ├── SEMANTIC         Semantic views for Cortex Analyst
  └── AGENTS           Cortex Agents + eval infrastructure

  AM_DEPLOY_ROLE_DEV          CI/CD deployment role
  AM_SKI_RESORT_WH_USER_DEV  Warehouse usage role
  AM_SKI_RESORT_WH_DEV       Compute warehouse (SMALL, 1-5 clusters)
  EVAL_CONFIG_STAGE           Internal stage for eval config uploads
```

## Deployment Patterns

DCM enforces **single-project ownership** — every Snowflake object (database, role, warehouse) can only belong to one DCM project at a time. This means your deployment pattern depends on whether environments share an account.

### Pattern A — Cross-Account (recommended for production)

Each environment deploys to a **separate Snowflake account**. Object names stay identical (`AM_SKI_RESORT`, `AM_DEPLOY_ROLE`, etc.) because each account is its own namespace.

```
manifest.yml (cross-account)
=============================

targets:
  DEV:
    account_identifier: ACCT_DEV_123        <-- different account per env
    project_name: 'DCM.AM.AM_SKI_RESORT'    <-- same project name everywhere
    templating_config: 'DEV'

  PROD:
    account_identifier: ACCT_PROD_456       <-- different account
    project_name: 'DCM.AM.AM_SKI_RESORT'    <-- same project name
    templating_config: 'PROD'

templating:
  configurations:
    DEV:
      db: 'AM_SKI_RESORT'                   <-- same name, no suffix needed
      deploy_role: 'AM_DEPLOY_ROLE'
      wh_name: 'AM_SKI_RESORT_WH'
    PROD:
      db: 'AM_SKI_RESORT'
      deploy_role: 'AM_DEPLOY_ROLE'
      wh_name: 'AM_SKI_RESORT_WH'
```

### Pattern B — Single-Account (dev/demo, used in this repo)

All environments share **one Snowflake account**. Every account-level object must be env-suffixed to avoid DCM ownership conflicts.

```
manifest.yml (single-account)
==============================

targets:
  DEV:
    account_identifier: TRB65519            <-- same account for all
    project_name: 'DCM.AM.AM_SKI_RESORT_DEV'
    templating_config: 'DEV'

  PROD:
    account_identifier: TRB65519
    project_name: 'DCM.AM.AM_SKI_RESORT'
    templating_config: 'PROD'

templating:
  configurations:
    DEV:
      db: 'AM_SKI_RESORT_DEV'               <-- env suffix on EVERYTHING
      deploy_role: 'AM_DEPLOY_ROLE_DEV'
      wh_name: 'AM_SKI_RESORT_WH_DEV'
      wh_role: 'AM_SKI_RESORT_WH_USER_DEV'
    PROD:
      db: 'AM_SKI_RESORT_PROD'
      deploy_role: 'AM_DEPLOY_ROLE_PROD'
      wh_name: 'AM_SKI_RESORT_WH_PROD'
      wh_role: 'AM_SKI_RESORT_WH_USER_PROD'
```

The `infrastructure.sql` uses `{{db}}` everywhere, so env-suffixed database names flow through automatically — no schema suffixes needed.

## Directory Structure

```
dcm/
├── manifest.yml                        Target definitions (DEV / QA / PROD)
├── sources/
│   ├── definitions/
│   │   ├── infrastructure.sql          Database, schemas, warehouse, stage
│   │   └── access.sql                  Roles, grants, role hierarchy
│   └── macros/
│       └── grants_macro.sql            Reusable Jinja macros for grant patterns
└── post_deploy.sql                     Reserved for post-deploy companion scripts
```

## Targets

Defined in `manifest.yml` (single-account pattern). Each target maps to a registered DCM project:

| Target | Project Name              | Database           | Deploy Role         | Warehouse             |
|--------|---------------------------|--------------------|---------------------|-----------------------|
| DEV    | DCM.AM.AM_SKI_RESORT_DEV  | AM_SKI_RESORT_DEV  | AM_DEPLOY_ROLE_DEV  | AM_SKI_RESORT_WH_DEV  |
| QA     | DCM.AM.AM_SKI_RESORT_QA   | AM_SKI_RESORT_QA   | AM_DEPLOY_ROLE_QA   | AM_SKI_RESORT_WH_QA   |
| PROD   | DCM.AM.AM_SKI_RESORT      | AM_SKI_RESORT_PROD | AM_DEPLOY_ROLE_PROD | AM_SKI_RESORT_WH_PROD |

All warehouses: SMALL, 1-5 clusters, multi-cluster (STANDARD scaling).

## Roles and Access Control

DCM creates **two kinds of roles** for each environment: account-level roles (for warehouse access and CI/CD ownership) and database-level roles (for fine-grained data access).

### Why Two Kinds?

Snowflake database roles **cannot** hold warehouse grants — those require account-level roles. So we need both:

- **Account roles** → warehouse USAGE, CI/CD pipeline ownership
- **Database roles** → schema-level SELECT, INSERT, DDL, Cortex object creation

### Account Roles (one set per environment)

```
+---------------------------+--------------------------------------------------+
| Role                      | Purpose                                          |
+---------------------------+--------------------------------------------------+
| AM_DEPLOY_ROLE_{ENV}      | CI/CD pipeline identity. Owns the DCM project,   |
|                           | runs dbt, deploys agents and semantic views.      |
|                           | Granted to SYSADMIN.                              |
+---------------------------+--------------------------------------------------+
| AM_SKI_RESORT_WH_USER_   | Warehouse USAGE only. Granted to deploy role      |
|   {ENV}                   | and to individual users who need compute.         |
+---------------------------+--------------------------------------------------+
```

### Database Roles (scoped to each environment's database)

```
+---------------------------+--------------------------------------------------+
| Role                      | Purpose                                          |
+---------------------------+--------------------------------------------------+
| {DB}.ADMIN                | Full DDL: CREATE TABLE, VIEW, DYNAMIC TABLE,     |
|                           | STAGE, FUNCTION, PROCEDURE, AGENT, SEMANTIC VIEW, |
|                           | CORTEX SEARCH SERVICE. Plus DML on all schemas.  |
|                           | This is what the CI/CD pipeline uses.             |
+---------------------------+--------------------------------------------------+
| {DB}.DEVELOPER            | DML (INSERT/UPDATE/DELETE) on RAW + STAGING.      |
|                           | Stage READ/WRITE on AGENTS (for eval uploads).    |
|                           | Read-only on all other schemas.                   |
+---------------------------+--------------------------------------------------+
| {DB}.ANALYST              | Read-only SELECT on ALL schemas, including        |
|                           | FUTURE tables and views (so new dbt objects are   |
|                           | immediately queryable).                           |
+---------------------------+--------------------------------------------------+
```

### How They Connect

```
SYSADMIN
  └── AM_DEPLOY_ROLE_{ENV}
        │
        ├── DB ROLE: {DB}.ADMIN
        │     └── DB ROLE: {DB}.DEVELOPER
        │           └── DB ROLE: {DB}.ANALYST
        │
        └── AM_SKI_RESORT_WH_USER_{ENV}
```

Each higher role **inherits** the permissions of the roles below it:
- ADMIN can do everything DEVELOPER and ANALYST can do, plus DDL
- DEVELOPER can do everything ANALYST can do, plus write to RAW/STAGING
- ANALYST is read-only across all schemas

Individual users get `DEVELOPER` + `WH_USER` by default (see the `users` list in manifest.yml).

### Grant Details Per Schema

| Schema   | ANALYST              | DEVELOPER (adds)       | ADMIN (adds)                           |
|----------|----------------------|------------------------|----------------------------------------|
| RAW      | SELECT all + future  | INSERT/UPDATE/DELETE    | CREATE TABLE/VIEW/DT/STAGE/FUNC/PROC  |
| STAGING  | SELECT all + future  | INSERT/UPDATE/DELETE    | CREATE TABLE/VIEW/DT/STAGE/FUNC/PROC  |
| MARTS    | SELECT all + future  | —                      | CREATE TABLE/VIEW/DT/STAGE/FUNC/PROC  |
| DOCS     | SELECT all + future  | —                      | + CREATE CORTEX SEARCH SERVICE         |
| SEMANTIC | SELECT all + future  | —                      | + CREATE SEMANTIC VIEW + AGENT         |
| AGENTS   | SELECT all + future  | Stage READ/WRITE       | + CREATE AGENT + CORTEX SEARCH SVC     |

**FUTURE grants** on tables and views mean that when dbt creates new objects, they are immediately queryable by ANALYST without any manual grant.

### Grant Macros

Four reusable Jinja macros in `sources/macros/grants_macro.sql` keep `access.sql` DRY:

| Macro | What It Grants |
|-------|----------------|
| `schema_read_grants(db, schema, role)` | USAGE + SELECT on all/future tables and views |
| `schema_write_grants(db, schema, role)` | INSERT/UPDATE/DELETE on all/future tables |
| `schema_ddl_grants(db, schema, role)` | CREATE TABLE/VIEW/DT/STAGE/FUNCTION/PROCEDURE/AGENT/SEMANTIC VIEW/CORTEX SEARCH SERVICE |
| `schema_stage_write_grants(db, schema, role)` | READ/WRITE on all/future stages |

## CI/CD Workflow

The GitHub Actions workflow (`.github/workflows/dcm-deploy.yml`) uses the official [Snowflake-Labs reusable DCM actions](https://github.com/Snowflake-Labs/snowflake_dcm_projects/tree/main/actions):

| Trigger | Behavior |
|---------|----------|
| **PR to main** | Runs `dcm-plan` on DEV, posts changeset as PR comment |
| **Push to main** | Runs `dcm-plan` + `dcm-deploy` on DEV (drops blocked by default) |
| **Manual dispatch** | Pick target (DEV/QA/PROD), plan-only or plan+deploy |

Authentication uses key-pair (SNOWFLAKE_JWT) via repository secrets. OIDC is recommended for production — see the [Actions README](https://github.com/Snowflake-Labs/snowflake_dcm_projects/blob/main/actions/README.md).

## Local Usage

```bash
cd dcm

snow dcm plan --target DEV -c myconnection

snow dcm deploy --target DEV -c myconnection --alias "my-change"

snow dcm create DCM.AM.AM_SKI_RESORT_DEV --if-not-exists -c myconnection
```

**Note:** Requires Snowflake CLI 3.16+. Earlier versions have a bundling bug where only `manifest.yml` is uploaded to the temp stage, missing the `sources/` directory.

## What DCM Does NOT Manage

These objects are created by other pipeline stages that run after DCM:

| Object Type | Created By |
|-------------|-----------|
| Tables, views, dynamic tables | dbt (`dbt run`) |
| Semantic views | dbt semantic_view materialization or `deploy_semantic_views.py` |
| Cortex Agents | `deploy_agents.py` (ALTER AGENT / CREATE AGENT) |
| Cortex Search Services | `data_generation/` scripts |
| UDFs / Stored Procedures | Deployment scripts |
| Raw data | `data_generation/` scripts |

DCM creates the roles and grants that _allow_ all of the above to succeed.

## Gotchas

- **`snow dcm drop` does NOT drop objects** — it only removes the project registration. You must manually `DROP ROLE/WAREHOUSE/DATABASE IF EXISTS` for cleanup.
- **Alias uniqueness** — each deploy alias must be unique per project. If a previous deploy (even a failed one) consumed an alias, use a new one.
- **CLI 3.16+ required** — 3.13.0 has a bundling bug; the Homebrew formula for 3.16.0 may also be broken (missing pydantic). Install via pip if needed: `pip install snowflake-cli==3.16.0`.
