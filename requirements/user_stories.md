# User Stories

All user stories for the project, organized by requirement.

## How to Use
- Add stories here as you define requirements
- Each story must link back to a requirement ID
- Each story should have at least one test case in `tests/test_cases.md`

---

## REQ-001: Environment Configuration System

| Story ID | As a... | I want to... | So that... | Priority | Status |
|----------|---------|-------------|------------|----------|--------|
| US-001   | platform engineer | define env-specific configs in YAML | the same specs deploy to dev/QA/prod with different object names | High | To Do |
| US-002   | DevOps engineer | a single env variable to control which environment deploys target | GitHub Actions can parameterize workflows | High | To Do |

---

## REQ-002: Semantic View CI/CD Pipeline

| Story ID | As a... | I want to... | So that... | Priority | Status |
|----------|---------|-------------|------------|----------|--------|
| US-003   | data engineer | semantic views defined in Git | changes go through PR review before reaching any environment | High | To Do |
| US-004   | data engineer | dry-run validation before deploying | I catch YAML errors and missing columns before they break production | High | To Do |
| US-005   | operator | drift detection comparing Git vs deployed state | I know if someone edited a semantic view in the UI without updating Git | Medium | To Do |

---

## REQ-003: Agent CI/CD Pipeline

| Story ID | As a... | I want to... | So that... | Priority | Status |
|----------|---------|-------------|------------|----------|--------|
| US-006   | platform engineer | agent specs defined in Git | I never manually add/remove semantic views in the UI | High | To Do |
| US-007   | platform engineer | parameterized agent specs with env placeholders | the same spec deploys to dev/QA/prod with correct fully qualified names | High | To Do |
| US-008   | operator | deploy order enforcement (SVs before agents) | agents never reference semantic views that do not exist yet | High | To Do |

---

## REQ-004: Evaluation Framework with Gate

| Story ID | As a... | I want to... | So that... | Priority | Status |
|----------|---------|-------------|------------|----------|--------|
| US-009   | QA engineer | golden question sets with known-correct answers | agent quality is measured objectively against ground truth | High | To Do |
| US-010   | QA engineer | F1, precision, and recall metrics | I can quantify agent accuracy beyond LLM-judge averages | High | To Do |
| US-011   | DevOps engineer | eval exit codes (0 = pass, 1 = fail) | CI/CD can automatically gate promotions on quality thresholds | High | To Do |
| US-012   | data analyst | custom metrics like relevance and faithfulness | I measure answer quality dimensions beyond just correctness | Medium | To Do |

---

## REQ-005: Snapshot and Rollback

| Story ID | As a... | I want to... | So that... | Priority | Status |
|----------|---------|-------------|------------|----------|--------|
| US-013   | operator | pre-deploy snapshots of current state | I always have a known-good state to restore if a deploy breaks something | High | To Do |
| US-014   | operator | rollback by timestamp | I can restore any prior deployment, not just the most recent one | Medium | To Do |
| US-015   | DevOps engineer | auto-rollback on prod eval failure | broken changes are automatically reversed without manual intervention | High | To Do |

---

## REQ-006: GitHub Actions Workflows

| Story ID | As a... | I want to... | So that... | Priority | Status |
|----------|---------|-------------|------------|----------|--------|
| US-016   | developer | PR validation that lints and dry-run validates specs | broken specs never merge to main | High | To Do |
| US-017   | DevOps engineer | automated dev deploy on merge to main | the dev environment always reflects the latest main branch | High | To Do |
| US-018   | DevOps engineer | manual promotion with eval gates for QA and prod | environment changes are deliberate and quality-validated | High | To Do |
| US-019   | operator | a rollback workflow triggered from the GitHub UI | I can restore any environment without SSH or CLI access | Medium | To Do |

---

## REQ-007: dbt Integration Points

| Story ID | As a... | I want to... | So that... | Priority | Status |
|----------|---------|-------------|------------|----------|--------|
| US-020   | data engineer | a clear integration guide for my dbt project | I can plug my existing dbt project into this pipeline without guessing | Medium | To Do |
| US-021   | DevOps engineer | conditional dbt steps in the pipeline | the pipeline works correctly with or without a dbt project present | Medium | To Do |

---

## REQ-008: Data Generation Pipeline

| Story ID | As a... | I want to... | So that... | Priority | Status |
|----------|---------|-------------|------------|----------|--------|
| US-022   | developer | synthetic data generated daily on a schedule | the demo environment always has current, realistic data for agent evaluations | High | Done |
| US-023   | developer | recovery options for data corruption | I can rebuild from any date without losing the entire dataset | Medium | Done |

---

## REQ-009: Semantic View Evaluations

| Story ID | As a... | I want to... | So that... | Priority | Status |
|----------|---------|-------------|------------|----------|--------|
| US-024   | data engineer | SQL correctness checks on my semantic views after each deploy | I catch SV regressions before they cascade into agent failures | High | To Do |
| US-025   | DevOps engineer | a CI gate based on SV eval regression count | broken semantic views never reach agent deployment | High | To Do |
