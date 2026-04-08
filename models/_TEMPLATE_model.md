# Model: [Model Name]

## Purpose
[What this model represents and why it exists]

## Source(s)
| Source Object | Type | Grain | Notes |
|--------------|------|-------|-------|
| DB.SCHEMA.TABLE | Table | One row per [entity] | |

## Schema

| Column | Data Type | Nullable | Description | Business Logic |
|--------|-----------|----------|-------------|----------------|
| id     | NUMBER    | No       | Primary key |                |

## Relationships
- [Model Name].column → [Other Model].column (FK)

## Business Rules
- [Rule 1: e.g., "status can only transition from PENDING → ACTIVE → CLOSED"]
- [Rule 2]

## Notes
- [Anything relevant: refresh cadence, known quirks, data quality issues]
