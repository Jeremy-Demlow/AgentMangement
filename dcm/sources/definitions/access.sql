DEFINE ROLE {{deploy_role}}
COMMENT = 'CI/CD deployment role — owns DCM project, runs dbt, deploys agents and SVs';

DEFINE DATABASE ROLE {{db}}.ADMIN
COMMENT = 'Full DDL + DML + Cortex object creation on all schemas';

DEFINE DATABASE ROLE {{db}}.DEVELOPER
COMMENT = 'DML on RAW/STAGING, read on all, stage write for evals';

DEFINE DATABASE ROLE {{db}}.ANALYST
COMMENT = 'Read-only: SELECT on all schemas (includes future objects)';

-- NOTE: The template variable is named {{wh_role}} for historical reasons but
-- the actual role name follows the pattern AM_SKI_RESORT_WH_USER[_<env>]. Do
-- not rename without coordinating with manifest.yml and all target configs.
-- See docs/operations/IAC_GAPS.md #5.
DEFINE ROLE {{wh_role}}
COMMENT = 'Warehouse USAGE for {{wh_name}}';

GRANT DATABASE ROLE {{db}}.ANALYST TO DATABASE ROLE {{db}}.DEVELOPER;
GRANT DATABASE ROLE {{db}}.DEVELOPER TO DATABASE ROLE {{db}}.ADMIN;
GRANT DATABASE ROLE {{db}}.ADMIN TO ROLE {{deploy_role}};
GRANT ROLE {{wh_role}} TO ROLE {{deploy_role}};
GRANT ROLE {{deploy_role}} TO ROLE SYSADMIN;

GRANT USAGE ON WAREHOUSE {{wh_name}} TO ROLE {{wh_role}};
GRANT EXECUTE TASK ON ACCOUNT TO ROLE {{deploy_role}};
GRANT USAGE ON DATABASE {{db}} TO DATABASE ROLE {{db}}.ANALYST;

-- Cortex Analyst Evaluations (SV Eval Gate) requires this account-level
-- privilege to read the AI OBS events table. Without it, EXECUTE_AI_EVALUATION
-- fails with "Semantic View Optimization does not exist or not authorized".
-- Ref: Snowflake bug notice — fix rolling out, but this grant is needed for
-- reliable evals. See docs/operations/IAC_GAPS.md #8.
GRANT READ UNREDACTED AI OBSERVABILITY EVENTS TABLE ON ACCOUNT TO ROLE {{deploy_role}};

{{ schema_read_grants(db, 'RAW', 'ANALYST') }}
{{ schema_read_grants(db, 'STAGING', 'ANALYST') }}
{{ schema_read_grants(db, 'MARTS', 'ANALYST') }}
{{ schema_read_grants(db, 'DOCS', 'ANALYST') }}
{{ schema_read_grants(db, 'SEMANTIC' ~ semantic_schema_suffix, 'ANALYST') }}
{{ schema_read_grants(db, 'AGENTS' ~ agents_schema_suffix, 'ANALYST') }}
{{ schema_read_grants(db, 'DBT_TEST__AUDIT', 'ANALYST') }}

{{ schema_write_grants(db, 'RAW', 'DEVELOPER') }}
{{ schema_write_grants(db, 'STAGING', 'DEVELOPER') }}

{{ schema_ddl_grants(db, 'RAW', 'ADMIN') }}
{{ schema_ddl_grants(db, 'STAGING', 'ADMIN') }}
{{ schema_ddl_grants(db, 'MARTS', 'ADMIN') }}
{{ schema_ddl_grants(db, 'DOCS', 'ADMIN') }}
{{ schema_ddl_grants(db, 'SEMANTIC' ~ semantic_schema_suffix, 'ADMIN') }}
{{ schema_ddl_grants(db, 'AGENTS' ~ agents_schema_suffix, 'ADMIN') }}
{{ schema_ddl_grants(db, 'DBT_TEST__AUDIT', 'ADMIN') }}

{{ schema_stage_write_grants(db, 'AGENTS' ~ agents_schema_suffix, 'DEVELOPER') }}
{{ schema_stage_write_grants(db, 'AGENTS' ~ agents_schema_suffix, 'ADMIN') }}
{{ schema_stage_write_grants(db, 'SEMANTIC' ~ semantic_schema_suffix, 'ADMIN') }}
{{ schema_stage_write_grants(db, 'DOCS', 'ADMIN') }}

{% for user_name in users %}
GRANT ROLE {{wh_role}} TO USER {{user_name}};
GRANT ROLE {{deploy_role}} TO USER {{user_name}};
GRANT DATABASE ROLE {{db}}.DEVELOPER TO USER {{user_name}};
{% endfor %}
