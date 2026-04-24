# 11 — GitHub Actions workflow diff

## Files touched

- `.github/workflows/deploy-dev.yml`
- `.github/workflows/deploy-qa-on-main.yml`
- `.github/workflows/promote-qa.yml`
- `.github/workflows/promote-prod.yml`
- `.github/workflows/rollback.yml`
- `.github/workflows/validate-pr.yml` (smoke test invocation change)

## Pattern: deploy workflows

Before:

```yaml
- name: Deploy agent
  run: python -m agent_management.deploy_agents --env ${{ matrix.env }}
```

After:

```yaml
- name: Snapshot current state
  run: python -m agent_management.snapshot_state --env ${{ matrix.env }}

- name: Deploy agent (versioned)
  run: python -m agent_management.deploy_agents --env ${{ matrix.env }}
  # reads agent_versioning.enabled + agent.deploy_alias internally

- name: Smoke test
  run: python -m agent_management.smoke_test --env ${{ matrix.env }}
```

## Pattern: promote-prod.yml

The two-step "eval in QA, then promote to prod" becomes:

```yaml
# runs after QA evals pass
jobs:
  promote:
    environment: production   # requires approval
    steps:
      - name: Move production alias
        run: |
          python -m agent_management.deploy_agents \
            --env prod \
            --promote-from qa \
            --alias production

      - name: Smoke test prod
        run: python -m agent_management.smoke_test --env prod

      - name: Post-promote eval
        run: python -m agent_management.run_ci_eval --env prod --alias production
```

`--promote-from qa` means: take the version currently aliased `validated` in QA and reassign it to `production` in prod. The library handles the SQL. If versioning is off, it falls back to spec-apply against prod.

## Pattern: rollback.yml

Before (snapshot re-apply):

```yaml
- name: Rollback
  run: python -m agent_management.rollback --env prod --agent RESORT_EXECUTIVE
```

After (identical CLI surface, different backend):

```yaml
- name: Rollback
  run: python -m agent_management.rollback --env prod --agent RESORT_EXECUTIVE
  # library reads the snapshot, finds VERSION$N, runs:
  # ALTER AGENT … MODIFY VERSION VERSION$N SET ALIAS = production
```

No workflow change — the CLI is stable. Documented here so reviewers know the backend changed.

## validate-pr.yml

- Add `python -m agent_management.validate_spec_format agents/specs/*.yml` as a step
- Smoke test step already present, no change

## Diagram

See `diagrams/08_ci_pipeline.txt`.
