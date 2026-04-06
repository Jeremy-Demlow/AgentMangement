ALTER AGENT SKI_RESORT_DB.AGENTS.RESORT_EXECUTIVE
MODIFY LIVE VERSION SET SPECIFICATION =
$$
{
  "models": {
    "orchestration": "claude-sonnet-4-5"
  },
  "orchestration": {
    "budget": {
      "seconds": 300,
      "tokens": 50000
    }
  },
  "instructions": {
    "orchestration": "You are Resort Executive Assistant, the comprehensive BI partner for leadership.\n\nTOOL ROUTING: Overall performance -> DailySummaryKPIs (start here for broad questions). Revenue deep dives -> RevenueAnalytics. Customer questions -> CustomerAnalytics or PassholderAnalytics. Operations -> LiftOperations. Staffing -> StaffingAnalytics. Weather -> WeatherAnalytics. Marketing -> MarketingAnalytics. Satisfaction -> CustomerSatisfaction. Safety -> SafetyIncidents. Ski school -> SkiSchoolAnalytics. Pass program -> PassholderAnalytics.\n\nCROSS-DOMAIN: Query multiple tools and synthesize. Start with DailySummaryKPIs for the big picture, drill into specific tools for detail.\n\nBOUNDARIES: No real-time data (updated nightly). No visitor forecasting. No weather forecasts. No individual HR data. No email/alert capabilities.",
    "response": "Executive-level communication \u2014 clear, strategic, insight-driven. Lead with the business headline, then supporting evidence. Provide YoY comparisons and benchmarks. Highlight risks and opportunities. Revenue as currency with commas. Growth rates with direction (+12.3% or -5.1%). Use tables for comparisons, charts for trends.",
    "sample_questions": [
      {
        "question": "Give me a complete resort performance summary for last season"
      },
      {
        "question": "How does weather impact our daily revenue?"
      },
      {
        "question": "Compare this season to last season"
      },
      {
        "question": "Which days of the week drive the most revenue?"
      },
      {
        "question": "Identify our highest-value customer segments"
      },
      {
        "question": "How effective is our marketing spend?"
      },
      {
        "question": "What is our current NPS score and satisfaction trend?"
      },
      {
        "question": "How is ski school revenue performing?"
      }
    ]
  },
  "tools": [
    {
      "tool_spec": {
        "type": "cortex_analyst_text_to_sql",
        "name": "DailySummaryKPIs",
        "description": "Executive daily summary \u2014 visitation, revenue, operations KPIs. PRIMARY TOOL for high-level performance. KEY METRICS: TOTAL_VISITS, UNIQUE_VISITORS, TOTAL_LIFT_SCANS, AVG_WAIT_TIME_MINUTES, TOTAL_TICKET_REVENUE, TOTAL_RENTAL_REVENUE, TOTAL_FNB_REVENUE, TOTAL_DAILY_REVENUE, AVG_RIDES_PER_VISIT, PASS_HOLDER_PCT. KEY DIMENSIONS: FULL_DATE, SKI_SEASON, DAY_NAME, MONTH_NAME, IS_WEEKEND, IS_HOLIDAY. USE FOR: Resort performance, executive summaries, revenue trends, season comparisons."
      }
    },
    {
      "tool_spec": {
        "type": "cortex_analyst_text_to_sql",
        "name": "RevenueAnalytics",
        "description": "Revenue across tickets, rentals, and F&B. KEY METRICS: TOTAL_TICKET_REVENUE, TOTAL_RENTAL_REVENUE, TOTAL_FNB_REVENUE, AVG_TICKET_PRICE, AVG_RENTAL_VALUE, AVG_FNB_SPEND. KEY DIMENSIONS: TICKET_TYPE, PURCHASE_CHANNEL, PRODUCT_CATEGORY, LOCATION_NAME. USE FOR: Revenue by category, channel analysis, pricing, product mix."
      }
    },
    {
      "tool_spec": {
        "type": "cortex_analyst_text_to_sql",
        "name": "CustomerAnalytics",
        "description": "Customer segmentation, demographics, visit behavior. KEY METRICS: TOTAL_VISITS, UNIQUE_CUSTOMERS, AVG_VISITS_PER_CUSTOMER. KEY DIMENSIONS: CUSTOMER_SEGMENT, AGE_GROUP, HOME_STATE, IS_PASS_HOLDER."
      }
    },
    {
      "tool_spec": {
        "type": "cortex_analyst_text_to_sql",
        "name": "LiftOperations",
        "description": "Lift performance, wait times, capacity utilization across 18 lifts. KEY METRICS: TOTAL_SCANS, AVG_WAIT_MINUTES, CAPACITY_UTILIZATION_PCT. KEY DIMENSIONS: LIFT_NAME, TERRAIN_TYPE, SCAN_HOUR, IS_WEEKEND."
      }
    },
    {
      "tool_spec": {
        "type": "cortex_analyst_text_to_sql",
        "name": "StaffingAnalytics",
        "description": "Staffing coverage, labor hours, workforce efficiency by department. KEY METRICS: TOTAL_SCHEDULED, TOTAL_ACTUAL, AVG_COVERAGE, UNDERSTAFFED_COUNT. KEY DIMENSIONS: DEPARTMENT, JOB_ROLE, FULL_DATE, IS_WEEKEND."
      }
    },
    {
      "tool_spec": {
        "type": "cortex_analyst_text_to_sql",
        "name": "WeatherAnalytics",
        "description": "Historical weather \u2014 snowfall, temperature, wind. KEY METRICS: TOTAL_SNOWFALL, POWDER_DAY_COUNT, MAX_WIND, MIN_TEMP, MAX_TEMP. KEY DIMENSIONS: MOUNTAIN_ZONE, SNOW_CONDITION, MONTH_NAME."
      }
    },
    {
      "tool_spec": {
        "type": "cortex_analyst_text_to_sql",
        "name": "MarketingAnalytics",
        "description": "Marketing campaign performance, conversion rates, ROI. KEY METRICS: TOTAL_CONVERSIONS, TOTAL_REVENUE, AVG_CONVERSION_RATE, CAMPAIGN_COUNT. KEY DIMENSIONS: CAMPAIGN_CHANNEL, CAMPAIGN_TYPE, AUDIENCE_SEGMENT."
      }
    },
    {
      "tool_spec": {
        "type": "cortex_analyst_text_to_sql",
        "name": "CustomerSatisfaction",
        "description": "Customer feedback, NPS scores, satisfaction metrics. KEY METRICS: TOTAL_FEEDBACK, AVERAGE_RATING, AVERAGE_NPS, POSITIVE_FEEDBACK_COUNT. KEY DIMENSIONS: CATEGORY, SENTIMENT, FEEDBACK_TYPE, CUSTOMER_SEGMENT."
      }
    },
    {
      "tool_spec": {
        "type": "cortex_analyst_text_to_sql",
        "name": "SafetyIncidents",
        "description": "Safety incidents, severity, patrol response times. KEY METRICS: TOTAL_INCIDENTS, AVERAGE_SEVERITY, AVG_PATROL_RESPONSE. KEY DIMENSIONS: INCIDENT_TYPE, SEVERITY, LOCATION_ID, TRAIL_NAME."
      }
    },
    {
      "tool_spec": {
        "type": "cortex_analyst_text_to_sql",
        "name": "SkiSchoolAnalytics",
        "description": "Ski school \u2014 lesson bookings, instructor utilization, student ratings. KEY METRICS: TOTAL_LESSONS, TOTAL_REVENUE, AVG_STUDENT_RATING. KEY DIMENSIONS: LESSON_TYPE, SPORT_TYPE, SKILL_LEVEL, INSTRUCTOR_NAME."
      }
    },
    {
      "tool_spec": {
        "type": "cortex_analyst_text_to_sql",
        "name": "PassholderAnalytics",
        "description": "Season pass holder behavior, utilization, ROI, retention. KEY METRICS: PASS_HOLDER_VISITS, PASS_HOLDER_COUNT, AVG_VISITS_PER_PASS_HOLDER. KEY DIMENSIONS: CUSTOMER_SEGMENT, AGE_GROUP, HOME_STATE, SKI_SEASON."
      }
    }
  ],
  "tool_resources": {
    "DailySummaryKPIs": {
      "semantic_view": "SKI_RESORT_DB.SEMANTIC.SEM_DAILY_SUMMARY",
      "execution_environment": {
        "type": "warehouse",
        "warehouse": "COMPUTE_WH",
        "query_timeout": 299
      }
    },
    "RevenueAnalytics": {
      "semantic_view": "SKI_RESORT_DB.SEMANTIC.SEM_REVENUE",
      "execution_environment": {
        "type": "warehouse",
        "warehouse": "COMPUTE_WH",
        "query_timeout": 299
      }
    },
    "CustomerAnalytics": {
      "semantic_view": "SKI_RESORT_DB.SEMANTIC.SEM_CUSTOMER_BEHAVIOR",
      "execution_environment": {
        "type": "warehouse",
        "warehouse": "COMPUTE_WH",
        "query_timeout": 299
      }
    },
    "LiftOperations": {
      "semantic_view": "SKI_RESORT_DB.SEMANTIC.SEM_OPERATIONS",
      "execution_environment": {
        "type": "warehouse",
        "warehouse": "COMPUTE_WH",
        "query_timeout": 299
      }
    },
    "StaffingAnalytics": {
      "semantic_view": "SKI_RESORT_DB.SEMANTIC.SEM_STAFFING_ANALYTICS",
      "execution_environment": {
        "type": "warehouse",
        "warehouse": "COMPUTE_WH",
        "query_timeout": 299
      }
    },
    "WeatherAnalytics": {
      "semantic_view": "SKI_RESORT_DB.SEMANTIC.SEM_WEATHER_ANALYTICS",
      "execution_environment": {
        "type": "warehouse",
        "warehouse": "COMPUTE_WH",
        "query_timeout": 299
      }
    },
    "MarketingAnalytics": {
      "semantic_view": "SKI_RESORT_DB.SEMANTIC.SEM_MARKETING_ANALYTICS",
      "execution_environment": {
        "type": "warehouse",
        "warehouse": "COMPUTE_WH",
        "query_timeout": 299
      }
    },
    "CustomerSatisfaction": {
      "semantic_view": "SKI_RESORT_DB.SEMANTIC.SEM_CUSTOMER_SATISFACTION",
      "execution_environment": {
        "type": "warehouse",
        "warehouse": "COMPUTE_WH",
        "query_timeout": 299
      }
    },
    "SafetyIncidents": {
      "semantic_view": "SKI_RESORT_DB.SEMANTIC.SEM_SAFETY_INCIDENTS",
      "execution_environment": {
        "type": "warehouse",
        "warehouse": "COMPUTE_WH",
        "query_timeout": 299
      }
    },
    "SkiSchoolAnalytics": {
      "semantic_view": "SKI_RESORT_DB.SEMANTIC.SEM_LESSONS_ANALYTICS",
      "execution_environment": {
        "type": "warehouse",
        "warehouse": "COMPUTE_WH",
        "query_timeout": 299
      }
    },
    "PassholderAnalytics": {
      "semantic_view": "SKI_RESORT_DB.SEMANTIC.SEM_PASSHOLDER_ANALYTICS",
      "execution_environment": {
        "type": "warehouse",
        "warehouse": "COMPUTE_WH",
        "query_timeout": 299
      }
    }
  }
}
$$
