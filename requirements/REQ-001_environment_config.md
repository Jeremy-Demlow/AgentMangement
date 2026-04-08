# REQ-001: Environment Configuration System

## Summary
YAML-based config system that parameterizes all Snowflake object references per environment, enabling the same agent and semantic view specs to deploy to dev, QA, and prod with different object names.

## Business Context
Cortex Agents and Semantic Views reference fully qualified Snowflake objects (DATABASE.SCHEMA.OBJECT). Without environment parameterization, teams must maintain separate copies of every spec per environment, leading to drift, manual errors, and broken promotions. A config-as-code approach lets one source-of-truth spec deploy correctly to any environment.

## Acceptance Criteria
- [ ] Environment configs exist for dev, QA, prod in `environments/` directory
- [ ] Config loader resolves database, schema, warehouse, role, stage per environment
- [ ] Jinja2 renderer substitutes `{{ env.database }}`, `{{ env.schema }}`, etc. in any YAML template
- [ ] Supports 3 isolation patterns: separate databases (default), separate schemas, separate accounts
- [ ] Template file `_template.env.yml` documents all configurable fields
- [ ] `SNOWFLAKE_ENV` environment variable overrides default environment selection

## User Stories
| Story ID | As a... | I want to... | So that... |
|----------|---------|-------------|------------|
| US-001   | platform engineer | define env-specific configs in YAML | the same specs deploy to dev/QA/prod with different object names |
| US-002   | DevOps engineer | a single env variable to control which environment deploys target | GitHub Actions can parameterize workflows |

## Dependencies
- None (foundation layer)

## Out of Scope
- Terraform or infrastructure-as-code for creating Snowflake databases/schemas/roles
- Secrets management (handled by GitHub Secrets and connections.toml)
- Multi-region deployment orchestration

## Notes
- Default demo uses database isolation: SADM_SKI_RESORT_DB with _DEV, _QA suffixes on agents
- Account isolation pattern documented but not demonstrated in the reference implementation
- Config files are plain YAML, loaded by `scripts/utils/config.py`
