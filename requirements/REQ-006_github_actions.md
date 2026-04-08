# REQ-006: GitHub Actions Workflows

## Summary
Five CI/CD workflows covering the full lifecycle: validate PRs, deploy to dev on merge, promote to QA and prod with evaluation gates, and rollback any environment to a prior state.

## Business Context
The scripts from REQ-001 through REQ-005 provide the building blocks. GitHub Actions workflows orchestrate them into an automated pipeline where every change is validated, deployed, evaluated, and promotable — with guardrails at every stage. This is the connective tissue that turns config-as-code into a reliable, repeatable deployment process.

## Acceptance Criteria
- [ ] `validate-pr.yml`: triggers on PR to main; lints YAML, validates agent and SV specs (dry-run), compiles dbt (if present)
- [ ] `deploy-dev.yml`: triggers on push to main; snapshots current dev state -> dbt build (conditional) -> deploy SVs -> deploy agents -> run eval (warning only, does not block)
- [ ] `promote-qa.yml`: manual trigger via `workflow_dispatch`; snapshots QA state -> deploy -> eval gate (blocks on failure)
- [ ] `promote-prod.yml`: manual trigger with GitHub environment approval; snapshots prod state -> deploy -> eval gate -> auto-rollback on failure
- [ ] `rollback.yml`: manual trigger with inputs for environment, target (agents/semantic-views/both), and snapshot timestamp
- [ ] All workflows use key-pair auth via GitHub Secrets (no passwords in CI)
- [ ] Eval results uploaded as GitHub Actions artifacts with appropriate retention (30d PR, 90d staging, 365d prod)
- [ ] Workflow YAML passes `actionlint` validation

## User Stories
| Story ID | As a... | I want to... | So that... |
|----------|---------|-------------|------------|
| US-016   | developer | PR validation that lints and dry-run validates specs | broken specs never merge to main |
| US-017   | DevOps engineer | automated dev deploy on merge to main | the dev environment always reflects the latest main branch |
| US-018   | DevOps engineer | manual promotion with eval gates for QA and prod | environment changes are deliberate and quality-validated |
| US-019   | operator | a rollback workflow triggered from the GitHub UI | I can restore any environment without SSH or CLI access |

## Dependencies
- REQ-001: Environment Configuration System (workflows pass `--env` to all scripts)
- REQ-002: Semantic View CI/CD Pipeline (`deploy_semantic_views.py`)
- REQ-003: Agent CI/CD Pipeline (`deploy_agents.py`)
- REQ-004: Evaluation Framework (`run_eval.py`, `compute_metrics.py`)
- REQ-005: Snapshot and Rollback (`snapshot_state.py`, `rollback.py`)

## Out of Scope
- Self-hosted GitHub Actions runners (uses ubuntu-latest)
- Slack/Teams notifications on deploy success/failure (can be added as enhancement)
- Scheduled evaluation runs via GitHub Actions cron (manual or deploy-triggered only)
- Multi-repo orchestration (single repo pipeline)

## Notes
- Key-pair auth: `SNOWFLAKE_PRIVATE_KEY` secret contains RSA private key content
- GitHub environment protection rules used for prod approval gate
- Conditional dbt steps: `if: hashFiles('dbt/dbt_project.yml') != ''`
- Eval in dev is warning-only (does not block); eval in QA/prod blocks promotion
- Prod auto-rollback: on eval failure, workflow calls `rollback.py` with the pre-deploy snapshot
- Adapted from existing workflows in SnowflakeAgentDevelopmentManagement
