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
-- Optional future hardening: split OWNER-style DDL from deployer operations
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

-- Cortex Analyst Evaluations (SV Eval Gate) requires the full set of
-- privileges documented at
--   https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst/evaluation
-- Without EVERY one of these, EXECUTE_AI_EVALUATION on a semantic view
-- fails with "Semantic View Optimization SYSTEM_AI_OBS_ANALYST_EVAL_<sv>
-- does not exist or not authorized" because the companion optimization
-- object can't be provisioned by current Snowflake platform behavior.
--
-- Required per the doc:
--   1. CORTEX_USER database role
--   2. AI_OBSERVABILITY_EVENTS_LOOKUP application role
--   3. EXECUTE TASK on account
--   4. CREATE TASK on the schema containing the semantic view
--   5. CREATE DATASET on the schema containing the semantic view
--   6. SELECT and MONITOR on the semantic view(s)
--   7. READ UNREDACTED AI OBSERVABILITY EVENTS TABLE (account-level)
GRANT READ UNREDACTED AI OBSERVABILITY EVENTS TABLE ON ACCOUNT TO ROLE {{deploy_role}};
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE {{deploy_role}};
GRANT APPLICATION ROLE SNOWFLAKE.AI_OBSERVABILITY_EVENTS_LOOKUP TO ROLE {{deploy_role}};
GRANT CREATE TASK ON SCHEMA {{db}}.SEMANTIC{{ semantic_schema_suffix }} TO ROLE {{deploy_role}};
GRANT CREATE DATASET ON SCHEMA {{db}}.SEMANTIC{{ semantic_schema_suffix }} TO ROLE {{deploy_role}};
GRANT SELECT ON ALL SEMANTIC VIEWS IN SCHEMA {{db}}.SEMANTIC{{ semantic_schema_suffix }} TO ROLE {{deploy_role}};
GRANT MONITOR ON ALL SEMANTIC VIEWS IN SCHEMA {{db}}.SEMANTIC{{ semantic_schema_suffix }} TO ROLE {{deploy_role}};
GRANT SELECT ON FUTURE SEMANTIC VIEWS IN SCHEMA {{db}}.SEMANTIC{{ semantic_schema_suffix }} TO ROLE {{deploy_role}};
GRANT MONITOR ON FUTURE SEMANTIC VIEWS IN SCHEMA {{db}}.SEMANTIC{{ semantic_schema_suffix }} TO ROLE {{deploy_role}};

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
