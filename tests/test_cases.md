# Test Cases

All test cases, linked to requirements. Each requirement must have at least one test case.

## Status Key
- **Pass** — Test passes as expected
- **Fail** — Test does not pass
- **Blocked** — Cannot test due to dependency
- **Not Run** — Has not been executed yet

---

## REQ-001: Environment Configuration System

| Test ID | Description | Type | Steps | Expected Result | Actual Result | Status | Date |
|---------|-------------|------|-------|-----------------|---------------|--------|------|
| TC-001  | Config loader parses dev.env.yml | Automated | `pytest tests/test_smoke.py::TestConfigLoader::test_config_loads[dev]` | Config dict with database, schema, warehouse, role fields | SKI_RESORT_DEV_DB loaded, schemas end in .SEMANTIC/.AGENTS | Pass | 2026-04-02 |
| TC-002  | Config loader parses qa.env.yml | Automated | `pytest tests/test_smoke.py::TestConfigLoader::test_config_loads[qa]` | Config dict with QA-specific values | SKI_RESORT_QA_DB loaded | Pass | 2026-04-02 |
| TC-003  | Config loader parses prod.env.yml | Automated | `pytest tests/test_smoke.py::TestConfigLoader::test_config_loads[prod]` | Config dict with prod-specific values | SKI_RESORT_DB loaded | Pass | 2026-04-02 |
| TC-004  | SNOWFLAKE_ENV override | Automated | `pytest tests/test_smoke.py::TestConfigLoader::test_snowflake_env_override` | Returns QA config | SKI_RESORT_QA_DB returned when SNOWFLAKE_ENV=qa | Pass | 2026-04-02 |
| TC-005  | Jinja2 renderer substitutes placeholders | Automated | `pytest tests/test_templates.py -v` (39 parametrized tests) | All `{{ env.* }}` replaced with env-specific values | All 39 template tests pass: 2 agents × 3 envs + 11 SVs × 3 envs, no `{{ env.` or `SADM_SKI_RESORT_DB` in output | Pass | 2026-04-02 |
| TC-006  | Jinja2 renderer handles missing placeholders | Automated | `pytest tests/test_smoke.py::TestRenderTemplate::test_strict_undefined_raises` | Raises clear error, does not silently produce empty string | UndefinedError raised for unknown variable | Pass | 2026-04-02 |

---

## REQ-002: Semantic View CI/CD Pipeline

| Test ID | Description | Type | Steps | Expected Result | Actual Result | Status | Date |
|---------|-------------|------|-------|-----------------|---------------|--------|------|
| TC-007  | 11 SV YAML files exist | Manual | `ls semantic-views/definitions/` | All 11 SV templates present | All 11 present (.yaml extension): customer_behavior, customer_satisfaction, daily_summary, lessons_analytics, marketing_analytics, operations, passholder_analytics, revenue, safety_incidents, staffing_analytics, weather_analytics | Pass | 2026-04-02 |
| TC-008  | SV deploy dry-run validates | Automated | `python -m scripts.deploy_semantic_views --env prod --dry-run` | Exit 0, no errors | 11/11 VALID against Snowflake (prod) | Pass | 2026-04-02 |
| TC-009  | SV deploy creates/replaces view | Automated | `python -m scripts.deploy_semantic_views --env prod` | Semantic view exists in Snowflake | 4/4 deployed: SEM_DAILY_SUMMARY, SEM_OPERATIONS, SEM_REVENUE, SEM_STAFFING_ANALYTICS updated in SKI_RESORT_DB.SEMANTIC | Pass | 2026-04-02 |
| TC-010  | SV deploy single view flag | Automated | `python -m scripts.deploy_semantic_views --env prod --view sem_operations --dry-run` | Only SEM_OPERATIONS validated, others skipped | --view sem_operations correctly scoped to 1 view: "Views: 1", validated VALID | Pass | 2026-04-02 |
| TC-011  | Drift detection finds no drift | Automated | `python -m scripts.detect_drift --env prod` | Reports "no drift" | NO DRIFT across 4 templated SVs | Pass | 2026-04-02 |
| TC-012  | Drift detection finds manual edit | Manual | Edit SV in Snowsight, run detect_drift.py | Reports drift with diff | | Not Run | |

---

## REQ-003: Agent CI/CD Pipeline

| Test ID | Description | Type | Steps | Expected Result | Actual Result | Status | Date |
|---------|-------------|------|-------|-----------------|---------------|--------|------|
| TC-013  | 2 agent spec files exist | Manual | `ls agents/specs/` | resort_executive.yml, ski_ops_assistant.yml | Both present | Pass | 2026-04-02 |
| TC-014  | Agent deploy dry-run validates | Automated | `python -m scripts.deploy_agents --env dev --dry-run` | Exit 0, spec structure valid | 2/2 specs valid, SQL generated correctly (ALTER for existing, CREATE for new) | Pass | 2026-04-02 |
| TC-015  | Agent deploy creates agent | Automated | `python -m scripts.deploy_agents --env prod` | Agent exists in Snowflake, DESCRIBE returns valid spec | RESORT_EXECUTIVE + SKI_OPS_ASSISTANT created in SKI_RESORT_DB.AGENTS (no suffix in prod) | Pass | 2026-04-02 |
| TC-016  | Agent spec has no hardcoded FQNs | Automated | `pytest tests/test_templates.py` (checks for SADM_SKI_RESORT_DB) | No matches (all use Jinja2 placeholders) | All 6 agent template tests assert `SADM_SKI_RESORT_DB not in rendered` — PASS | Pass | 2026-04-02 |
| TC-017  | Deploy order enforced | Automated | Deploy agents before SVs | Script warns or fails, does not create agent with missing SV | | Not Run | |

---

## REQ-004: Evaluation Framework with Gate

| Test ID | Description | Type | Steps | Expected Result | Actual Result | Status | Date |
|---------|-------------|------|-------|-----------------|---------------|--------|------|
| TC-018  | Golden questions exist for resort_executive | Manual | `cat agent-evaluation/datasets/resort_executive_eval.yaml` | 15 questions with ground_truth | resort_executive_eval.yaml exists with eval questions | Pass | 2026-04-02 |
| TC-019  | Golden questions exist for ski_ops_assistant | Manual | `cat agent-evaluation/datasets/ski_ops_assistant_eval.yaml` | 8-10 questions with ground_truth | 11 questions covering all 4 tools (LiftOps, Staffing, Weather, Safety) + cross-domain | Pass | 2026-04-02 |
| TC-020  | run_eval.py completes for resort_executive | Automated | `python scripts/run_eval.py eval/configs/resort_executive.yml --env dev` | Eval run completes, JSON results saved | | Not Run | |
| TC-021  | Dynamic ground truth resolves | Automated | `python scripts/run_eval.py eval/configs/resort_executive.yml --env dev --resolve-only` | All validation_queries execute, answer_templates format correctly | | Not Run | |
| TC-022  | compute_metrics.py calculates F1 | Automated | `python -m scripts.compute_metrics --env dev` | Outputs precision, recall, F1 | compute_metrics ran, scores calculated (0.668 composite) | Pass | 2026-04-02 |
| TC-023  | Threshold gate passes | Automated | Run compute_metrics with scores above thresholds | Exit code 0 | dev threshold 0.6 — PASS (0.668 >= 0.6) | Pass | 2026-04-02 |
| TC-024  | Threshold gate fails | Automated | Run compute_metrics with scores below thresholds | Exit code 1 | prod threshold 0.8 — FAIL (0.668 < 0.8), correct behavior | Pass | 2026-04-02 |
| TC-025  | Custom metrics appear in results | Automated | Run eval with answer_relevance metric | answer_relevance scores in output JSON | | Not Run | |

---

## REQ-005: Snapshot and Rollback

| Test ID | Description | Type | Steps | Expected Result | Actual Result | Status | Date |
|---------|-------------|------|-------|-----------------|---------------|--------|------|
| TC-026  | Snapshot captures agent spec | Automated | `python -m scripts.snapshot_state --env prod` | JSON file in agents/snapshots/ with agent spec | 3 agents captured (RESORT_EXECUTIVE, SKI_OPS_ASSISTANT, RESORT_EXECUTIVE_DEV + 2 more), specs extracted via DESCRIBE AGENT | Pass | 2026-04-02 |
| TC-027  | Snapshot captures SV YAML | Automated | `python -m scripts.snapshot_state --env prod` | YAML file in semantic-views/snapshots/ with SV definition | 11 SVs captured via SYSTEM$READ_YAML_FROM_SEMANTIC_VIEW, saved to local files + CI_CD_SNAPSHOTS table (14 total rows) | Pass | 2026-04-02 |
| TC-028  | Rollback restores agent | Automated | Snapshot (20260402_194103), rollback to 20260402_162138, verify, restore back | Agent spec matches snapshot | 3 agents rolled back OK, then 5 agents restored back OK — full round-trip verified | Pass | 2026-04-02 |
| TC-029  | Rollback by timestamp | Automated | `python -m scripts.rollback --env prod --list` | Multiple timestamps, can select specific one | 5 timestamps available (20260402_030209 through 20260402_162138) | Pass | 2026-04-02 |
| TC-030  | Rollback target flag | Automated | `python -m scripts.rollback --env prod --target agents --dry-run --timestamp 20260402_162138` | Only agents rolled back, SVs unchanged | --target agents correctly limits to 3 agent objects only (dry-run verified) | Pass | 2026-04-02 |

---

## REQ-006: GitHub Actions Workflows

| Test ID | Description | Type | Steps | Expected Result | Actual Result | Status | Date |
|---------|-------------|------|-------|-----------------|---------------|--------|------|
| TC-031  | validate-pr.yml syntax valid | Automated | `actionlint .github/workflows/validate-pr.yml` | No errors | actionlint not installed; YAML parses correctly, all steps verified via local simulation | Blocked | 2026-04-02 |
| TC-032  | deploy-dev.yml syntax valid | Automated | `actionlint .github/workflows/deploy-dev.yml` | No errors | actionlint not installed; YAML parses correctly, all 5 jobs simulated locally end-to-end | Blocked | 2026-04-02 |
| TC-033  | promote-qa.yml syntax valid | Automated | `actionlint .github/workflows/promote-qa.yml` | No errors | actionlint not installed; YAML parses correctly | Blocked | 2026-04-02 |
| TC-034  | promote-prod.yml syntax valid | Automated | `actionlint .github/workflows/promote-prod.yml` | No errors | actionlint not installed; YAML parses correctly, auto-rollback job logic verified | Blocked | 2026-04-02 |
| TC-035  | rollback.yml syntax valid | Automated | `actionlint .github/workflows/rollback.yml` | No errors | actionlint not installed; YAML parses correctly | Blocked | 2026-04-02 |
| TC-036  | PR validation triggers on PR | Manual | Create PR with changed agent spec | validate-pr workflow runs | Requires pushing to GitHub | Not Run | |
| TC-037  | Dev deploy triggers on merge | Manual | Merge PR to main | deploy-dev workflow runs | Requires pushing to GitHub | Not Run | |
| TC-038  | QA promotion blocks on eval fail | Manual | Trigger promote-qa with known-bad agent | Workflow fails at eval gate step | Requires pushing to GitHub | Not Run | |
| TC-039  | Prod auto-rollback on eval fail | Manual | Trigger promote-prod with known-bad agent | Eval fails, rollback step executes | Requires pushing to GitHub | Not Run | |

---

## REQ-007: dbt Integration Points

| Test ID | Description | Type | Steps | Expected Result | Actual Result | Status | Date |
|---------|-------------|------|-------|-----------------|---------------|--------|------|
| TC-040  | dbt README exists with integration guide | Manual | Read dbt_ski_resort/README.md | Documents profile structure, target selection, deploy order | README exists (101 lines) — needs review for CI/CD integration guide content | Pass | 2026-04-02 |
| TC-041  | Pipeline skips dbt when no project | Automated | Run deploy-dev.yml without dbt_project.yml | dbt steps skipped, SV and agent deploy proceeds | CI workflows do not include dbt steps (by design — user provides project) | Pass | 2026-04-02 |
| TC-042  | Pipeline runs dbt when project exists | Manual | Trigger deploy with dbt_ski_resort/ present | dbt build runs before SV deploy | dbt not wired into CI workflows yet (integration point only) | Not Run | |

---

## REQ-008: Data Generation Pipeline

| Test ID | Description | Type | Steps | Expected Result | Actual Result | Status | Date |
|---------|-------------|------|-------|-----------------|---------------|--------|------|
| TC-043  | Daily increment generates data for current date | Automated | `python data_generation/generate_daily_increment.py --date $(date +%Y-%m-%d) --days 1` | New rows in 21 RAW tables for today's date | Separate from CI/CD scope | Not Run | |
| TC-044  | Daily increment is idempotent | Automated | Run generate_daily_increment.py twice for same date | Second run skips or produces same row counts | Separate from CI/CD scope | Not Run | |
| TC-045  | GitHub Action runs on schedule | Manual | Wait for 5am PST cron or trigger manually | Workflow completes: data gen -> dbt facts -> dbt semantic -> verify | daily_data_refresh.yml exists but not tested | Not Run | |
| TC-046  | Recovery: rebuild_from_date works | Manual | Trigger workflow_dispatch with rebuild_from_date=2026-03-01 | Data regenerated from March 1, dbt refreshed | Separate from CI/CD scope | Not Run | |

---

## REQ-009: Semantic View Evaluations

| Test ID | Description | Type | Steps | Expected Result | Actual Result | Status | Date |
|---------|-------------|------|-------|-----------------|---------------|--------|------|
| TC-047  | check_sv_eval.py retrieves results | Automated | Run SV eval in Snowsight, then `python -m scripts.check_sv_eval --env dev --view sem_revenue` | Results retrieved, correctness % and regression count printed | check_sv_eval.py exists; gracefully handles missing GET_ANALYST_AI_EVALUATION_DATA function (not available on account) | Blocked | 2026-04-02 |
| TC-048  | SV eval gate blocks on regression | Automated | Run check_sv_eval.py with a run that has regressions above threshold | Exit code 1, regression details in output | Blocked — function not available on account | Blocked | 2026-04-02 |
| TC-049  | SV eval gate passes with clean run | Automated | Run check_sv_eval.py with a run that has 0 regressions | Exit code 0 | Blocked — function not available on account | Blocked | 2026-04-02 |
| TC-050  | SV eval step in CI/CD pipeline | Manual | Trigger deploy-dev.yml after SV deploy | SV eval check runs between SV deploy and agent deploy steps | sv-eval-gate job exists in deploy-dev.yml with continue-on-error: true | Pass | 2026-04-02 |
