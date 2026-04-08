#!/usr/bin/env bash
set -euo pipefail

#
# Creates the 4 GitHub Environments required by the CI/CD workflows.
#
# What this creates:
#   4 environments in the GitHub repo Settings > Environments:
#
#   DEV         - Used by deploy-dev.yml
#                 No protection rules (auto-deploys on push to main)
#                 Secrets: SNOWFLAKE_WAREHOUSE, SNOWFLAKE_ROLE, SNOWFLAKE_DATABASE
#
#   QA          - Used by promote-qa.yml
#                 No protection rules
#                 Secrets: SNOWFLAKE_WAREHOUSE, SNOWFLAKE_ROLE, SNOWFLAKE_DATABASE
#
#   PROD        - Used by promote-prod.yml (deploy + eval jobs), daily_data_refresh.yml
#                 No protection rules (approval handled by 'production' env)
#                 Secrets: SNOWFLAKE_WAREHOUSE, SNOWFLAKE_ROLE, SNOWFLAKE_DATABASE
#
#   production  - Used by promote-prod.yml pre-flight job as an approval gate
#                 HAS required reviewer: repo owner must approve before prod deploy
#                 Secrets: same as PROD (SNOWFLAKE_WAREHOUSE, SNOWFLAKE_ROLE, SNOWFLAKE_DATABASE)
#
# After creating environments, run setup_github_secrets.sh to populate secrets.
#
# Prerequisites:
#   - gh CLI installed and authenticated (`gh auth login`)
#   - The authenticated user must be a repo admin
#
# Usage:
#   .github/scripts/setup_github_environments.sh
#

REPO="${GH_REPO:-Jeremy-Demlow/AgentMangement}"

echo "=== GitHub Environment Setup ==="
echo "Repo: $REPO"
echo ""

if ! command -v gh &> /dev/null; then
  echo "ERROR: gh CLI not found. Install: https://cli.github.com"
  exit 1
fi

OWNER=$(echo "$REPO" | cut -d'/' -f1)
GH_USER_ID=$(gh api "users/$OWNER" --jq '.id' 2>/dev/null || echo "")

if [ -z "$GH_USER_ID" ]; then
  echo "ERROR: Could not resolve GitHub user ID for $OWNER"
  exit 1
fi

echo "GitHub user: $OWNER (id: $GH_USER_ID)"
echo ""

echo "Creating environment: DEV (no protection rules)..."
echo '{}' | gh api "repos/$REPO/environments/DEV" --method PUT --input - > /dev/null

echo "Creating environment: QA (no protection rules)..."
echo '{}' | gh api "repos/$REPO/environments/QA" --method PUT --input - > /dev/null

echo "Creating environment: PROD (no protection rules)..."
echo '{}' | gh api "repos/$REPO/environments/PROD" --method PUT --input - > /dev/null

echo "Creating environment: production (with required reviewer: $OWNER)..."
echo "{\"reviewers\":[{\"type\":\"User\",\"id\":$GH_USER_ID}]}" \
  | gh api "repos/$REPO/environments/production" --method PUT --input - > /dev/null

echo ""
echo "=== Done: 4 environments created ==="
echo ""
echo "  DEV         — deploy-dev.yml (no approval)"
echo "  QA          — promote-qa.yml (no approval)"
echo "  PROD        — promote-prod.yml, daily_data_refresh.yml (no approval)"
echo "  production  — promote-prod.yml pre-flight gate (requires $OWNER approval)"
echo ""
echo "Next: run setup_github_secrets.sh to set repo + environment secrets"
echo ""
echo "Verify at: https://github.com/$REPO/settings/environments"
