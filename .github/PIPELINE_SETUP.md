# Daily Data Pipeline Setup

This guide explains how to set up the automated daily data refresh pipeline.

## Overview

The pipeline runs daily at **5am PST** and uses the **official Snowflake CLI GitHub Action** ([snowflakedb/snowflake-cli-action](https://github.com/snowflakedb/snowflake-cli-action)):

1. 🔧 Sets up Snowflake CLI (official action)
2. 📊 Generates incremental ski resort data for the current date
3. 🏗️ Runs DBT fact tables (incremental)
4. 🎯 Refreshes semantic views
5. ✅ Verifies the data was loaded correctly

## GitHub Actions Secrets Required

Go to **Settings → Secrets and variables → Actions** in your repository and add:

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `SNOWFLAKE_ACCOUNT` | Snowflake account identifier | `trb65519` |
| `SNOWFLAKE_USER` | Service account username | `jd_service_account_admin` |
| `SNOWFLAKE_PASSWORD` | Password or PAT token | `eyJ...` |
| `SNOWFLAKE_WAREHOUSE` | Compute warehouse | `COMPUTE_WH` |
| `SNOWFLAKE_ROLE` | Role with write access | `SYSADMIN` |

## Setting Up Secrets

### Option 1: Via GitHub UI
1. Go to your repository on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add each secret listed above

### Option 2: Via GitHub CLI
```bash
# Install gh CLI if needed: brew install gh

gh secret set SNOWFLAKE_ACCOUNT --body "trb65519"
gh secret set SNOWFLAKE_USER --body "jd_service_account_admin"
gh secret set SNOWFLAKE_PASSWORD --body "your-pat-or-password"
gh secret set SNOWFLAKE_WAREHOUSE --body "COMPUTE_WH"
gh secret set SNOWFLAKE_ROLE --body "SYSADMIN"
```

## Manual Trigger

You can manually run the pipeline anytime:

### Via GitHub UI
1. Go to **Actions** → **Daily Data Refresh**
2. Click **Run workflow**
3. Optionally configure:
   - **Days**: Number of days to generate (default: 1)
   - **Full refresh**: Force rebuild of fact tables

### Via GitHub CLI
```bash
# Run with defaults
gh workflow run daily_data_refresh.yml

# Run with options
gh workflow run daily_data_refresh.yml \
  -f days=3 \
  -f full_refresh=true
```

## Schedule

- **Cron**: `0 13 * * *` (1pm UTC = 5am PST)
- **Timezone Note**: GitHub Actions uses UTC
  - PST (Nov-Mar): UTC-8 → 5am PST = 1pm UTC
  - PDT (Mar-Nov): UTC-7 → 5am PDT = 12pm UTC

To change the schedule, edit `.github/workflows/daily_data_refresh.yml`:
```yaml
on:
  schedule:
    - cron: '0 13 * * *'  # Change this
```

## Monitoring

### Check Run Status
- Go to **Actions** tab in GitHub
- View recent workflow runs
- Check logs for any failures

### Failure Notifications
When the pipeline fails, it automatically:
1. Creates a GitHub Issue with `bug` and `data-pipeline` labels
2. Links to the failed run for debugging

### View Job Summary
Each successful run creates a summary with:
- Timestamp
- Steps completed
- Data verification results

## Troubleshooting

### Common Issues

**Authentication Failed**
```
Error: 250001 (08001): Failed to connect to DB
```
→ Check `SNOWFLAKE_PASSWORD` secret is correct

**Permission Denied**
```
Error: SQL access control error
```
→ Verify `SNOWFLAKE_ROLE` has write access to `SKI_RESORT_DB.RAW`

**DBT Model Fails**
```
SQL compilation error: cannot change column type
```
→ Run with `full_refresh=true` to rebuild tables

### Debug Locally
```bash
# Test data generation
cd data_generation
python generate_daily_increment.py --date $(date +%Y-%m-%d) --days 1

# Test DBT
cd dbt_ski_resort
dbt run --select "marts.facts" --full-refresh
dbt run --select "marts.semantic"
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions                            │
│                    (5am PST Daily)                           │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  0. snowflakedb/snowflake-cli-action@v2.0                    │
│     - Official Snowflake CLI installation                    │
│     - Isolated, no dependency conflicts                      │
│     → snow connection test -x                                │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  1. generate_daily_increment.py                              │
│     - Weather, Visitors, Lift Scans                          │
│     - F&B, Rentals, Tickets                                  │
│     - Lessons, Incidents, Feedback                           │
│     → SKI_RESORT_DB.RAW.*                                    │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  2. dbt run --select "marts.facts"                          │
│     - 13 incremental fact tables                             │
│     → SKI_RESORT_DB.MARTS.FACT_*                             │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  3. dbt run --select "marts.semantic"                       │
│     - 11 semantic views                                      │
│     → SKI_RESORT_DB.SEMANTIC.SEM_*                           │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  4. snow sql -q "..." -x (verify with official CLI)          │
│     - Verify data loaded correctly                           │
│     - Show recent visitor counts                             │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Ready for Cortex Agent Queries!                             │
│  - Slack Bot                                                 │
│  - Snowflake Intelligence                                    │
│  - Email Alerts                                              │
└─────────────────────────────────────────────────────────────┘
```

## Why Official Snowflake CLI Action?

Using [snowflakedb/snowflake-cli-action](https://github.com/snowflakedb/snowflake-cli-action):

- ✅ **Official & Maintained** - By Snowflake
- ✅ **Isolated Installation** - No dependency conflicts
- ✅ **Automatic Config** - Sets up `~/.snowflake/` automatically
- ✅ **Version Pinning** - Specify exact CLI version
- ✅ **OIDC Support** - Passwordless auth option (v3.11+)

## Cost Considerations

- **GitHub Actions**: Free for public repos, 2,000 min/month for private
- **Snowflake Compute**: ~30 seconds of warehouse time per run
- **Storage**: ~1MB per day of incremental data

## Next Steps

1. Set up the secrets in GitHub
2. Run the workflow manually to test
3. Monitor the first few automated runs
4. Consider adding Slack notifications for failures
