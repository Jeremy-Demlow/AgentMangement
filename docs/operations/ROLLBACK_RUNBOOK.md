# Rollback Runbook

A customer-visible regression has reached `production`. This runbook walks
through restoring service.

## Prereqs

- You have permission to trigger `.github/workflows/rollback.yml`.
- You have approver rights on the GitHub `production-promote` environment.
- You know the affected agent short name (e.g. `resort_executive`) and the
  alias (`production`).

## Step 1 — Verify

1. Confirm the regression is live:
   ```bash
   python -m agent_management.smoke_test --env prod --alias production --agent AM_SKI_RESORT.AGENTS.RESORT_EXECUTIVE
   ```
2. Check current versions + alias layout:
   ```bash
   python -m agent_management.versioning list --env prod --agent resort_executive
   ```
   You'll see something like:
   ```json
   {
     "aliases": {"validated": "VERSION$7", "production": "VERSION$7"},
     "versions": [..., {"name": "VERSION$6"}, {"name": "VERSION$7"}]
   }
   ```
3. Identify the last good version (usually the previous `production` holder).
   The snapshot captured before the last deploy is under:
   ```
   .snowflake/ci/snapshots/prod/AM_SKI_RESORT_AGENTS_RESORT_EXECUTIVE/<ts>.json
   ```

## Step 2 — Trigger rollback

From the GitHub UI:

1. Actions → **Rollback** → Run workflow
2. environment: `prod`
3. agent: `resort_executive` (short name) or full FQN
4. alias: `production`
5. target_version: leave empty to use last snapshot pointer, or enter
   `VERSION$6` explicitly.

Approve the `production-promote` environment when GitHub prompts.

The workflow runs:

```sql
ALTER AGENT AM_SKI_RESORT.AGENTS.RESORT_EXECUTIVE
  MODIFY VERSION VERSION$6
  SET ALIAS = production;
```

Then it smoke-tests `!production`.

## Step 3 — Verify

```bash
python -m agent_management.smoke_test --env prod --alias production
```

Customer traffic is restored.

## Step 4 — Post-mortem

The bad version (e.g. `VERSION$7`) is **retained**. Useful for diff:

```bash
python -m agent_management.snapshot_agent --env prod \
  --agent AM_SKI_RESORT.AGENTS.RESORT_EXECUTIVE \
  --version VERSION$7
python -m agent_management.snapshot_agent --env prod \
  --agent AM_SKI_RESORT.AGENTS.RESORT_EXECUTIVE \
  --version VERSION$6
python -m agent_management.snapshot_agent diff snapshots/.../V7.json snapshots/.../V6.json
```

File a bug capturing the diff and the failing eval question. Fix in a PR.
The fix merges → `deploy-prod-validated.yml` commits `VERSION$8` under
`validated` → eval passes → `promote-validated-to-production.yml` flips
`production` forward again.

## Anti-patterns

- Do not drop the bad version immediately. Keep it for forensics; version
  retention will drop it automatically after ~10 deploys.
- Do not edit the spec in Snowsight UI. Versions are authoritative; ad-hoc
  edits create drift.
- Do not re-point `validated` to the older version; let the next merge do
  that when the fix lands.
