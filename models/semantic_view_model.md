# Model: Semantic View Definition

## Purpose
Defines the YAML structure for a Cortex Semantic View as stored in `semantic-views/definitions/`. Semantic views provide a business-friendly abstraction over physical tables, defining dimensions, facts, time dimensions, and relationships that Cortex Analyst uses to generate SQL from natural language.

## Source(s)
| Source Object | Type | Grain | Notes |
|--------------|------|-------|-------|
| semantic-views/definitions/*.yml | YAML file | One file per semantic view | Deployed via SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML |
| SADM_SKI_RESORT_DB.SEMANTIC.* | Semantic View | One object per SV per environment | Created/replaced by deploy script |

## Schema

| Field | Data Type | Nullable | Description | Business Logic |
|-------|-----------|----------|-------------|----------------|
| name | STRING | No | Semantic view identifier | Matches Snowflake object name |
| description | STRING | No | Purpose and scope of this semantic view | Guides Cortex Analyst tool selection |
| tables[] | LIST | No | Array of table definitions included in this view | |
| tables[].name | STRING | No | Logical table name within the semantic view | Usually matches physical table name |
| tables[].base_table.database | STRING | No | Physical database | Uses Jinja2 or hardcoded per SV |
| tables[].base_table.schema | STRING | No | Physical schema | Typically MARTS |
| tables[].base_table.table | STRING | No | Physical table name | |
| tables[].dimensions[] | LIST | Yes | Non-time categorical columns | |
| tables[].dimensions[].name | STRING | No | Column name | |
| tables[].dimensions[].expr | STRING | No | SQL expression | Usually matches column name |
| tables[].dimensions[].data_type | STRING | No | Snowflake data type | VARCHAR, NUMBER, BOOLEAN |
| tables[].time_dimensions[] | LIST | Yes | Date/time columns | |
| tables[].time_dimensions[].name | STRING | No | Column name | |
| tables[].time_dimensions[].expr | STRING | No | SQL expression | |
| tables[].time_dimensions[].data_type | STRING | No | Snowflake data type | DATE, TIMESTAMP_NTZ |
| tables[].facts[] | LIST | Yes | Numeric measure columns | |
| tables[].facts[].name | STRING | No | Column name | |
| tables[].facts[].expr | STRING | No | SQL expression | Can be calculated: `PRICE * QUANTITY` |
| tables[].facts[].data_type | STRING | No | Snowflake data type | NUMBER, FLOAT |
| relationships[] | LIST | Yes | Join definitions between tables | |
| metrics[] | LIST | Yes | Pre-defined aggregate calculations | |

## Relationships
- Semantic View -> base tables in SADM_SKI_RESORT_DB.MARTS (physical dependency)
- Semantic View -> Agent spec tools[].semantic_view (referenced by agents)

## Business Rules
- Every base table referenced must exist in the target database/schema before deployment
- `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML` validates column existence against live tables
- Dry-run validation (3rd arg TRUE) checks everything without creating the object
- `relationship_type` and `join_type` are auto-inferred by semantic views — do not specify them
- Round-trip export via `SYSTEM$READ_YAML_FROM_SEMANTIC_VIEW` is lossy on first pass (ordering/formatting changes) but idempotent thereafter

## Notes
- 4 of 11 total ski resort semantic views included in this repo
- SEM_DAILY_SUMMARY: executive KPIs (4 fact tables, 1 dim)
- SEM_REVENUE: ticket, rental, F&B revenue (3 fact tables, 5 dims)
- SEM_OPERATIONS: lift operations (1 fact table, 3 dims)
- SEM_STAFFING_ANALYTICS: staffing/labor (1 fact table, 2 dims)
