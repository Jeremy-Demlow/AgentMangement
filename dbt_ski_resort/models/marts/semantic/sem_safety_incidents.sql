{{ config(materialized='semantic_view') }}

-- Safety Incidents semantic view (simplified)

TABLES (
    FACT_INCIDENTS AS {{ ref('fact_incidents') }}
      PRIMARY KEY (INCIDENT_ID)
      WITH SYNONYMS ('incidents', 'accidents', 'safety')
      COMMENT = 'Safety incident records',

    DIM_DATE AS {{ ref('dim_date') }}
      PRIMARY KEY (DATE_KEY)
      WITH SYNONYMS ('calendar')
      COMMENT = 'Calendar dimension with ski season awareness'
)

RELATIONSHIPS (
    INCIDENTS_TO_DATE AS
      FACT_INCIDENTS (DATE_KEY) REFERENCES DIM_DATE
)

FACTS (
    FACT_INCIDENTS.SEVERITY_SCORE AS SEVERITY_SCORE
      COMMENT = 'Numeric severity (1-4)',
    FACT_INCIDENTS.PATROL_RESPONSE_MINUTES AS PATROL_RESPONSE_MINUTES
      COMMENT = 'Ski patrol response time'
)

DIMENSIONS (
    FACT_INCIDENTS.DATE_KEY AS DATE_KEY
      COMMENT = 'Date surrogate key',
    FACT_INCIDENTS.INCIDENT_DATE AS INCIDENT_DATE
      COMMENT = 'Date of incident',
    DIM_DATE.DATE_KEY AS DIM_DATE_KEY
      COMMENT = 'Calendar date key',
    DIM_DATE.SKI_SEASON AS SKI_SEASON
      COMMENT = 'Ski season identifier (e.g. 2024-2025)',
    DIM_DATE.FULL_DATE AS FULL_DATE
      WITH SYNONYMS ('date')
      COMMENT = 'Calendar date',
    FACT_INCIDENTS.INCIDENT_TYPE AS INCIDENT_TYPE
      WITH SYNONYMS ('type')
      COMMENT = 'Type of incident',
    FACT_INCIDENTS.SEVERITY AS SEVERITY
      COMMENT = 'Severity level',
    FACT_INCIDENTS.LOCATION_ID AS LOCATION_ID
      COMMENT = 'Location ID',
    FACT_INCIDENTS.LIFT_ID AS LIFT_ID
      COMMENT = 'Lift associated',
    FACT_INCIDENTS.TRAIL_NAME AS TRAIL_NAME
      COMMENT = 'Trail name',
    FACT_INCIDENTS.CUSTOMER_SKILL_LEVEL AS CUSTOMER_SKILL_LEVEL
      COMMENT = 'Customer skill level',
    FACT_INCIDENTS.TRANSPORT_REQUIRED AS TRANSPORT_REQUIRED
      COMMENT = 'Transport required',
    FACT_INCIDENTS.CUSTOMER_SEGMENT AS CUSTOMER_SEGMENT
      COMMENT = 'Customer segment'
)

METRICS (
    FACT_INCIDENTS.TOTAL_INCIDENTS AS COUNT(FACT_INCIDENTS.INCIDENT_ID)
      COMMENT = 'Total incidents',
    FACT_INCIDENTS.AVERAGE_SEVERITY AS AVG(FACT_INCIDENTS.SEVERITY_SCORE)
      COMMENT = 'Average severity',
    FACT_INCIDENTS.CRITICAL_INCIDENTS AS COUNT(CASE WHEN FACT_INCIDENTS.SEVERITY = 'Critical' THEN 1 END)
      COMMENT = 'Critical incidents',
    FACT_INCIDENTS.AVG_PATROL_RESPONSE AS AVG(FACT_INCIDENTS.PATROL_RESPONSE_MINUTES)
      COMMENT = 'Avg patrol response time'
)

COMMENT = 'Safety incident tracking'

WITH EXTENSION (CA = $$
{
  "module_custom_instructions": {
    "sql_generation": "Use FACT_INCIDENTS for all safety and incident queries. Use DIM_DATE.SKI_SEASON for seasonal filtering (e.g. 'last season'). Filter by SEVERITY for critical analysis. Use PATROL_RESPONSE_MINUTES for response time metrics. Guard division with DIV0()."
  },
  "verified_queries": [
    {
      "name": "incidents_severity_by_type",
      "question": "What are the total incidents and average severity by incident type?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n  AM_SKI_RESORT.SEMANTIC.SEM_SAFETY_INCIDENTS\n  DIMENSIONS incident_type\n  METRICS total_incidents, average_severity\n)",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": true
    },
    {
      "name": "critical_by_trail",
      "question": "What is the total incidents and critical incidents count by trail name for trails with at least one critical incident?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n    AM_SKI_RESORT.SEMANTIC.SEM_SAFETY_INCIDENTS\n    METRICS total_incidents, critical_incidents\n    DIMENSIONS trail_name\n    WHERE trail_name IS NOT NULL\n) WHERE critical_incidents >= 1 ORDER BY critical_incidents DESC NULLS LAST",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": true
    },
    {
      "name": "severity_by_skill_level",
      "question": "What is the average severity and total incidents by customer skill level and severity level?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n  AM_SKI_RESORT.SEMANTIC.SEM_SAFETY_INCIDENTS\n  METRICS average_severity, total_incidents\n  DIMENSIONS customer_skill_level, severity\n)",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": false
    },
    {
      "name": "transport_incidents_by_segment",
      "question": "What is the total incidents and critical incidents count by customer segment where transport was required?",
      "sql": "SELECT * FROM SEMANTIC_VIEW(\n    AM_SKI_RESORT.SEMANTIC.SEM_SAFETY_INCIDENTS\n    DIMENSIONS fact_incidents.customer_segment\n    METRICS total_incidents, critical_incidents\n    WHERE fact_incidents.transport_required = TRUE\n)",
      "verified_by": "Cortex Analyst",
      "verified_at": 1744900000,
      "use_as_onboarding_question": false
    }
  ]
}
$$)
