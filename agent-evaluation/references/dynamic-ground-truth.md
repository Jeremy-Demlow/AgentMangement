# Dynamic Ground Truth via `validation_query`

## Problem

Static ground truth (e.g., "Total ticket revenue for the 2024-2025 season was $2.62M") breaks when:
- New data is loaded (next season begins)
- Historical data is corrected
- Questions reference relative time ("current season", "most recent")
- You want YoY/WoW analysis where the comparison window shifts

## Solution: `validation_query` as Primary Ground Truth Source

Each question in the dataset YAML can include:

```yaml
- question: "What was our total ticket revenue for the most recent complete season?"
  validation_query: |
    SELECT ROUND(SUM(t.PURCHASE_AMOUNT), 2) AS total_revenue,
           COUNT(*) AS ticket_count,
           d.SKI_SEASON AS season
    FROM SADM_SKI_RESORT_DB.MARTS.FACT_TICKET_SALES t
    JOIN SADM_SKI_RESORT_DB.MARTS.DIM_DATE d ON t.PURCHASE_DATE_KEY = d.DATE_KEY
    WHERE d.SKI_SEASON = (
      SELECT MAX(SKI_SEASON) FROM SADM_SKI_RESORT_DB.MARTS.DIM_DATE
      WHERE FULL_DATE < CURRENT_DATE()
      AND SKI_SEASON < (
        SELECT SKI_SEASON FROM SADM_SKI_RESORT_DB.MARTS.DIM_DATE
        WHERE FULL_DATE = CURRENT_DATE()
      )
    )
    GROUP BY d.SKI_SEASON
  answer_template: >-
    Total ticket revenue for the {season} season was approximately
    ${total_revenue:,.0f} from {ticket_count:,} tickets sold.
  ground_truth: ""
```

### How It Works

1. **At eval time**, `run_eval.py` executes each `validation_query` against Snowflake
2. The query returns column names and values (e.g., `total_revenue=2619109`, `ticket_count=24041`, `season=2024-2025`)
3. Those values are substituted into `answer_template` using Python format strings
4. The formatted string becomes the `ground_truth` for that question
5. If `validation_query` is empty or fails, falls back to the static `ground_truth` field

### Field Hierarchy

| Priority | Field | When Used |
|----------|-------|-----------|
| 1 | `validation_query` + `answer_template` | Dynamic ground truth — **preferred for all data questions** |
| 2 | `ground_truth` (static) | Fallback when no validation_query, or for boundary/negative tests |

## Question Design Patterns

### Pattern 1: Current Season Totals

Use relative time references so the question stays valid across seasons.

```yaml
- question: "What was our total ticket revenue for the most recent complete season?"
  validation_query: |
    WITH current_season AS (
      SELECT SKI_SEASON FROM SADM_SKI_RESORT_DB.MARTS.DIM_DATE
      WHERE FULL_DATE = CURRENT_DATE()
    ),
    most_recent_complete AS (
      SELECT MAX(SKI_SEASON) AS season
      FROM SADM_SKI_RESORT_DB.MARTS.DIM_DATE
      WHERE SKI_SEASON < (SELECT SKI_SEASON FROM current_season)
    )
    SELECT d.SKI_SEASON AS season,
           ROUND(SUM(t.PURCHASE_AMOUNT), 2) AS total_revenue,
           COUNT(*) AS ticket_count,
           ROUND(AVG(t.PURCHASE_AMOUNT), 2) AS avg_price
    FROM SADM_SKI_RESORT_DB.MARTS.FACT_TICKET_SALES t
    JOIN SADM_SKI_RESORT_DB.MARTS.DIM_DATE d ON t.PURCHASE_DATE_KEY = d.DATE_KEY
    WHERE d.SKI_SEASON = (SELECT season FROM most_recent_complete)
    GROUP BY d.SKI_SEASON
  answer_template: >-
    Total ticket revenue for the {season} season was approximately
    ${total_revenue:,.0f} from {ticket_count:,} tickets sold,
    with an average ticket price of ${avg_price:,.2f}.
```

### Pattern 2: Year-over-Year (YoY) Comparison

The query computes both periods and the delta — ground truth updates automatically.

```yaml
- question: "How does this season's ticket revenue compare to last season so far?"
  validation_query: |
    WITH season_dates AS (
      SELECT SKI_SEASON,
             MIN(FULL_DATE) AS season_start
      FROM SADM_SKI_RESORT_DB.MARTS.DIM_DATE
      GROUP BY SKI_SEASON
    ),
    current AS (
      SELECT d.SKI_SEASON AS current_season,
             ROUND(SUM(t.PURCHASE_AMOUNT), 0) AS current_revenue
      FROM SADM_SKI_RESORT_DB.MARTS.FACT_TICKET_SALES t
      JOIN SADM_SKI_RESORT_DB.MARTS.DIM_DATE d ON t.PURCHASE_DATE_KEY = d.DATE_KEY
      WHERE d.SKI_SEASON = (
        SELECT SKI_SEASON FROM SADM_SKI_RESORT_DB.MARTS.DIM_DATE
        WHERE FULL_DATE = CURRENT_DATE()
      )
      AND d.FULL_DATE <= CURRENT_DATE()
      GROUP BY d.SKI_SEASON
    ),
    prior AS (
      SELECT d.SKI_SEASON AS prior_season,
             ROUND(SUM(t.PURCHASE_AMOUNT), 0) AS prior_revenue
      FROM SADM_SKI_RESORT_DB.MARTS.FACT_TICKET_SALES t
      JOIN SADM_SKI_RESORT_DB.MARTS.DIM_DATE d ON t.PURCHASE_DATE_KEY = d.DATE_KEY
      WHERE d.SKI_SEASON = (
        SELECT MAX(SKI_SEASON) FROM SADM_SKI_RESORT_DB.MARTS.DIM_DATE
        WHERE SKI_SEASON < (
          SELECT SKI_SEASON FROM SADM_SKI_RESORT_DB.MARTS.DIM_DATE
          WHERE FULL_DATE = CURRENT_DATE()
        )
      )
      AND d.WEEK_OF_SEASON <= (
        SELECT MAX(WEEK_OF_SEASON) FROM SADM_SKI_RESORT_DB.MARTS.DIM_DATE
        WHERE FULL_DATE <= CURRENT_DATE()
        AND SKI_SEASON = (
          SELECT SKI_SEASON FROM SADM_SKI_RESORT_DB.MARTS.DIM_DATE
          WHERE FULL_DATE = CURRENT_DATE()
        )
      )
      GROUP BY d.SKI_SEASON
    )
    SELECT c.current_season, c.current_revenue,
           p.prior_season, p.prior_revenue,
           ROUND((c.current_revenue - p.prior_revenue) / NULLIF(p.prior_revenue, 0) * 100, 1) AS yoy_pct
    FROM current c, prior p
  answer_template: >-
    {current_season} ticket revenue is ${current_revenue:,.0f} compared to
    ${prior_revenue:,.0f} through the same point in {prior_season},
    a {yoy_pct}% year-over-year change.
```

### Pattern 3: Rankings (Top-N)

Rankings shift as data changes — validation_query keeps them current.

```yaml
- question: "Which days of the week have the most lift activity this season?"
  validation_query: |
    SELECT d.DAY_NAME AS top_day,
           COUNT(*) AS scan_count
    FROM SADM_SKI_RESORT_DB.MARTS.FACT_LIFT_SCANS ls
    JOIN SADM_SKI_RESORT_DB.MARTS.DIM_DATE d ON ls.DATE_KEY = d.DATE_KEY
    WHERE d.SKI_SEASON = (
      SELECT SKI_SEASON FROM SADM_SKI_RESORT_DB.MARTS.DIM_DATE
      WHERE FULL_DATE = CURRENT_DATE()
    )
    GROUP BY d.DAY_NAME
    ORDER BY scan_count DESC
    LIMIT 1
  answer_template: >-
    {top_day} was the busiest day with {scan_count:,} lift scans this season.
```

For multi-row results, see the `_rows` convention in `run_eval.py` — the template receives
a `rows` list you can iterate with Jinja-style logic, or keep the template simple and use
only the first row.

### Pattern 4: Static Dimension Queries (No Dynamic Needed)

Some questions don't depend on time — use static `ground_truth` directly.

```yaml
- question: "What are the largest customer segments at the resort by number of customers?"
  expected_tools: ["CustomerAnalytics"]
  category: customers
  ground_truth: >-
    The largest customer segments are vacation_family (2,400),
    weekend_warrior (2,000), day_tripper (1,600),
    local_pass_holder (1,200), and expert_skier (400).
```

## `answer_template` Format Strings

Templates use Python `str.format_map()` with the query result columns as keys.

| Syntax | Example | Result |
|--------|---------|--------|
| `{column}` | `{season}` | `2024-2025` |
| `{column:,.0f}` | `{total_revenue:,.0f}` | `2,619,109` |
| `{column:,.2f}` | `{avg_price:,.2f}` | `108.94` |
| `{column:.1f}` | `{yoy_pct:.1f}` | `-14.3` |

Prefix `$` for dollar amounts: `${total_revenue:,.0f}` renders as `$2,619,109`.

## Tips

1. **Always use fully qualified table names** in validation_query — the runner connects to any warehouse
2. **Keep queries simple** — they run before every eval, so avoid expensive scans
3. **Use CTEs for relative time** — `CURRENT_DATE()` as anchor, derive season from `DIM_DATE`
4. **Test your queries independently** before adding them to the YAML
5. **The agent doesn't see the validation_query** — it only sees the question text
6. **Multi-row results**: Only the first row populates the template by default. For top-N ranking answers, use a single-row query that aggregates the ranking into one field, or use the `rows` list in advanced templates
