# Agents

Cortex Agent spec definitions, generated deployment SQL, and pre-deploy snapshots.

## Directory Layout

```
agents/
  specs/                     # Source of truth — one YAML per agent
    resort_executive.yml
    ski_ops_assistant.yml
  generated/{env}/           # Auto-generated SQL + spec JSON (do not edit)
    RESORT_EXECUTIVE.sql
    RESORT_EXECUTIVE_spec.json
  snapshots/{env}/           # Pre-deploy state captures (auto-generated)
    RESORT_EXECUTIVE_20260402_030209.json
```

## Adding a New Agent

1. Create `specs/<agent_name>.yml` using an existing spec as a template.

2. Required top-level fields:

   ```yaml
   metadata:
     name: my_agent          # Lowercase, underscored — becomes UPPER in Snowflake
     version: "1.0.0"
     owner: team_name
     status: active

   description: >
     What this agent does.

   tools:
     - name: ToolName
       type: cortex_analyst_text_to_sql   # or cortex_search, generic
       semantic_view: "{{ env.semantic_schema }}.SEM_MY_VIEW"
       warehouse: "{{ env.warehouse }}"
       description: >
         What this tool accesses and when to use it.
   ```

3. Validate locally:

   ```bash
   agent-mgmt-validate --env dev
   ```

4. Dry-run deploy:

   ```bash
   agent-mgmt-deploy-agents --env dev --agent my_agent --dry-run
   ```

5. Generated SQL appears in `generated/dev/MY_AGENT.sql`.

## Conventions

- **File naming**: `specs/<agent_name>.yml` — lowercase with underscores, matching `metadata.name`.
- **Jinja2 placeholders**: Use `{{ env.* }}` for environment-specific values (database, schema, warehouse). Never hardcode environment names.
- **Tool descriptions**: Include key metrics, dimensions, and use-case guidance. The LLM orchestrator uses these to route questions.
- **Instructions**: `orchestration` for routing logic, `response` for output formatting. Both are optional.
- **Sample questions**: Add 5-8 representative questions that exercise different tools.

## What Not to Edit

- `generated/` — Overwritten on every deploy. Useful for reviewing what was deployed.
- `snapshots/` — Created by `snapshot_state.py` before deploys. Used for rollback.

## Deployment Behavior

| Scenario | SQL Used |
|----------|----------|
| Agent already exists | `ALTER AGENT ... MODIFY LIVE VERSION SET SPECIFICATION` (preserves eval history) |
| Agent does not exist | `CREATE AGENT IF NOT EXISTS` |
| `--force-create` flag | `CREATE OR REPLACE AGENT` (destroys eval history) |

## Related Commands

```bash
agent-mgmt-validate --env dev          # Validate all specs
agent-mgmt-deploy-agents --env dev           # Deploy all agents
agent-mgmt-deploy-agents --env dev -a <name> # Deploy one agent
agent-mgmt-snapshot --env dev -t agents # Snapshot current state
agent-mgmt-rollback --env dev --list          # List available snapshots
```
