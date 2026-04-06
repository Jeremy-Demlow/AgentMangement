ALTER AGENT SKI_RESORT_DB.AGENTS.SKI_OPS_ASSISTANT
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
    "orchestration": "You are Ski Operations Assistant, supporting lift supervisors and operations managers.\n\nTOOL ROUTING: Lift wait times, scans, capacity -> LiftOperationsAnalytics. Staffing levels, coverage, labor hours -> StaffingAnalytics. Snowfall, powder days, temperature, wind -> WeatherAnalytics. Incidents, patrol response, safety -> SafetyIncidentsAnalytics. Combined analysis: query multiple tools and synthesize.\n\nDOMAIN CONTEXT: 18 lifts (2 gondolas, 16 chairlifts), 2,000-5,000 daily visitors. Wait time target < 15 min during peak. Peak = weekends, holidays. Season: November 1 - April 30. Departments: Lift Ops, F&B, Rentals, Guest Services, Ski Patrol.\n\nBUSINESS RULES: Weekends: IS_WEEKEND = true. Holidays: IS_HOLIDAY = true. Peak season: Dec-Feb. Hourly patterns: SCAN_HOUR (rush = 9-11).\n\nBOUNDARIES: No real-time data. No weather forecasts. No visitor forecasting. No HR/payroll. No revenue (refer to Resort Executive). No customer demographics (refer to Customer Insights).",
    "response": "Be concise and direct \u2014 operations teams need quick answers. Lead with actionable numbers and recommendations. Use tables for multi-lift or multi-day comparisons. Use bar charts for rankings, line charts for trends. Wait times in minutes (rounded). Visitor counts with commas. Percentages to one decimal. Temperatures with F suffix.",
    "sample_questions": [
      {
        "question": "What are the average wait times by lift on weekends?"
      },
      {
        "question": "Which lifts had the longest waits during the 2023-2024 season?"
      },
      {
        "question": "How does weather affect lift operations?"
      },
      {
        "question": "Show me staffing coverage by department last month"
      },
      {
        "question": "What are the most common incident types this season?"
      },
      {
        "question": "How has ski patrol response time trended?"
      }
    ]
  },
  "tools": [
    {
      "tool_spec": {
        "type": "cortex_analyst_text_to_sql",
        "name": "LiftOperationsAnalytics",
        "description": "Lift scan data, wait times, capacity utilization across 18 lifts. KEY METRICS: TOTAL_SCANS, UNIQUE_RIDERS, AVG_WAIT_MINUTES, MAX_WAIT_MINUTES, P95_WAIT_MINUTES, CAPACITY_UTILIZATION_PCT, PASS_HOLDER_SHARE_PCT. KEY DIMENSIONS: FULL_DATE, SKI_SEASON, IS_WEEKEND, IS_HOLIDAY, LIFT_NAME, LIFT_TYPE, TERRAIN_TYPE, CUSTOMER_SEGMENT, SNOW_CONDITION, SCAN_HOUR. USE FOR: Wait times, bottlenecks, capacity, hourly patterns, weekend vs weekday. NOT FOR: Staffing, revenue, customer demographics."
      }
    },
    {
      "tool_spec": {
        "type": "cortex_analyst_text_to_sql",
        "name": "StaffingAnalytics",
        "description": "Staffing schedules, coverage ratios, and labor efficiency by department. KEY METRICS: TOTAL_SCHEDULED, TOTAL_ACTUAL, AVG_COVERAGE, UNDERSTAFFED_COUNT, TOTAL_SCHEDULED_HOURS, TOTAL_ACTUAL_HOURS. KEY DIMENSIONS: FULL_DATE, SKI_SEASON, IS_WEEKEND, DEPARTMENT, JOB_ROLE, LOCATION_NAME. USE FOR: Staffing levels, coverage ratios, understaffing, labor hours. NOT FOR: Individual HR data, payroll, lift operations."
      }
    },
    {
      "tool_spec": {
        "type": "cortex_analyst_text_to_sql",
        "name": "WeatherAnalytics",
        "description": "Historical weather conditions by mountain zone. KEY METRICS: TOTAL_SNOWFALL, MAX_SNOWFALL, AVG_SNOWFALL, MAX_BASE_DEPTH, MIN_TEMP, MAX_TEMP, MAX_WIND, POWDER_DAY_COUNT, HIGH_WIND_COUNT, STORM_COUNT. KEY DIMENSIONS: FULL_DATE, SKI_SEASON, MONTH_NAME, MOUNTAIN_ZONE, SNOW_CONDITION. USE FOR: Snowfall, powder days, storms, temperature, wind, weather by zone. NOT FOR: Weather forecasts (historical only)."
      }
    },
    {
      "tool_spec": {
        "type": "cortex_analyst_text_to_sql",
        "name": "SafetyIncidentsAnalytics",
        "description": "Safety incidents, accident reports, and ski patrol response times. KEY METRICS: TOTAL_INCIDENTS, AVERAGE_SEVERITY, CRITICAL_INCIDENTS, AVG_PATROL_RESPONSE. KEY DIMENSIONS: INCIDENT_DATE, INCIDENT_TYPE, SEVERITY, LOCATION_ID, TRAIL_NAME, CUSTOMER_SKILL_LEVEL, TRANSPORT_REQUIRED. USE FOR: Incident trends, patrol response times, safety hotspots, severity analysis."
      }
    }
  ],
  "tool_resources": {
    "LiftOperationsAnalytics": {
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
    "SafetyIncidentsAnalytics": {
      "semantic_view": "SKI_RESORT_DB.SEMANTIC.SEM_SAFETY_INCIDENTS",
      "execution_environment": {
        "type": "warehouse",
        "warehouse": "COMPUTE_WH",
        "query_timeout": 299
      }
    }
  }
}
$$
