#!/usr/bin/env bash
set -euo pipefail

#
# Sets all required GitHub Actions secrets for the AgentManagement repo.
#
# Architecture:
#   4 REPO-LEVEL secrets (shared across all environments):
#     SNOWFLAKE_ACCOUNT         -> Snowflake account identifier
#     SNOWFLAKE_USER            -> Snowflake user for CI
#     SNOWFLAKE_PRIVATE_KEY     -> PEM private key for JWT auth
#     SNOWFLAKE_PRIVATE_KEY_RAW -> Same key (required by DCM reusable actions)
#
#   3 ENVIRONMENT-LEVEL variables (per DEV/QA/PROD/production):
#     SNOWFLAKE_WAREHOUSE       -> Environment-specific warehouse
#     SNOWFLAKE_ROLE            -> Environment-specific deploy role
#     SNOWFLAKE_DATABASE        -> Environment-specific database
#
#   Variables (not secrets) are used for non-sensitive values so they
#   appear in CI logs unmasked — critical for clickable Snowsight URLs.
#
#   All workflows use key-pair (JWT) auth. No password needed.
#
# Prerequisites:
#   - gh CLI installed and authenticated (`gh auth login`)
#   - Private key file at the path below (or override with SNOWFLAKE_KEY_PATH)
#   - GitHub environments already created (run setup_github_environments.sh first)
#
# Usage:
#   .github/scripts/setup_github_secrets.sh
#

REPO="${GH_REPO:-Jeremy-Demlow/AgentMangement}"
ACCOUNT="${SNOWFLAKE_ACCOUNT:-trb65519}"
USER="${SNOWFLAKE_USER:-JDEMLOW}"
KEY_PATH="${SNOWFLAKE_KEY_PATH:-$HOME/.snowflake/keys/snowflake_tf_key.p8}"

echo "=== GitHub Actions Secret Setup ==="
echo "Repo:     $REPO"
echo "Account:  $ACCOUNT"
echo "User:     $USER"
echo "Key file: $KEY_PATH"
echo ""

if ! command -v gh &> /dev/null; then
  echo "ERROR: gh CLI not found. Install: https://cli.github.com"
  exit 1
fi

if ! gh auth status &> /dev/null; then
  echo "ERROR: gh CLI not authenticated. Run: gh auth login"
  exit 1
fi

if [ ! -f "$KEY_PATH" ]; then
  echo "ERROR: Private key not found at $KEY_PATH"
  echo "  Generate one with:"
  echo "    openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out snowflake_tf_key.p8 -nocrypt"
  exit 1
fi

echo "--- Repo-level secrets (4) ---"

echo "Setting SNOWFLAKE_ACCOUNT..."
echo "$ACCOUNT" | gh secret set SNOWFLAKE_ACCOUNT -R "$REPO"

echo "Setting SNOWFLAKE_USER..."
echo "$USER" | gh secret set SNOWFLAKE_USER -R "$REPO"

echo "Setting SNOWFLAKE_PRIVATE_KEY..."
gh secret set SNOWFLAKE_PRIVATE_KEY -R "$REPO" < "$KEY_PATH"

echo "Setting SNOWFLAKE_PRIVATE_KEY_RAW..."
gh secret set SNOWFLAKE_PRIVATE_KEY_RAW -R "$REPO" < "$KEY_PATH"

echo ""
echo "--- Environment-level variables (3 per env) ---"

declare -A ENV_WH=(
  [DEV]="AM_SKI_RESORT_WH_DEV"
  [QA]="AM_SKI_RESORT_WH_QA"
  [PROD]="AM_SKI_RESORT_WH"
  [production]="AM_SKI_RESORT_WH"
)
declare -A ENV_ROLE=(
  [DEV]="AM_DEPLOY_ROLE_DEV"
  [QA]="AM_DEPLOY_ROLE_QA"
  [PROD]="AM_DEPLOY_ROLE"
  [production]="AM_DEPLOY_ROLE"
)
declare -A ENV_DB=(
  [DEV]="AM_SKI_RESORT_DEV"
  [QA]="AM_SKI_RESORT_QA"
  [PROD]="AM_SKI_RESORT"
  [production]="AM_SKI_RESORT"
)

for ENV_NAME in DEV QA PROD production; do
  echo ""
  echo "Setting variables for environment: $ENV_NAME"
  echo "  SNOWFLAKE_WAREHOUSE = ${ENV_WH[$ENV_NAME]}"
  echo "  SNOWFLAKE_ROLE      = ${ENV_ROLE[$ENV_NAME]}"
  echo "  SNOWFLAKE_DATABASE  = ${ENV_DB[$ENV_NAME]}"

  gh variable set SNOWFLAKE_WAREHOUSE -R "$REPO" --env "$ENV_NAME" --body "${ENV_WH[$ENV_NAME]}"
  gh variable set SNOWFLAKE_ROLE -R "$REPO" --env "$ENV_NAME" --body "${ENV_ROLE[$ENV_NAME]}"
  gh variable set SNOWFLAKE_DATABASE -R "$REPO" --env "$ENV_NAME" --body "${ENV_DB[$ENV_NAME]}"
done

echo ""
echo "=== Done: 4 repo secrets + 12 environment variables (3 x 4 envs) ==="
echo ""
echo "Verify with:"
echo "  gh secret list -R $REPO"
echo "  gh variable list -R $REPO --env DEV"
echo "  gh variable list -R $REPO --env QA"
echo "  gh variable list -R $REPO --env PROD"
echo "  gh variable list -R $REPO --env production"
echo ""
echo "All workflows use key-pair (JWT) auth. No password needed."
