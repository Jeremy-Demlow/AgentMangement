#!/usr/bin/env bash
set -euo pipefail

#
# Runs the deploy-dev workflow steps locally against your real Snowflake account.
# This simulates what GitHub Actions does, step by step, so you can catch errors
# before pushing.
#
# Prerequisites:
#   - Python 3.11 with: pyyaml jinja2 snowflake-connector-python cryptography requests
#   - dbt-snowflake installed
#   - Private key at ~/.snowflake/keys/snowflake_tf_key.p8
#
# Usage:
#   .github/scripts/test_workflow_locally.sh          # run all steps
#   .github/scripts/test_workflow_locally.sh snapshot  # run one step
#
# Steps: snapshot, dbt, deploy-svs, sv-eval, deploy-agents, agent-eval, compute-metrics
#

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

PYTHON="${PYTHON:-python3}"
DBT="${DBT:-dbt}"
TARGET_ENV="${TARGET_ENV:-dev}"
STEP="${1:-all}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

export SNOWFLAKE_ACCOUNT="${SNOWFLAKE_ACCOUNT:-trb65519}"
export SNOWFLAKE_USER="${SNOWFLAKE_USER:-JDEMLOW}"
export SNOWFLAKE_PRIVATE_KEY_PATH="${SNOWFLAKE_PRIVATE_KEY_PATH:-$HOME/.snowflake/keys/snowflake_tf_key.p8}"

read -r DEFAULT_DB DEFAULT_WH DEFAULT_ROLE < <(
  $PYTHON -c "
import yaml, sys
with open('project.yml') as f:
    cfg = yaml.safe_load(f)
env = cfg.get('environments', {}).get('$TARGET_ENV')
if not env:
    print('Unknown env: $TARGET_ENV', file=sys.stderr)
    sys.exit(1)
print(env['database'], env['warehouse'], env['role'])
"
)

export SNOWFLAKE_WAREHOUSE="$DEFAULT_WH"
export SNOWFLAKE_ROLE="$DEFAULT_ROLE"
export SNOWFLAKE_DATABASE="$DEFAULT_DB"
export PYTHONPATH="$REPO_ROOT"

echo -e "${YELLOW}Environment: $TARGET_ENV | DB: $SNOWFLAKE_DATABASE | WH: $SNOWFLAKE_WAREHOUSE | Role: $SNOWFLAKE_ROLE${NC}"

pass_count=0
fail_count=0
skip_count=0

run_step() {
    local name="$1"
    shift
    echo ""
    echo -e "${YELLOW}━━━ $name ━━━${NC}"
    if "$@"; then
        echo -e "${GREEN}✓ $name${NC}"
        pass_count=$((pass_count + 1))
    else
        echo -e "${RED}✗ $name (exit $?)${NC}"
        fail_count=$((fail_count + 1))
    fi
}

should_run() {
    [[ "$STEP" == "all" || "$STEP" == "$1" ]]
}

# ── Step 1: Snapshot ──────────────────────────────────────────────────────────
if should_run "snapshot"; then
    run_step "snapshot_state --env $TARGET_ENV" \
        $PYTHON -m agent_management.snapshot_state --env "$TARGET_ENV"
fi

# ── Step 2: dbt build ────────────────────────────────────────────────────────
if should_run "dbt"; then
    if [ -f "dbt_ski_resort/dbt_project.yml" ]; then
        run_step "dbt deps" \
            $DBT deps --project-dir dbt_ski_resort --profiles-dir dbt_ski_resort
        run_step "dbt run (facts)" \
            $DBT run --project-dir dbt_ski_resort --profiles-dir dbt_ski_resort \
                --target "$TARGET_ENV" --select "+marts.facts"
        run_step "dbt run (semantic)" \
            $DBT run --project-dir dbt_ski_resort --profiles-dir dbt_ski_resort \
                --target "$TARGET_ENV" --select "marts.semantic"
    else
        echo -e "${YELLOW}SKIP: dbt_ski_resort/dbt_project.yml not found${NC}"
        skip_count=$((skip_count + 1))
    fi
fi

# ── Step 3: Deploy semantic views ────────────────────────────────────────────
if should_run "deploy-svs"; then
    run_step "deploy_semantic_views --env $TARGET_ENV" \
        $PYTHON -m agent_management.deploy_semantic_views --env "$TARGET_ENV"
fi

# ── Step 4: SV eval gate ─────────────────────────────────────────────────────
if should_run "sv-eval"; then
    run_step "run_sv_eval --env $TARGET_ENV (dry-run)" \
        $PYTHON -m agent_management.run_sv_eval --env "$TARGET_ENV" --dry-run || true
fi

# ── Step 5: Deploy agents ────────────────────────────────────────────────────
if should_run "deploy-agents"; then
    run_step "deploy_agents --env $TARGET_ENV" \
        $PYTHON -m agent_management.deploy_agents --env "$TARGET_ENV"
fi

# ── Step 6: Agent evaluations ────────────────────────────────────────────────
if should_run "agent-eval"; then
    for config in agent-evaluation/configs/*.yaml; do
        run_step "run_eval $(basename "$config")" \
            $PYTHON agent-evaluation/scripts/run_eval.py "$config" --env "$TARGET_ENV" || true
    done
fi

# ── Step 7: Compute metrics ──────────────────────────────────────────────────
if should_run "compute-metrics"; then
    run_step "compute_metrics --env $TARGET_ENV" \
        $PYTHON -m agent_management.compute_metrics --env "$TARGET_ENV" \
            --results-dir agent-evaluation/results/
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "  ${GREEN}Passed: $pass_count${NC}  ${RED}Failed: $fail_count${NC}  ${YELLOW}Skipped: $skip_count${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$fail_count" -gt 0 ]; then
    echo -e "${RED}Fix failures above before pushing.${NC}"
    exit 1
fi
