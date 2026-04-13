# Semantic Views

Standalone semantic view YAML definitions, rendered generated output, and pre-deploy snapshots.

## Directory Layout

```
semantic-views/
  definitions/               # Source of truth — one YAML per semantic view
    sem_revenue.yaml
    sem_operations.yaml
    sem_daily_summary.yaml
    ...
  generated/{env}/           # Auto-generated rendered YAMLs (do not edit)
  snapshots/{env}/           # Pre-deploy state captures (auto-generated)
  verified_queries/          # VQR files for Cortex Analyst accuracy
```

## Adding a New Semantic View

1. Create `definitions/sem_<domain>.yaml`.

2. Required structure:

   ```yaml
   name: sem_my_domain
   description: 'What this semantic view covers.'
   tables:
     - name: FACT_MY_TABLE
       base_table:
         database: "{{ env.database }}"
         schema: MARTS
         table: FACT_MY_TABLE
       dimensions:
         - name: MY_KEY
           expr: MY_KEY
           data_type: VARCHAR
       facts:
         - name: TOTAL_AMOUNT
           expr: TOTAL_AMOUNT
           data_type: NUMBER
       time_dimensions:
         - name: EVENT_DATE
           expr: EVENT_DATE
           data_type: DATE
       primary_key:
         columns: [MY_KEY]
   ```

3. Validate locally:

   ```bash
   python -m agent_management.validate_specs --env dev
   ```

4. Dry-run deploy (validates against Snowflake without creating):

   ```bash
   python -m agent_management.deploy_semantic_views --env dev --view sem_my_domain --dry-run
   ```

5. Deploy:

   ```bash
   python -m agent_management.deploy_semantic_views --env dev --view sem_my_domain
   ```

## Conventions

- **File naming**: `definitions/sem_<domain>.yaml` — prefix `sem_` is required (glob pattern matches `sem_*.y*ml`).
- **Jinja2 placeholders**: Use `{{ env.database }}` for the database name. Schema names (MARTS, STAGING) are typically static since they don't vary by environment.
- **Column coverage**: Declare all columns you want the agent to query. Undeclared columns in the underlying table will be flagged by drift detection.
- **Descriptions**: Add meaningful descriptions to facts and dimensions — Cortex Analyst uses these for SQL generation.
- **Joins**: Use `relationships` to declare foreign key joins between tables within the same SV.

## Dual Deployment Path

Semantic views can be deployed two ways:

| Method | Source | When to Use |
|--------|--------|-------------|
| `deploy_semantic_views.py` | `definitions/*.yaml` | Standalone definitions, full control over YAML |
| dbt `semantic_view` materialization | `dbt_ski_resort/models/marts/semantic/` | Integrated with dbt DAG, inherits dbt conventions |

Both paths produce identical Snowflake objects. This repo uses **both** — the dbt models define the mart tables, and the standalone YAMLs here define the semantic views that reference those tables.

## Drift Detection

```bash
python -m agent_management.detect_drift --env dev
```

Compares declared columns in SV YAMLs against actual table schemas. Reports:
- `COLUMN_MISSING` — column declared in SV but not in table
- `COLUMN_UNDECLARED` — column in table but not declared in SV
- `TABLE_NOT_FOUND` — base table doesn't exist

## What Not to Edit

- `generated/` — Rendered output from Jinja2 templates. Overwritten on deploy.
- `snapshots/` — Pre-deploy captures for rollback.

## Related Commands

```bash
python -m agent_management.validate_specs --env dev                  # Validate all
python -m agent_management.deploy_semantic_views --env dev            # Deploy all SVs
python -m agent_management.deploy_semantic_views --env dev -v <name>  # Deploy one SV
python -m agent_management.detect_drift --env dev                    # Check for drift
python -m agent_management.snapshot_state --env dev -t semantic-views # Snapshot state
```
