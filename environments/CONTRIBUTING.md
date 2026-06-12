# Environments

Environment-specific configuration files that drive the entire deployment pipeline.

## Directory Layout

```
environments/
  dev.env.yml     # DEV — lenient thresholds, _DEV suffix, deploy alias=latest
  prod.env.yml    # PROD — strict thresholds, no suffix, aliases=validated+production
```

## How Environment Configs Work

Every CLI command accepts `--env <name>` which loads `environments/<name>.env.yml`. The config values are injected into agent specs, semantic view definitions, and eval configs via Jinja2 (`{{ env.* }}` and `{{ eval.* }}` placeholders).

```
environments/dev.env.yml
        │
        ▼
  render_template.py → build_context()
        │
        ├── {{ env.database }}     → AM_SKI_RESORT_DEV
        ├── {{ env.warehouse }}    → AM_SKI_RESORT_WH_DEV
        ├── {{ env.semantic_schema }} → SEMANTIC
        └── {{ eval.thresholds.answer_correctness }} → 0.60
```

## Config Structure

Each env file has these sections:

| Section | Purpose | Example |
|---------|---------|---------|
| `environment` | Env name (used in output and generated paths) | `dev` |
| `snowflake` | Connection settings (account, role, warehouse) | `AM_DEPLOY_ROLE_DEV` |
| `deployment` | Target Snowflake objects (database, schemas, stage) | `AM_SKI_RESORT_DEV` |
| `agent.name_suffix` | Appended to agent names for environment isolation | `_DEV` |
| `model.orchestration` | LLM model for agent orchestration | `claude-sonnet-4-5` |
| `orchestration.budget` | Max seconds and tokens per agent interaction | `300s / 50000 tokens` |
| `eval.thresholds` | Pass/fail gates for CI evaluations | `0.60` (DEV) |

## Adding a New Environment

1. Copy an existing config:

   ```bash
   cp environments/dev.env.yml environments/sandbox.env.yml
   ```

2. Update all values — especially `deployment.database`, `snowflake.role`, `snowflake.warehouse`, and `agent.name_suffix`.

3. Ensure the Snowflake infrastructure exists (database, schemas, roles, warehouse). Use DCM or create manually.

4. Validate:

   ```bash
   agent-mgmt-validate --env sandbox
   ```

5. Add the environment to `project.yml` under `environments:` so it's documented centrally.

## Conventions

- **File naming**: `<env_name>.env.yml` — the name before `.env.yml` is what you pass to `--env`.
- **Thresholds progression**: DEV (lenient) < QA (moderate) < PROD (strict). This lets you iterate in DEV while enforcing quality gates upstream.
- **Suffix convention**: `_DEV`, `_QA`, empty for PROD. This is required in single-account mode where all environments share one Snowflake account.
- **Model selection**: Can vary by environment (e.g., cheaper model in DEV, production model in PROD).

## Threshold Reference

| Environment | answer_correctness | logical_consistency | sv_sql_correctness | sv_max_regressions |
|-------------|-------------------|--------------------|--------------------|-------------------|
| DEV | 0.60 | 0.60 | 0.60 | 5 |
| QA | 0.70 | 0.70 | 0.70 | 2 |
| PROD | 0.80 | 0.80 | 0.80 | 0 |

To change thresholds, edit the `eval.thresholds` section in the relevant env file. Template configs and generated configs update automatically on the next render.

## What Not to Do

- Do not hardcode environment-specific values in agent specs or SV definitions. Use `{{ env.* }}` placeholders.
- Do not duplicate threshold values in eval config templates. They should reference `{{ eval.thresholds.* }}`.
- Do not remove the comments in env files — they document what each section is used for and by which workflows.
