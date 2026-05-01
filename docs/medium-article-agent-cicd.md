# CI/CD for Snowflake Cortex Agents: A Complete Framework

*How we built a multi-environment deployment pipeline with automated evaluation gates for AI agents on Snowflake.*

---

## The Problem Nobody Talks About

You've built a Cortex Agent. It answers questions, calls semantic views, and your stakeholders love it. Then someone asks: "Can we get this in production?"

That's when it gets real.

Cortex Agents aren't just code. They're a combination of infrastructure (databases, warehouses, roles), data models (dbt), semantic views (the knowledge layer), agent specifications (tools, instructions, orchestration config), and evaluation datasets (ground truth for quality gates). Change any one of these and the agent's behavior shifts — sometimes subtly, sometimes catastrophically.

Without CI/CD, agent management looks like this: someone SSHes into Snowsight, hand-edits a `CREATE OR ALTER AGENT` statement, eyeballs the output, and declares it "good." That works for one agent in one environment. It doesn't work for two agents across three environments with a team of contributors.

This article walks through the framework we built to solve this. Everything shown here is running in production today. The full repository is structured as a reference implementation you can adapt for your own agents.

---

## What We Built

A promotion pipeline that moves agents from dev through QA to production, with automated evaluation gates at each stage:

```
Feature Branch → PR Validation → Dev Deploy → QA Promotion → Prod Promotion
                 (4 parallel       (snapshot,     (approval,      (approval,
                  checks +          dbt, SVs,      eval hard       snapshot,
                  eval advisory)    agents, eval)  gate)           eval, auto-
                                                                   rollback)
```

The key design principles:

1. **One spec, many environments** — Jinja2 templates resolve per-environment. No copy-paste across dev/QA/prod.
2. **Eval gates, not vibes** — Every promotion runs the agent against ground truth questions and checks score thresholds.
3. **Snapshot-based rollback** — Before every deploy, we clone the current state. If eval fails in prod, we auto-rollback.
4. **Infrastructure as code** — Databases, schemas, warehouses, and roles defined via DCM (Database Change Management).

---

## Repository Architecture

```
AgentManagement/
├── project.yml                    # Central config: environments, defaults, schemas
├── environments/
│   ├── dev.env.yml                # Dev environment: role, warehouse, thresholds
│   ├── qa.env.yml                 # QA environment: stricter thresholds
│   └── prod.env.yml               # Prod environment: strictest thresholds
├── agents/
│   └── specs/
│       ├── resort_executive.yml   # Agent spec template (Jinja2)
│       └── ski_ops_assistant.yml  # Agent spec template (Jinja2)
├── semantic-views/
│   └── definitions/               # Semantic view YAML templates (if source: yaml)
├── agent-evaluation/
│   ├── configs/                   # Per-agent eval config (thresholds, metrics)
│   ├── datasets/                  # Eval questions with dynamic ground truth
│   └── scripts/                   # run_eval.py, eval_summary.py
├── agent_management/              # CLI modules: deploy, snapshot, rollback, eval
├── dbt_ski_resort/                # dbt project: staging → marts → semantic models
├── dcm/                           # Database Change Management: infra-as-code
├── data-generation/               # Synthetic data generation scripts
└── .github/
    └── workflows/                 # 8 workflow files covering the full lifecycle
```

Every directory maps to a pipeline stage. The `environments/` directory is the glue — each `*.env.yml` file defines the full context for one environment:

```yaml
# environments/dev.env.yml
environment: dev

snowflake:
  account: trb65519
  role: AM_DEPLOY_ROLE_DEV
  warehouse: AM_SKI_RESORT_WH_DEV

deployment:
  database: AM_SKI_RESORT_DEV
  semantic_schema: SEMANTIC
  agents_schema: AGENTS
  stage: EVAL_CONFIG_STAGE

semantic_views:
  source: dbt           # "dbt" = verify only; "yaml" = deploy from templates

agent:
  name_suffix: _DEV     # RESORT_EXECUTIVE → RESORT_EXECUTIVE_DEV

model:
  orchestration: claude-sonnet-4-5

eval:
  thresholds:
    answer_correctness: 0.60
    logical_consistency: 0.60
```

This single file drives everything: which Snowflake objects to target, how to name agents, which model to use, and what score thresholds to enforce. Dev is lenient (0.60). QA tightens. Prod is strictest.

### Jinja2 Templating: One Spec, Many Environments

Agent specs use `{{ env.* }}` placeholders that resolve at deploy time:

```yaml
# agents/specs/resort_executive.yml (abbreviated)
metadata:
  name: resort_executive
  version: "1.0.1"

description: >
  Comprehensive business intelligence agent for resort executives.
  11 semantic views covering 4 years of resort data.

tools:
  - name: DailySummaryKPIs
    type: cortex_analyst_text_to_sql
    semantic_view: {{ env.semantic_schema }}.SEM_DAILY_SUMMARY
    warehouse: {{ env.warehouse }}
    description: >
      Executive daily summary — visitation, revenue, operations KPIs.
      KEY METRICS: TOTAL_VISITS, TOTAL_DAILY_REVENUE, PASS_HOLDER_PCT.

  - name: RevenueAnalytics
    type: cortex_analyst_text_to_sql
    semantic_view: {{ env.semantic_schema }}.SEM_REVENUE
    warehouse: {{ env.warehouse }}
    description: >
      Revenue across tickets, rentals, and F&B.

  # ... 9 more tools (11 total)

instructions:
  orchestration: >
    You are Resort Executive Assistant, the comprehensive BI partner
    for leadership. TOOL ROUTING: Overall performance → DailySummaryKPIs.
    Revenue deep dives → RevenueAnalytics. Customer questions →
    CustomerAnalytics or PassholderAnalytics. ...
```

When deployed to dev, `{{ env.semantic_schema }}` becomes `SEMANTIC` and `{{ env.warehouse }}` becomes `AM_SKI_RESORT_WH_DEV`. Same spec, different environment — no divergence.

---

## The Deployment Pipeline

Eight GitHub Actions workflows cover the full lifecycle:

| Workflow | Trigger | Purpose |
|---|---|---|
| `validate-pr.yml` | Pull request | 4 parallel checks + eval advisory |
| `deploy-dev.yml` | Push to `dev` | Snapshot → dbt → SVs → agents → eval |
| `promote-qa.yml` | Manual | Pre-flight → deploy → eval (hard gate) |
| `promote-prod.yml` | Manual + approval | Snapshot → deploy → eval → auto-rollback |
| `rollback.yml` | Manual | Restore from snapshot |
| `daily_data_refresh.yml` | Cron (5am PST) | Generate data → dbt → sync DEV/QA |
| `dcm-deploy.yml` | Manual | Infrastructure provisioning |
| `sync_env_data.yml` | Manual | Cross-environment data sync |

### PR Validation: Fast Feedback

When you open a PR, four jobs run in parallel:

1. **Lint & Unit Tests** — `pytest` on smoke tests and template tests
2. **Validate Specs** — Render all agent specs for dev/QA/prod and check for schema errors
3. **dbt Quality Gate** — `dbt parse` to catch model issues before they reach Snowflake
4. **Validate Against Snowflake** — Dry-run semantic view and agent deployments against the live DEV environment

After all four pass, a fifth job runs the full evaluation suite against DEV. On PRs targeting `dev`, eval is **advisory** (`continue-on-error: true`) — it won't block the merge, but the results appear as a PR comment so reviewers can see the impact:

```yaml
# .github/workflows/validate-pr.yml (eval job)
agent-eval:
  name: Agent Evaluation (DEV)
  needs: [lint-and-unit, validate-specs, dbt-quality-gate, validate-snowflake]
  continue-on-error: ${{ github.base_ref == 'dev' }}
  steps:
    - name: Run agent evaluations
      run: python -m agent_management.run_ci_eval --env dev

    - name: Query eval summary
      if: always()
      run: >
        python agent-evaluation/scripts/eval_summary.py
        --env dev --run-names agent-evaluation/results/run_names.json

    - name: Comment PR with eval summary
      if: always()
      uses: actions/github-script@v7
      # ... posts markdown table to PR
```

### Dev Deploy: The Full Sequence

Pushing to `dev` triggers a five-stage pipeline:

1. **Snapshot** — Clone current agent and semantic view state (for rollback)
2. **Deploy Semantic Views** — Run dbt, then verify (or deploy) semantic views
3. **SV Evaluation Gate** — Check semantic view quality (advisory)
4. **Deploy Agents** — Render templates, execute `CREATE OR ALTER AGENT`
5. **Agent Evaluation** — Run full eval suite, upload results as artifacts

### Semantic Views: The Dual-Path Design

We support two modes for semantic views, controlled by a single config key:

```yaml
# In environments/dev.env.yml
semantic_views:
  source: dbt    # Options: "dbt" or "yaml"
```

- **`dbt` mode**: Semantic views are created by `dbt run` (as dbt models). The deploy script only *verifies* they exist — it doesn't deploy YAML.
- **`yaml` mode**: Semantic views are deployed from Jinja2 YAML templates via `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML`.

This matters because teams have different workflows. Some manage semantic views in dbt alongside their data models. Others prefer standalone YAML definitions. The framework supports both without code changes — just flip the config key.

```python
# agent_management/deploy_semantic_views.py (core logic)
def main():
    config = load_env_config(args.env)
    schema_fqn = get_semantic_schema(config)
    source = get_sv_source(config)

    if source == "dbt":
        # Verify semantic views exist in Snowflake (created by dbt run)
        sys.exit(run_dbt_path(config, schema_fqn, args.dry_run))
    else:
        # Render Jinja2 templates and deploy via SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML
        sys.exit(run_yaml_path(config, schema_fqn, args.view, args.dry_run))
```

### Production Deploy: Approval + Auto-Rollback

The production workflow adds two critical safeguards:

**GitHub environment approval gate** — The `production` environment requires manual approval before the workflow can proceed. This is a human checkpoint: someone reviews the changes before they touch prod.

**Automatic rollback on eval failure** — If the post-deploy evaluation fails, the pipeline automatically restores from the pre-deploy snapshot:

```yaml
# .github/workflows/promote-prod.yml
auto-rollback:
  name: Auto-Rollback on Eval Failure
  needs: [eval-gate, snapshot]
  if: failure() && needs.eval-gate.result == 'failure'
  steps:
    - name: Rollback to pre-deploy snapshot
      run: |
        TIMESTAMP="${{ needs.snapshot.outputs.snapshot_timestamp }}"
        python -m agent_management.rollback --env prod --timestamp "$TIMESTAMP" --target all
```

No manual intervention needed. If eval fails, prod is restored to its pre-deploy state and the team is notified via the failed workflow.

---

## The Evaluation Framework

This is where it gets interesting. Evaluating an AI agent isn't like running unit tests — the answers are non-deterministic, the ground truth changes as data updates, and you need to test across multiple domains simultaneously.

### Dynamic Ground Truth

Static ground truth goes stale. If your eval question asks "What was total revenue last season?" and the answer is hardcoded as "$4.2M," the eval breaks the moment new data loads.

We solve this with **validation queries** — SQL that runs at eval time to generate fresh ground truth:

```yaml
# agent-evaluation/datasets/resort_executive_eval.yaml
questions:
  - question: "What was our total ticket revenue for the most recent complete season?"
    expected_tools: ["DailySummaryKPIs", "RevenueAnalytics"]
    category: revenue
    test_type: in_scope
    validation_query: |
      WITH current_season AS (
        SELECT SKI_SEASON FROM {{ eval.source_database }}.MARTS.DIM_DATE
        WHERE FULL_DATE = CURRENT_DATE()
      ),
      most_recent_complete AS (
        SELECT MAX(SKI_SEASON) AS season FROM {{ eval.source_database }}.MARTS.DIM_DATE
        WHERE SKI_SEASON < (SELECT SKI_SEASON FROM current_season)
      )
      SELECT d.SKI_SEASON AS season,
             ROUND(SUM(t.PURCHASE_AMOUNT), 2) AS total_revenue,
             COUNT(*) AS ticket_count,
             ROUND(AVG(t.PURCHASE_AMOUNT), 2) AS avg_price
      FROM {{ eval.source_database }}.MARTS.FACT_TICKET_SALES t
      JOIN {{ eval.source_database }}.MARTS.DIM_DATE d
        ON t.PURCHASE_DATE_KEY = d.DATE_KEY
      WHERE d.SKI_SEASON = (SELECT season FROM most_recent_complete)
      GROUP BY d.SKI_SEASON
    answer_template: >-
      Total ticket revenue for the {season} season was approximately
      ${total_revenue:,.0f} from {ticket_count:,} tickets sold,
      with an average ticket price of ${avg_price:,.2f}.
```

The `validation_query` runs against the same data the agent queries. The `answer_template` is a Python format string that turns the query results into natural language. At eval time, the framework:

1. Renders the Jinja2 template (resolving `{{ eval.source_database }}`)
2. Executes the `validation_query` against Snowflake
3. Formats the result row into the `answer_template`
4. Uploads the question + generated ground truth as the evaluation dataset

This means the eval stays accurate regardless of data changes — it's always testing against the current state of the database.

### Parallel Execution

With multiple agents and 15+ questions each, sequential evaluation takes too long for CI. We run agent evaluations in parallel using Python's `ThreadPoolExecutor`:

```python
# agent_management/run_ci_eval.py
workers = min(args.max_parallel, len(prepared))
results: dict[str, tuple[int, str, str]] = {}

with ThreadPoolExecutor(max_workers=workers) as pool:
    futures = {}
    for agent_name, _, rendered_path in prepared:
        cmd = build_cmd(rendered_path, args)
        future = pool.submit(run_single_eval, agent_name, cmd)
        futures[future] = agent_name

    for future in as_completed(futures):
        agent_name, returncode, stdout, stderr = future.result()
        results[agent_name] = (returncode, stdout, stderr)
```

Each eval runs as a subprocess with `capture_output=True`, which prevents log interleaving — each agent's output is captured independently and printed sequentially after all evals complete.

### Threshold Gating

Each environment defines its own pass/fail thresholds:

| Environment | answer_correctness | logical_consistency | Behavior on failure |
|---|---|---|---|
| DEV | 0.60 | 0.60 | Advisory (CI continues) |
| QA | 0.65 | 0.65 | Hard gate (blocks promotion) |
| PROD | 0.70 | 0.70 | Hard gate + auto-rollback |

Dev thresholds are intentionally lenient — you want to iterate quickly without CI blocking every change. QA and prod get progressively stricter. The idea is that by the time an agent reaches prod, it's been evaluated three times with increasing rigor.

### Eval Summary in PR Comments

After evaluation, `eval_summary.py` queries the results from Snowflake and posts a markdown table directly on the PR:

```
## DEV Evaluation Summary

| Agent | Run | Score | Status |
|---|---|---|---|
| RESORT_EXECUTIVE_DEV | resort_executive_dev_eval_20260414_001241 | 72.3% | PASS |
| SKI_OPS_ASSISTANT_DEV | ski_ops_assistant_dev_eval_20260414_001241 | 66.7% | PASS |

Thresholds: answer_correctness ≥ 0.60 | Snowsight: [View Results](https://app.snowflake.com/...)
```

Reviewers see the quality impact of every PR without leaving GitHub.

---

## Lessons From Production

### Secrets vs. Variables in GitHub Actions

This one cost us a day. GitHub Actions **masks any value stored as a secret** everywhere in CI logs — including in URLs, file paths, and diagnostic output. We had our database name (`AM_SKI_RESORT_DEV`) stored as a secret, which meant every Snowsight URL in CI output rendered as:

```
https://app.snowflake.com/.../database/***/schema/AGENTS/agent/RESORT_EXECUTIVE_DEV
```

Useless. The fix: move non-sensitive values (database, warehouse, role) from `secrets.*` to `vars.*` (GitHub environment variables). Secrets are for credentials only.

```yaml
# Before (masked in logs):
SNOWFLAKE_DATABASE: ${{ secrets.SNOWFLAKE_DATABASE }}

# After (visible in logs):
SNOWFLAKE_DATABASE: ${{ vars.SNOWFLAKE_DATABASE }}
```

### Eval Race Conditions

When multiple CI runs execute concurrently (common with active PRs), the eval summary script can query the wrong evaluation run. Our `find_latest_run()` function queries Snowflake for the most recent eval — but "most recent" might belong to a different workflow that's still in progress.

The fix: `run_ci_eval.py` extracts the exact run name from each eval's stdout and writes it to `run_names.json`. The summary script accepts `--run-names` to query those specific runs instead of guessing "latest."

### LLM Variance and Threshold Flakiness

Agent eval scores fluctuate between runs. The same agent answering the same questions can score 0.599 one run and 0.667 the next. With a threshold of 0.60, that means the eval gate is non-deterministic.

We handle this two ways: (1) keep dev thresholds slightly below what we expect the agent to achieve consistently, and (2) make dev eval advisory rather than blocking. The hard gates live in QA and prod where thresholds are set based on observed performance baselines, not aspirational targets.

### Single-Account Multi-Environment

All three environments (dev, QA, prod) live in one Snowflake account. Isolation comes from:

- **Naming conventions**: `AM_SKI_RESORT_DEV`, `AM_SKI_RESORT_QA`, `AM_SKI_RESORT` (prod)
- **Role-based access**: `AM_DEPLOY_ROLE_DEV` can only touch dev objects
- **Agent suffixes**: `RESORT_EXECUTIVE_DEV`, `RESORT_EXECUTIVE_QA`, `RESORT_EXECUTIVE`

This keeps things simple for a single team. Multi-account deployment (one Snowflake account per environment) is supported by changing the account in each env config — the framework doesn't care.

---

## What's Next: Agent Versioning

Snowflake is adding native agent versioning — `CREATE AGENT VERSION`, semantic versioning, and the ability to pin consumers to specific versions.

When this lands, our framework gets simpler in a few key ways:

- **Rollback becomes version-based** instead of snapshot-based. Instead of cloning and restoring, you point to a previous version.
- **Canary deployments** become possible — route a percentage of traffic to a new version while the old one continues serving.
- **Promotion carries a version tag** through dev → QA → prod, making it trivially auditable which version is running where.

The evaluation framework is version-agnostic — it tests whatever agent is currently deployed. So the promotion flow stays the same: deploy, evaluate, gate, promote. Versioning adds precision without changing the process.

---

## Getting Started

If you want to build something similar, here's the minimum viable setup:

1. **One agent spec** with Jinja2 placeholders (`agents/specs/my_agent.yml`)
2. **One environment config** (`environments/dev.env.yml`)
3. **One eval dataset** with at least 5 questions and validation queries
4. **Two workflows**: `validate-pr.yml` (PR checks) and `deploy-dev.yml` (deploy on push)
5. **GitHub environments** with `vars.*` for non-sensitive values and `secrets.*` for credentials only

Start with dev only. Add QA when you have stable eval baselines. Add prod with approval gates and auto-rollback when you're confident in the eval framework.

The key insight is that agent CI/CD isn't fundamentally different from application CI/CD — it's deploy, test, gate, promote. The nuance is in *what* you test (non-deterministic LLM output against dynamic ground truth) and *how* you test it (Snowflake's built-in evaluation functions with score thresholds).

The framework is designed to be forked and adapted. The ski resort domain is just a vehicle — swap in your own agents, semantic views, and evaluation questions, and the pipeline works the same way.

---

*Built with Snowflake Cortex Agents, Cortex Analyst semantic views, dbt, DCM, and GitHub Actions.*
