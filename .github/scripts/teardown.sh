#!/usr/bin/env bash
set -euo pipefail

#
# Removes all GitHub Actions secrets and environments created by the setup scripts.
# Useful for resetting or cleaning up before re-running setup.
#
# What this removes:
#   Secrets:      SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PRIVATE_KEY,
#                 SNOWFLAKE_PRIVATE_KEY_RAW, SNOWFLAKE_WAREHOUSE, SNOWFLAKE_ROLE
#   Environments: DEV, QA, PROD, production
#
# Usage:
#   .github/scripts/teardown.sh
#

REPO="${GH_REPO:-Jeremy-Demlow/AgentMangement}"

echo "=== Teardown: Removing GitHub secrets and environments ==="
echo "Repo: $REPO"
echo ""

SECRETS=(
  SNOWFLAKE_ACCOUNT
  SNOWFLAKE_USER
  SNOWFLAKE_PRIVATE_KEY
  SNOWFLAKE_PRIVATE_KEY_RAW
  SNOWFLAKE_WAREHOUSE
  SNOWFLAKE_ROLE
)

echo "--- Removing secrets ---"
for secret in "${SECRETS[@]}"; do
  echo "  Removing $secret..."
  gh secret delete "$secret" -R "$REPO" 2>/dev/null || echo "    (not found, skipping)"
done

ENVS=(DEV QA PROD production)

echo ""
echo "--- Removing environments ---"
for env in "${ENVS[@]}"; do
  echo "  Removing $env..."
  gh api "repos/$REPO/environments/$env" --method DELETE 2>/dev/null || echo "    (not found, skipping)"
done

echo ""
echo "=== Teardown complete ==="
echo "Verify: gh secret list -R $REPO"
echo "Verify: https://github.com/$REPO/settings/environments"
