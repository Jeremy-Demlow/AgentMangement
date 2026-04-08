# REQ-013: Infrastructure as Code (DCM)

## Summary
Snowflake Database Change Management (DCM) project that declaratively defines the AM_SKI_RESORT database, schemas, warehouse, roles, and grants. Replaces manual object creation with version-controlled, environment-aware infrastructure definitions deployed via `snow dcm deploy`.

## Business Context
A CI/CD reference framework must manage its own infrastructure declaratively. Using Snowflake-native DCM (not Terraform) demonstrates best practice for teams already invested in the Snowflake ecosystem. DCM provides drift detection, environment isolation (DEV/QA/PROD via targets), and a proper role hierarchy that replaces the anti-pattern of deploying everything as ACCOUNTADMIN.

## Acceptance Criteria
- [ ] DCM project defines: 1 database, 6 schemas, 1 warehouse, 3 database roles, 2 account roles, 1 stage
- [ ] Three-tier database role hierarchy: ANALYST (read) -> DEVELOPER (DML) -> ADMIN (DDL)
- [ ] Dedicated `AM_DEPLOY_ROLE` account role for CI/CD deployments (replaces ACCOUNTADMIN)
- [ ] `AM_SKI_RESORT_WH_USER` account role for warehouse access (database roles cannot hold warehouse grants)
- [ ] Warehouse definition includes: size, min/max clusters, scaling policy, auto-suspend, statement timeouts
- [ ] Environment-specific warehouse sizing via DCM templating (XSMALL dev, SMALL QA, MEDIUM prod)
- [ ] Grant macros extracted to `sources/macros/grants_macro.sql` (global, reusable)
- [ ] manifest.yml supports DEV/QA/PROD targets with per-environment templating
- [ ] `snow dcm plan` produces clean output (zero errors) for all targets
- [ ] GitHub Action (`dcm-deploy.yml`) supports plan-only and deploy modes with target selection
- [ ] All project config files (environments/*.env.yml, dbt profiles, project.yml) reference DCM-created roles and warehouse
- [ ] Role hierarchy connects cleanly: AM_DEPLOY_ROLE -> SYSADMIN, database roles -> AM_DEPLOY_ROLE

## User Stories
| Story ID | As a... | I want to... | So that... |
|----------|---------|-------------|------------|
| US-030   | DevOps engineer | declarative infrastructure definitions in version control | database objects are reproducible and auditable |
| US-031   | developer | environment-specific warehouse sizing | dev uses minimal compute while prod handles real workloads |
| US-032   | security engineer | a dedicated deploy role instead of ACCOUNTADMIN | the principle of least privilege is enforced in CI/CD |
| US-033   | platform engineer | a GitHub Action that plans before deploying | infrastructure changes are reviewed before applying |

## Dependencies
- REQ-001: Environment Configuration System (env files reference DCM-created roles/warehouse)
- REQ-006: GitHub Actions Workflows (dcm-deploy.yml integrates with existing workflow set)
- REQ-007: dbt Integration (dbt profiles reference DCM-created database/warehouse/role)

## Technical Notes
- DCM projects are registered in Snowflake: `DCM.AM.AM_SKI_RESORT_<ENV>`
- `project_owner` in manifest.yml remains ACCOUNTADMIN (required to CREATE the deploy role initially)
- After first deploy, CI/CD runs as AM_DEPLOY_ROLE for all subsequent operations
- Objects not supported by DEFINE (semantic views, agents, streams) go in post_deploy.sql or CI/CD pipeline
- `snow dcm plan` validates without applying; `snow dcm deploy` applies changes

## File Layout
```
dcm/
  manifest.yml                              # Project manifest with DEV/QA/PROD targets
  sources/
    definitions/
      infrastructure.sql                    # Database, schemas, warehouse, stage
      access.sql                            # Roles, grants, user assignments
    macros/
      grants_macro.sql                      # Reusable schema_read/write/ddl_grants
  post_deploy.sql                           # Reserved for non-DEFINE objects
  output/                                   # Generated bundle (gitignored)
```
