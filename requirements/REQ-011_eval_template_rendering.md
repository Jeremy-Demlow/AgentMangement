# REQ-011: Eval Template Rendering Pipeline

## Summary
Resolve Jinja2 placeholders in eval configs and datasets so they can be used directly by the eval runner or uploaded to Snowflake stages.

## Business Context
Eval configs and datasets contain `{{ eval.* }}` Jinja2 placeholders for database names, schema names, stage references, and run dates. These must be resolved to environment-specific values before SQL execution. Additionally, eval metric prompts contain LLM-judge placeholders (`{{output}}`, `{{ground_truth}}`, `{{input}}`) that must pass through untouched. Without a rendering step, eval files cannot be used outside of the specific environment they were authored for.

## Acceptance Criteria
- [x] `build_context()` includes an `eval` namespace with `source_database`, `agents_schema`, `marts_schema`, `stage`, `file_format`, `warehouse`, `run_date`
- [x] `eval.source_database` resolves from `project.yml` eval section (not deployment config)
- [x] `eval.agents_schema` resolves to the eval source schema (e.g., `AGENTS`), NOT the deployment schema (e.g., `AGENTS_DEV`)
- [x] `eval.stage` and `eval.file_format` use the eval source database + source schema for FQNs
- [x] `eval.run_date` defaults to today's date (YYYYMMDD) and is overridable via `--run-date`
- [x] `render_eval_templates.py` CLI discovers all eval YAML files in `agent-evaluation/`
- [x] CLI renders all files to `agent-evaluation/generated/{env}/` preserving directory structure
- [x] Unknown Jinja2 variables (e.g., `{{output}}`, `{{ground_truth}}`) are preserved as-is via `_PreserveUndefined`
- [x] CLI supports `--dry-run`, `--file` (single file), `--run-date` flags
- [x] Rendered output is consistent across dev/qa/prod (same eval source, different deployment targets)
- [x] 12 tests verify all rendering behavior

## User Stories
| Story ID | As a... | I want to... | So that... |
|----------|---------|-------------|------------|
| US-024   | CI pipeline | render eval templates before running evaluations | eval configs point to correct Snowflake objects for the target environment |
| US-025   | Developer | preview rendered eval configs with `--dry-run` | I can verify placeholder resolution before committing generated files |
| US-026   | Developer | override the eval run date | I can re-run historical evaluations or test date-specific behavior |

## Dependencies
- REQ-001: Environment Configuration System (provides `load_env_config()`)
- REQ-010: Library Configuration (provides `project.yml` with eval section)

## Out of Scope
- Actually running evaluations (handled by `run_eval.py` / REQ-004)
- Uploading rendered configs to Snowflake stages (separate step in CI/CD)
- pip-installable package format (REQ-012 — future)

## Notes
- `_PreserveUndefined` is critical: Jinja2 processes `{{ }}` inside YAML comments too, so commented-out metric prompts with `{{output}}` would fail with `StrictUndefined`
- Generated files in `agent-evaluation/generated/` should be `.gitignore`d in production usage (they are environment-specific artifacts)
- The eval source database (`SADM_SKI_RESORT_DB`) is intentionally separate from deployment databases — eval golden questions validate against a stable reference dataset
