# RESORT_EXECUTIVE Evaluation Dataset
# Agent: SADM_SKI_RESORT_DB.AGENTS.RESORT_EXECUTIVE
# Anchor: 2024-2025 ski season (Nov 2024 - Apr 2025)
# Metrics: answer_correctness, logical_consistency
# Created: 2026-04-01

## Questions and Ground Truth

| # | Target Tool | Question | Ground Truth |
|---|-------------|----------|-------------|
| 1 | DailySummaryKPIs / RevenueAnalytics | What was our total ticket revenue for the 2024-2025 ski season? | Total ticket revenue for the 2024-2025 season was approximately $2.62 million from 24,041 tickets sold, with an average ticket price of $108.94. |
| 2 | RevenueAnalytics | How did food and beverage revenue perform during the 2024-2025 season? | Food and beverage revenue for the 2024-2025 season was approximately $3.09 million from about 216,944 transactions. |
| 3 | RevenueAnalytics | What was the total rental revenue for the 2024-2025 ski season? | Total rental revenue for the 2024-2025 season was approximately $1.51 million from 27,770 rentals, with an average rental amount of $54.53. |
| 4 | WeatherAnalytics | How much total snowfall did we receive during the 2024-2025 season and how many powder days? | The resort received approximately 4,421.5 inches of total snowfall during the 2024-2025 season with 375 powder days. Average high temperature was 30.5°F and average low was 18°F. |
| 5 | LiftOperations | What was the average lift wait time for the 2024-2025 season and how many total scans were recorded? | Average lift wait time for the 2024-2025 season was 3.4 minutes with approximately 1.62 million total lift scans recorded. |
| 6 | LiftOperations | Which days of the week had the most lift activity during the 2024-2025 season? | Saturday was the busiest day with about 320,158 scans, followed by Sunday with 256,433 scans and Friday with 219,057 scans. |
| 7 | StaffingAnalytics | What was the average staffing coverage ratio during the 2024-2025 season and how many understaffed shifts occurred? | Average staffing coverage ratio was 0.97 (97%) during the 2024-2025 season with 48 understaffed shifts. |
| 8 | MarketingAnalytics | Which marketing campaign had the highest conversion rate during the 2024-2025 season? | High Performance Demo Days via Push Notification had the highest conversion rate at approximately 8.1%, followed by Weekend Warrior Flash Sale via SMS at about 6.8%, and Family Winter Getaway via Email at about 5.5%. |
| 9 | CustomerSatisfaction | What was our average NPS score and customer rating during the 2024-2025 season? | Average NPS score was 7.2 and average customer rating was 3.43 out of 5 during the 2024-2025 season, based on 1,553 feedback submissions. |
| 10 | SafetyIncidents | How many safety incidents occurred during the 2024-2025 season and what was the average patrol response time? | There were 528 safety incidents during the 2024-2025 season with an average severity score of 1.22 and average patrol response time of 8.9 minutes. |
| 11 | SkiSchoolAnalytics | How did ski school perform during the 2024-2025 season in terms of lessons and revenue? | Ski school delivered 4,957 lessons during the 2024-2025 season generating approximately $1.81 million in total lesson revenue. Average student rating was 4.24 out of 5. |
| 12 | PassholderAnalytics | How many season passes were sold for the 2024-2025 season and what was the total pass revenue? | 3,064 season passes were sold for the 2024-2025 season generating approximately $2.15 million in revenue, with an average pass price of $701.60. All 3,064 were renewals. |
| 13 | CustomerAnalytics | What are the largest customer segments at the resort by number of customers? | The largest customer segments are vacation_family (2,400 customers), weekend_warrior (2,000), day_tripper (1,600), local_pass_holder (1,200), and expert_skier (400). |

## Snowflake Objects
- **Table:** `SADM_SKI_RESORT_DB.AGENTS.RESORT_EXECUTIVE_EVAL_DATA`
- **Dataset:** `SADM_SKI_RESORT_DB.AGENTS.RESORT_EXECUTIVE_EVAL_DS_V3`
- **Config:** `@SADM_SKI_RESORT_DB.AGENTS.eval_config_stage/resort_executive_eval_config_v3.yaml`
- **Run:** `resort_executive_eval_20260401_v3`

## Results (v3 — 2026-04-01)

| Metric | Avg Score | High (≥0.8) | Low (<0.3) |
|--------|-----------|-------------|------------|
| answer_correctness | **92.4%** | 10/13 | 0/13 |
| logical_consistency | **87.2%** | 10/13 | 0/13 |

### Per-Question Scores (answer_correctness)

| # | Question | Score | Notes |
|---|----------|-------|-------|
| 1 | Total ticket revenue | 1.00 | Exact match |
| 2 | F&B revenue | 1.00 | Exact match |
| 3 | Rental revenue | 1.00 | Exact match |
| 4 | Total snowfall | 1.00 | 4,421 vs 4,421.5 — close enough |
| 5 | Avg lift wait time | 1.00 | Exact match |
| 6 | Busiest days of week | 1.00 | Exact match |
| 7 | Staffing coverage | 1.00 | 97.2% vs 97% — close enough |
| 8 | Marketing conversion rate | 0.67 | Correct data, missed channel (Push Notification) detail |
| 9 | NPS + customer rating | 1.00 | 7.24 vs 7.2 — close enough |
| 10 | Safety incidents | 1.00 | Exact match |
| 11 | Ski school performance | 0.67 | Correct data, minor rounding ($1,805,880 vs ~$1.81M) |
| 12 | Season pass sales | 0.67 | Correct data, missed "all renewals" detail |
| 13 | Customer segments | 1.00 | Exact match |

### Lessons Learned
- Approach A (YAML `dataset` section) is required for `answer_correctness` to work
- Approach B (`SYSTEM$CREATE_EVALUATION_DATASET`) had a ground truth mapping bug — scores showed 0%
- `logical_consistency` works with either approach (no ground truth needed)
- Questions scoring 0.67 had correct core data but missed secondary details from ground truth
