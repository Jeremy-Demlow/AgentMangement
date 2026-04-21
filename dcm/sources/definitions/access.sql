DEFINE ROLE {{deploy_role}}
COMMENT = 'CI/CD deployment role — owns DCM project, runs dbt, deploys agents and SVs';

DEFINE DATABASE ROLE {{db}}.ADMIN
COMMENT = 'Full DDL + DML + Cortex object creation on all schemas';

DEFINE DATABASE ROLE {{db}}.DEVELOPER
COMMENT = 'DML on RAW/STAGING, read on all, stage write for evals';

DEFINE DATABASE ROLE {{db}}.ANALYST
COMMENT = 'Read-only: SELECT on all schemas (includes future objects)';

DEFINE ROLE {{wh_role}}
COMMENT = 'Warehouse USAGE for {{wh_name}}';

GRANT DATABASE ROLE {{db}}.ANALYST TO DATABASE ROLE {{db}}.DEVELOPER;
GRANT DATABASE ROLE {{db}}.DEVELOPER TO DATABASE ROLE {{db}}.ADMIN;
GRANT DATABASE ROLE {{db}}.ADMIN TO ROLE {{deploy_role}};
GRANT ROLE {{wh_role}} TO ROLE {{deploy_role}};
GRANT ROLE {{deploy_role}} TO ROLE SYSADMIN;

GRANT USAGE ON WAREHOUSE {{wh_name}} TO ROLE {{wh_role}};
GRANT USAGE ON DATABASE {{db}} TO DATABASE ROLE {{db}}.ANALYST;

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
GRANT DATABASE ROLE {{db}}.DEVELOPER TO USER {{user_name}};
{% endfor %}
