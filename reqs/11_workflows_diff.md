# 11 — GitHub Actions workflows (Option B)

## Files touched

Renamed / new:

- `.github/workflows/deploy-dev.yml` — on branch push / manual; deploys to DEV agent, alias=latest
- `.github/workflows/deploy-prod-validated.yml` — on main push; deploys to PROD agent, alias=validated, runs eval
- `.github/workflows/promote-validated-to-production.yml` — manual dispatch; env `production-promote` with required reviewers; flips alias `production` to whatever version currently holds `validated`
- `.github/workflows/rollback.yml` — manual dispatch; alias reassignment via `rollback.py`
- `.github/workflows/validate-pr.yml` — updated matrix `[dev, prod]`; adds `validate_spec_format` step

Deleted:

- `.github/workflows/deploy-qa-on-main.yml`
- `.github/workflows/promote-qa.yml`
- `.github/workflows/promote-prod.yml`  ← replaced by `promote-validated-to-production.yml`

## deploy-dev.yml (feature branch)

```yaml
on:
  push:
    branches-ignore: [main]
  workflow_dispatch:

jobs:
  deploy:
    steps:
      - uses: actions/checkout@v4
      - uses: ./.github/actions/setup-python
      - uses: ./.github/actions/snow-auth
        with:
          role: AM_DEPLOY_ROLE_DEV
      - name: Dbt build (target=dev)
        run: cd dbt_ski_resort && dbt build --target dev
      - name: Deploy semantic views
        run: python -m agent_management.deploy_semantic_views --env dev
      - name: Snapshot agent state
        run: python -m agent_management.snapshot_state --env dev
      - name: Deploy agents (alias=latest)
        run: python -m agent_management.deploy_agents --env dev
      - name: Smoke test
        run: python -m agent_management.smoke_test --env dev --alias latest
```

## deploy-prod-validated.yml (main merge)

```yaml
on:
  push:
    branches: [main]

jobs:
  deploy:
    steps:
      - uses: actions/checkout@v4
      - uses: ./.github/actions/setup-python
      - uses: ./.github/actions/snow-auth
        with:
          role: AM_DEPLOY_ROLE
      - name: Dbt build (target=prod)
        run: cd dbt_ski_resort && dbt build --target prod
      - name: Deploy semantic views
        run: python -m agent_management.deploy_semantic_views --env prod
      - name: Snapshot agent state
        run: python -m agent_management.snapshot_state --env prod
      - name: Deploy agents (alias=validated)
        run: python -m agent_management.deploy_agents --env prod
        # reads deploy_alias=validated from prod.env.yml
      - name: Smoke test (validated)
        run: python -m agent_management.smoke_test --env prod --alias validated
      - name: CI eval (validated)
        run: python -m agent_management.run_ci_eval --env prod --alias validated
      - name: Publish version info
        uses: actions/upload-artifact@v4
        with:
          name: validated-versions
          path: .snowflake/ci/snapshots/prod/
```

## promote-validated-to-production.yml (approval gate)

```yaml
on:
  workflow_dispatch:
    inputs:
      agent:
        description: 'Agent to promote (all if blank)'
        required: false

jobs:
  promote:
    environment: production-promote   # required reviewers gate
    steps:
      - uses: actions/checkout@v4
      - uses: ./.github/actions/setup-python
      - uses: ./.github/actions/snow-auth
        with:
          role: AM_DEPLOY_ROLE
      - name: Promote validated to production
        run: |
          python -m agent_management.versioning promote \
            --env prod \
            --from validated \
            --to production \
            ${{ inputs.agent && format('--agent {0}', inputs.agent) || '' }}
      - name: Smoke test (production)
        run: python -m agent_management.smoke_test --env prod --alias production
      - name: Post-promote eval
        run: python -m agent_management.run_ci_eval --env prod --alias production
```

## rollback.yml (manual)

```yaml
on:
  workflow_dispatch:
    inputs:
      env:
        required: true
        type: choice
        options: [dev, prod]
      agent:
        required: true
      alias:
        required: true
      target_version:
        required: false

jobs:
  rollback:
    environment: ${{ inputs.env == 'prod' && 'production-promote' || '' }}
    steps:
      - uses: actions/checkout@v4
      - uses: ./.github/actions/setup-python
      - uses: ./.github/actions/snow-auth
      - name: Rollback
        run: |
          python -m agent_management.rollback \
            --env ${{ inputs.env }} \
            --agent ${{ inputs.agent }} \
            --alias ${{ inputs.alias }} \
            ${{ inputs.target_version && format('--to {0}', inputs.target_version) || '' }}
      - name: Smoke test
        run: python -m agent_management.smoke_test --env ${{ inputs.env }} --alias ${{ inputs.alias }}
```

## validate-pr.yml

- Matrix becomes `[dev, prod]` (no qa).
- New step: `python -m agent_management.validate_spec_format agents/specs/*.yml`.
- `detect_sv_drift` runs per env (advisory today; blocking once clean).

## Diagram

See `diagrams/08_ci_pipeline.txt`.
