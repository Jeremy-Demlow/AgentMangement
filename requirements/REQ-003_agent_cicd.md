# REQ-003: Agent CI/CD Pipeline

## Summary
Cortex Agent specs defined as YAML in Git with automatic semantic view binding, deployed via `CREATE OR REPLACE AGENT ... FROM SPECIFICATION`, with enforced deploy ordering so agents never reference non-existent semantic views.

## Business Context
Today, teams manually add and remove semantic views from agents in the Snowsight UI. This creates an unversioned, unauditable state that cannot be reproduced across environments. When a semantic view change breaks an agent, there is no clear path to restore the previous working configuration. Defining agent specs as code and deploying them through CI/CD eliminates manual state management and enables reliable promotion across dev, QA, and prod.

## Acceptance Criteria
- [ ] 2 agent spec YAML files in `agents/specs/` (resort_executive, ski_ops_assistant)
- [ ] `deploy_agents.py` creates/replaces agents via `CREATE OR REPLACE AGENT ... FROM SPECIFICATION`
- [ ] Agent specs reference semantic views via Jinja2 env placeholders (no hardcoded FQNs)
- [ ] `--dry-run` flag validates spec structure without deploying
- [ ] `--agent <name>` deploys a single agent
- [ ] Deploy order enforced: semantic views must exist before agent deploy
- [ ] Agent spec includes: models, instructions, tools, tool_resources with semantic_view + warehouse

## User Stories
| Story ID | As a... | I want to... | So that... |
|----------|---------|-------------|------------|
| US-006   | platform engineer | agent specs defined in Git | I never manually add/remove semantic views in the UI |
| US-007   | platform engineer | parameterized agent specs with env placeholders | the same spec deploys to dev/QA/prod with correct fully qualified names |
| US-008   | operator | deploy order enforcement (SVs before agents) | agents never reference semantic views that do not exist yet |

## Dependencies
- REQ-001: Environment Configuration System (for FQN resolution)
- REQ-002: Semantic View CI/CD Pipeline (semantic views must deploy before agents)

## Out of Scope
- Cortex Search Service tools (only Cortex Analyst text-to-SQL tools are in scope)
- Agent versioning beyond Git history (no native Snowflake version timeline exists today)
- Snowflake Intelligence integration configuration
- Agent runtime budgets (seconds, tokens) — documented but not parameterized per env

## Notes
- `CREATE OR REPLACE AGENT ... FROM SPECIFICATION $$ yaml $$` is the deploy mechanism
- `ALTER AGENT ... MODIFY LIVE VERSION SET SPECIFICATION` can update without full replace
- `DESCRIBE AGENT` returns AGENT_SPEC as JSON (used by snapshot, see REQ-005)
- `GET_DDL('CORTEX_AGENT', fqn)` exists but output has formatting bugs — use DESCRIBE instead
- 2 of 3 total ski resort agents included; pattern scales to any number of agents
