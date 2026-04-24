# v0 Baseline — Pre-Framework Best Practices

## Source
- commit: main@8979658 (post PR #17)
- agent spec version: 1.1.0
- date captured: 2026-04-24

## Last eval scores (DEV)

From pipeline run 24863881412:

| Agent | answer_correctness | logical_consistency |
|---|---|---|
| resort_executive | 0.777 | 0.867 |
| ski_ops_assistant | 0.734 | 0.866 |

## SV eval scores (DEV)

All 11/11 PASS:
- SEM_CUSTOMER_BEHAVIOR: 80.0% (4.0/5)
- SEM_CUSTOMER_SATISFACTION: 100.0% (5.0/5)
- SEM_DAILY_SUMMARY: 100.0% (5.0/5)
- SEM_LESSONS_ANALYTICS: 100.0% (5.0/5)
- SEM_MARKETING_ANALYTICS: 80.0% (4.0/5)
- SEM_OPERATIONS: 100.0% (4.0/4)
- SEM_PASSHOLDER_ANALYTICS: 80.0% (4.0/5)
- SEM_REVENUE: 100.0% (5.0/5)
- SEM_SAFETY_INCIDENTS: 75.0% (3.0/4)
- SEM_STAFFING_ANALYTICS: 80.0% (4.0/5)
- SEM_WEATHER_ANALYTICS: 80.0% (4.0/5)

## Weakest answer_correctness questions (targets for VQR expansion)

### resort_executive (score 0.00-0.33)
- 0.00 "How did ski school perform last season in terms of lessons and revenue"
- 0.00 "What was the average staffing coverage ratio last season and how many understaffed shifts occurred"
- 0.33 "How many season passes were sold for last season and what was the total pass revenue"
- 0.33 "What are the largest customer segments at the resort by number of customers"
- 0.33 "How does the current season's ticket revenue compare to the same point last season"
- 0.33 "What was the average lift wait time last season and how many total scans were recorded"
- 0.33 "How many safety incidents occurred last season and what was the average patrol response time"
- 0.33 "What was our average NPS score and customer rating last season"
- 0.33 "How did food and beverage revenue perform last season"

### ski_ops_assistant (score 0.00-0.33)
- 0.00 "Which departments had the most understaffed shifts last season"
- 0.00 "What were the most common incident types last season"
- 0.33 "What were the wind conditions like last season? How many high wind days"
- 0.33 "Give me a daily operations summary for the most recent day with data"
- 0.33 "How many safety incidents occurred last season and what was the average patrol response time"
- 0.33 "How much total snowfall did we get last season and how many powder days"

## Baseline agent config files
- [agent_config.yml](agent_config.yml) — snapshot of resort_executive spec at v1.1.0
- ../../../ski_ops_assistant/versions/v0-baseline/agent_config.yml — snapshot of ski_ops spec at v1.1.0
