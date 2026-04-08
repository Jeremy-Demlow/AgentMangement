# Model: Agent Specification

## Purpose
Defines the YAML structure for a Cortex Agent spec as stored in `agents/specs/`. This is the source-of-truth for agent configuration, including which semantic views are bound, which model is used for orchestration, and what instructions govern agent behavior.

## Source(s)
| Source Object | Type | Grain | Notes |
|--------------|------|-------|-------|
| agents/specs/*.yml | YAML file | One file per agent | Jinja2 templates, rendered per environment |
| SADM_SKI_RESORT_DB.AGENTS.* | Cortex Agent | One object per agent per environment | Deployed via CREATE OR REPLACE AGENT |

## Schema

| Field | Data Type | Nullable | Description | Business Logic |
|-------|-----------|----------|-------------|----------------|
| metadata.name | STRING | No | Agent identifier (used as filename and Snowflake object name) | Lowercase, underscores |
| metadata.version | STRING | Yes | Semantic version for tracking | Format: x.y.z |
| metadata.owner | STRING | Yes | Team or individual responsible | |
| metadata.status | STRING | Yes | Lifecycle state | active, deprecated, experimental |
| profile.display_name | STRING | No | Human-readable name shown in Snowsight | |
| profile.color | STRING | Yes | UI color hint | |
| description | STRING | No | Multi-line description of agent purpose and capabilities | |
| sample_questions | LIST[STRING] | Yes | Example questions for users | |
| tools[].name | STRING | No | Tool identifier within agent spec | Must match key in tool_resources |
| tools[].type | STRING | No | Tool type | Always `cortex_analyst_text_to_sql` in this repo |
| tools[].semantic_view | STRING | No | FQN of semantic view | Uses Jinja2: `{{ env.database }}.{{ env.schema }}.SEM_NAME` |
| tools[].warehouse | STRING | No | Warehouse for query execution | Uses Jinja2: `{{ env.warehouse }}` |
| tools[].description | STRING | No | Detailed tool description with key metrics and dimensions | Guides orchestration routing |
| instructions.response | STRING | No | How to format and present answers | Tone, format, conventions |
| instructions.orchestration | STRING | No | Tool routing logic and boundaries | Which tool for which question type |

## Relationships
- Agent spec tools[].semantic_view -> Semantic View definitions in `semantic-views/definitions/`
- Agent spec -> Environment config in `environments/` (via Jinja2 rendering)

## Business Rules
- Every tool must have a corresponding entry in the semantic-views/definitions/ directory
- Agent specs must never contain hardcoded fully qualified names — always use Jinja2 placeholders
- The `specification` block (models, instructions, tools, tool_resources) is what gets passed to `CREATE AGENT ... FROM SPECIFICATION`
- The outer metadata, profile, description, and sample_questions are used by deploy scripts but are not part of the Snowflake SPECIFICATION block

## Notes
- Max spec size: 100,000 bytes
- Both YAML and JSON formats supported by Snowflake; this repo uses YAML
- `MODIFY LIVE VERSION SET SPECIFICATION` completely replaces the spec — omitted fields are removed
