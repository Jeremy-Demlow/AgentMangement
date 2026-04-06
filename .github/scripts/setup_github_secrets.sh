#!/usr/bin/env bash
set -euo pipefail

#
# Sets all required GitHub Actions secrets for the AgentManagement repo.
#
# What this creates:
#   6 repository-level secrets in GitHub Actions:
#     SNOWFLAKE_ACCOUNT        -> Your Snowflake account identifier
#     SNOWFLAKE_USER           -> The Snowflake user that CI runs as
#     SNOWFLAKE_PRIVATE_KEY    -> PEM private key for JWT auth (deploy/promote/validate/rollback)
#     SNOWFLAKE_PRIVATE_KEY_RAW-> Same key, separate name required by Snowflake DCM reusable actions
#     SNOWFLAKE_WAREHOUSE      -> Default warehouse for CI jobs
#     SNOWFLAKE_ROLE           -> Default role for CI jobs
#
#   All workflows use key-pair (JWT) auth. No password or PAT needed.
#
# Prerequisites:
#   - gh CLI installed and authenticated (`gh auth login`)
#   - Run from the repo root (or any dir — script uses -R flag)
#   - Private key file at the path below (or override with SNOWFLAKE_KEY_PATH)
#
# Usage:
#   .github/scripts/setup_github_secrets.sh
#
# To override defaults, set env vars before running:
#   SNOWFLAKE_KEY_PATH=~/.snowflake/keys/my_other_key.p8 \
#   GH_REPO=org/repo \
#     .github/scripts/setup_github_secrets.sh
#

REPO="${GH_REPO:-Jeremy-Demlow/AgentMangement}"
ACCOUNT="${SNOWFLAKE_ACCOUNT:-trb65519}"
USER="${SNOWFLAKE_USER:-JDEMLOW}"
WAREHOUSE="${SNOWFLAKE_WAREHOUSE:-AM_SKI_RESORT_WH_PROD}"
ROLE="${SNOWFLAKE_ROLE:-AM_DEPLOY_ROLE_PROD}"
KEY_PATH="${SNOWFLAKE_KEY_PATH:-$HOME/.snowflake/keys/snowflake_tf_key.p8}"

echo "=== GitHub Actions Secret Setup ==="
echo "Repo:      $REPO"
echo "Account:   $ACCOUNT"
echo "User:      $USER"
echo "Warehouse: $WAREHOUSE"
echo "Role:      $ROLE"
echo "Key file:  $KEY_PATH"
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

echo "Setting SNOWFLAKE_ACCOUNT..."
echo "$ACCOUNT" | gh secret set SNOWFLAKE_ACCOUNT -R "$REPO"

echo "Setting SNOWFLAKE_USER..."
echo "$USER" | gh secret set SNOWFLAKE_USER -R "$REPO"

echo "Setting SNOWFLAKE_PRIVATE_KEY (from $KEY_PATH)..."
gh secret set SNOWFLAKE_PRIVATE_KEY -R "$REPO" < "$KEY_PATH"

echo "Setting SNOWFLAKE_PRIVATE_KEY_RAW (same key, required by DCM actions)..."
gh secret set SNOWFLAKE_PRIVATE_KEY_RAW -R "$REPO" < "$KEY_PATH"

echo "Setting SNOWFLAKE_WAREHOUSE..."
echo "$WAREHOUSE" | gh secret set SNOWFLAKE_WAREHOUSE -R "$REPO"

echo "Setting SNOWFLAKE_ROLE..."
echo "$ROLE" | gh secret set SNOWFLAKE_ROLE -R "$REPO"

echo ""
echo "=== Done: 6 secrets set ==="
echo ""
echo "Verify with:  gh secret list -R $REPO"
echo ""
echo "All workflows use key-pair (JWT) auth. No password needed."
