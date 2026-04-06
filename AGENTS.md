# Project Rules for Cortex Code

## Identity
- Project Name: Cortex Agent CI/CD Reference Framework
- Owner: Jeremy Demlow
- Created: 2026-04-02
- Status: In Progress

## Core Principles

These principles combine fast.ai's engineering philosophy with Snowflake-specific best practices. Every contributor — human or AI — follows them.

1. **Read requirements first** — every feature traces to a REQ-ID in `requirements/`. Check acceptance criteria before writing code. If there is no requirement, create one before implementing.

2. **Top-down design** — start with the interface. Define what a function accepts and returns before writing its body. Define what a script's CLI looks like before implementing its logic. The caller's experience matters more than the implementer's convenience.

3. **Minimal abstractions** — one function beats one class when sufficient. Do not add inheritance, registries, or plugin systems until the third time you need them. The simplest code that meets the requirement is the correct code.

4. **Test everything, trust nothing** — every requirement has acceptance criteria. Every deploy has a verification step. Every eval run checks thresholds. If you cannot verify it works, it does not work.

5. **No corner-cutting** — no `|| true` to hide failures. No `try/except: pass` to swallow errors. No skipping the eval step because "it worked last time." If it is worth building, it is worth building correctly.

6. **REPL-driven development** — test SQL in Snowflake before scripting it. Validate YAML with `--dry-run` before deploying. Run `run_eval.py` on one question before running the full suite. Small increments, verified at each step.

7. **Snowflake conventions** — uppercase SQL keywords, lowercase identifiers, fully qualified object names (`DATABASE.SCHEMA.OBJECT`). No hardcoded secrets. Connection via environment variables or `connections.toml`.

8. **CI/CD discipline** — every change goes through PR -> validate -> deploy -> eval gate. No manual Snowsight edits to agents or semantic views. If it is not in Git, it does not exist.

## Workflow
1. **Understand** — read the relevant requirement in `requirements/` and its user stories
2. **Plan** — use the todo tool to break work into steps; confirm ambiguous items with user
3. **Implement** — follow conventions in this file and `docs/architecture.md`; reference REQ-IDs
4. **Test** — run tests from `tests/test_cases.md`; use `--dry-run` flags; check eval thresholds
5. **Document** — update data dictionary, dev notes, and architecture docs as needed

## Requirement Traceability
- Every code change must reference a REQ-ID (e.g., "Implements REQ-003 acceptance criterion 2")
- Sub-agents must read `requirements/` to understand acceptance criteria before implementing
- Sub-agents must verify completion against acceptance criteria before reporting done
- If acceptance criteria cannot be met, report what is blocked and why — do not silently skip

## Code Conventions
- SQL: uppercase keywords, lowercase identifiers, fully qualified object names (db.schema.object)
- Python: snake_case, type hints, docstrings on public functions only, no comments unless explaining *why*
- YAML: 2-space indent, Jinja2 placeholders for env-specific values (`{{ env.database }}`)
- All code: no comments unless explaining *why* (not *what*), no hardcoded secrets

## File Conventions
- Requirements go in `requirements/` — one file per feature, prefixed REQ-NNN
- Agent specs go in `agents/specs/` — one YAML per agent
- Semantic view definitions go in `semantic-views/definitions/` — one YAML per view
- Eval datasets go in `agent-evaluation/datasets/` — one YAML per agent
- Environment configs go in `environments/` — one YAML per environment
- Deploy/eval/rollback scripts go in `agent_management/`
- Test cases go in `tests/test_cases.md` — linked to requirement IDs
- Data models go in `models/` — one file per logical data model

## Folder Structure
```
AgentMangement/
├── AGENTS.md                              # This file — AI rules
├── README.md                              # Setup guide and runbook
├── Makefile                               # Common operations
├── requirements.txt                       # Python dependencies
├── pyproject.toml                         # Project metadata
├── .plans/                                # Execution plans
├── .gitignore
│
├── .github/workflows/                     # CI/CD workflows
│   ├── daily_data_refresh.yml             # Daily data pipeline (EXISTS)
│   ├── dcm-deploy.yml                  # DCM infrastructure deploy
│   ├── validate-pr.yml                    # Lint + validate on PR
│   ├── deploy-dev.yml                     # Deploy on merge to main
│   ├── promote-qa.yml                     # Manual promote with eval gate
│   ├── promote-prod.yml                   # Manual promote with approval + eval gate
│   └── rollback.yml                       # Rollback any environment
│
├── dcm/                                  # Infrastructure as Code (DCM)
│   ├── manifest.yml                      # DEV/QA/PROD targets + templating
│   ├── sources/
│   │   ├── definitions/
│   │   │   ├── infrastructure.sql        # Database, schemas, warehouse, stage
│   │   │   └── access.sql               # Roles, grants, user assignments
│   │   └── macros/
│   │       └── grants_macro.sql          # Reusable grant macros
│   └── post_deploy.sql                  # Reserved for non-DEFINE objects
│
├── environments/                          # Per-environment configs
│   ├── dev.env.yml
│   ├── qa.env.yml
│   ├── prod.env.yml
│   └── _template.env.yml
│
├── agents/                                # Cortex Agent specs
│   ├── specs/                             # YAML agent definitions (Jinja2)
│   └── snapshots/                         # Pre-deploy state captures
│
├── semantic-views/                        # Semantic View definitions
│   ├── definitions/                       # YAML view definitions
│   └── snapshots/                         # Pre-deploy state captures
│
├── data_generation/                       # Synthetic ski resort data (EXISTS)
│   ├── generate_complete_ski_data.py
│   ├── generate_daily_increment.py
│   └── shared.py
│
├── dbt_ski_resort/                        # dbt Kimball model (EXISTS)
│   ├── models/staging/
│   ├── models/marts/dimensions/
│   ├── models/marts/facts/
│   └── models/marts/semantic/
│
├── agent-evaluation/                      # Evaluation framework (EXISTS)
│   ├── scripts/run_eval.py
│   ├── datasets/                          # Golden question sets per agent
│   ├── metrics/                           # Custom LLM-judge metric YAML
│   ├── configs/                           # Eval runner configs per agent
│   └── results/                           # Eval run results (JSON)
│
├── agent_management/                      # Reusable library (pip installable)
│   ├── __init__.py                        # Package root (version 0.6.0)
│   ├── deploy_semantic_views.py
│   ├── deploy_agents.py
│   ├── snapshot_state.py
│   ├── rollback.py
│   ├── compute_metrics.py
│   ├── check_sv_eval.py
│   ├── validate_specs.py
│   ├── render_template.py
│   ├── render_eval_templates.py
│   ├── detect_drift.py
│   ├── ci/                                # fdbt-powered CI checks
│   │   ├── check_test_coverage.py         # Enforce min test coverage %
│   │   ├── check_pk_tests.py              # Validate PK tests on every model
│   │   └── generate_lineage_comment.py    # Auto-comment lineage on PRs
│   └── utils/
│       ├── snowflake_client.py
│       └── config.py
│
├── requirements/                          # What to build
│   ├── REQ-001_environment_config.md
│   ├── REQ-002_semantic_view_cicd.md
│   ├── REQ-003_agent_cicd.md
│   ├── REQ-004_eval_framework.md
│   ├── REQ-005_rollback.md
│   ├── REQ-006_github_actions.md
│   ├── REQ-007_dbt_integration.md
│   ├── REQ-008_data_generation.md
│   ├── REQ-009_semantic_view_eval.md
│   ├── REQ-010_library_config.md
│   ├── REQ-011_eval_template_rendering.md
│   ├── REQ-013_infrastructure_as_code.md
│   └── user_stories.md
│
├── models/                                # Data model definitions
│   ├── agent_spec_model.md
│   ├── semantic_view_model.md
│   └── eval_dataset_model.md
│
├── docs/                                  # Project knowledge
│   ├── architecture.md                    # Tech stack, diagrams, decisions
│   ├── data_dictionary.md                 # Every table, view, column
│   └── dev_notes.md                       # Running decision log
│
└── tests/                                 # Proof it works
    ├── test_cases.md                      # All test cases, linked to REQs
    ├── regression.md                      # Bug fixes that must stay fixed
    ├── test_data/
    └── unit/                              # Python unit tests
```

## Snowflake-Specific Rules
- Always use `snowflake_sql_execute` for SQL — never assume objects exist, verify first
- Use connection name from environment, never hardcode credentials
- Check `docs/data_dictionary.md` for table/view definitions before querying
- Validate SQL compiles before executing destructive DDL
- Agent names in eval YAML must be fully qualified: `DATABASE.SCHEMA.AGENT_NAME`
- Stage uploads must use `COPY INTO` (not PUT) to avoid nested subdirectory issues
- `source_metadata.type` in eval configs must be lowercase `"dataset"`

## Quality Gates
- Every requirement must have at least one test case
- Every bug fix must have a regression test entry
- No feature is "done" until tests pass and docs are updated
- No environment promotion without passing eval gate (QA, prod)
- No agent deploy without prior semantic view deploy (order enforced)

## What NOT to Do
- Do not create files outside the defined folder structure
- Do not add dependencies without noting them in `docs/dev_notes.md`
- Do not skip the testing step — ever
- Do not edit agents or semantic views in the Snowsight UI — all changes go through Git
- Do not hardcode environment-specific values in agent or SV specs — use Jinja2 placeholders
- Do not use `PUT` for stage uploads — use `COPY INTO`
- Do not over-engineer: build what is required, nothing more
