#!/usr/bin/env bash
set -euo pipefail

#
# Removes all GitHub Actions secrets and environments created by the setup scripts.
# Useful for resetting or cleaning up before re-running setup.
#
# What this removes:
#   Repo secrets:  SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PRIVATE_KEY, SNOWFLAKE_PRIVATE_KEY_RAW
#   Env variables: SNOWFLAKE_WAREHOUSE, SNOWFLAKE_ROLE, SNOWFLAKE_DATABASE (per DEV/QA/PROD)
#   Environments:  DEV, QA, PROD
#
# Usage:
#   .github/scripts/teardown.sh
#

REPO="${GH_REPO:-Jeremy-Demlow/AgentMangement}"

echo "=== Teardown: Removing GitHub secrets and environments ==="
echo "Repo: $REPO"
echo ""

REPO_SECRETS=(
  SNOWFLAKE_ACCOUNT
  SNOWFLAKE_USER
  SNOWFLAKE_PRIVATE_KEY
  SNOWFLAKE_PRIVATE_KEY_RAW
)

echo "--- Removing repo-level secrets ---"
for secret in "${REPO_SECRETS[@]}"; do
  echo "  Removing $secret..."
  gh secret delete "$secret" -R "$REPO" 2>/dev/null || echo "    (not found, skipping)"
done

ENV_VARS=(SNOWFLAKE_WAREHOUSE SNOWFLAKE_ROLE SNOWFLAKE_DATABASE)
ENVS=(DEV QA PROD)

echo ""
echo "--- Removing environment-level variables ---"
for env in "${ENVS[@]}"; do
  for var in "${ENV_VARS[@]}"; do
    echo "  Removing $env/$var..."
    gh variable delete "$var" -R "$REPO" --env "$env" 2>/dev/null || echo "    (not found, skipping)"
  done
done

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
