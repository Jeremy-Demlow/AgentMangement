# Tool Description Template

Every tool in `agents/specs/*.yml` MUST follow this format. The CI test in
[tests/test_templates.py](../tests/test_templates.py) asserts every
description contains the required section headers.

## Required sections (in order)

```yaml
description: >
  PURPOSE: <one sentence stating what the tool does and when it's the primary choice>

  DATA: <coverage, granularity, refresh frequency>

  KEY METRICS: <comma-separated list of the most important metric names>
  (optionally grouped: KEY METRICS (LIFTS): ..., KEY METRICS (MAINTENANCE): ...)

  KEY DIMENSIONS: <comma-separated list>

  USE FOR:
    - <scenario 1>
    - <scenario 2>
    - <scenario 3>

  NOT FOR:
    - <bounded scenario A (use <other tool> instead)>
    - <bounded scenario B>

  CROSS-REFERENCE WITH: <other tool> (<what multi-tool question this supports>),
  <other tool> (<another multi-tool question>).
```

## Optional sections

Add these only when relevant:

- **DISAMBIGUATION**: When two tools have overlapping domains (e.g. this
  repo's `CustomerAnalytics` vs `PassholderAnalytics`), include a paragraph
  that clarifies which tool to pick.
- **NOTE**: When the SV has a quirk the agent should know about
  (e.g. "powder days aggregate across zones unless grouped by MOUNTAIN_ZONE").

## Naming rules

- Tool names use `PascalCase`.
- Include both the **domain** and the **function**:
  - Good: `LiftOperationsAnalytics`, `RevenueAnalytics`, `SafetyIncidents`
  - Bad: `Analytics`, `DataTool`, `Query1`
- Tool name should never be more generic than the SV it wraps.

## Worked example — GOOD

```yaml
- name: RevenueAnalytics
  description: >
    PURPOSE: Detailed revenue across tickets, rentals, and F&B with
    product-level breakdowns.

    DATA: Transaction-level, refreshed nightly.

    KEY METRICS: TOTAL_TICKET_REVENUE, TOTAL_RENTAL_REVENUE, TOTAL_FNB_REVENUE,
    AVG_TICKET_PRICE, AVG_RENTAL_VALUE, AVG_FNB_SPEND, TICKET_COUNT, RENTAL_COUNT.

    KEY DIMENSIONS: TICKET_TYPE, PURCHASE_CHANNEL, PRODUCT_CATEGORY, LOCATION_NAME,
    FULL_DATE, SKI_SEASON.

    USE FOR:
      - Revenue by category, channel, or product
      - Ticket type breakdowns and pricing analysis
      - F&B category performance and location-level sales

    NOT FOR:
      - High-level daily totals (use DailySummaryKPIs)
      - Customer demographics (use CustomerAnalytics)

    CROSS-REFERENCE WITH: WeatherAnalytics (weather-revenue correlation),
    MarketingAnalytics (campaign-attributed revenue).
```

## Worked example — BAD

```yaml
- name: Revenue
  description: >
    Gets revenue data.
```

Problems:
- Generic name (which revenue? From where?)
- No PURPOSE sentence
- No DATA context (is it daily? transactional? stale?)
- No KEY METRICS / DIMENSIONS (what columns exist?)
- No USE FOR (when should I pick this tool?)
- No NOT FOR (when shouldn't I?)
- No CROSS-REFERENCE (how does it combine with other tools?)

## Why this rigor matters

Best practices guide observes that precise tool descriptions can increase
tool-selection accuracy by **30-40%**. That is a larger delta than any
single instruction change typically produces.
