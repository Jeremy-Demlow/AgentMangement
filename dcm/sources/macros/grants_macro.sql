{% macro schema_read_grants(db, schema, role) %}
    GRANT USAGE ON SCHEMA {{db}}.{{schema}} TO DATABASE ROLE {{db}}.{{role}};
    GRANT SELECT ON ALL TABLES IN SCHEMA {{db}}.{{schema}} TO DATABASE ROLE {{db}}.{{role}};
    GRANT SELECT ON ALL VIEWS IN SCHEMA {{db}}.{{schema}} TO DATABASE ROLE {{db}}.{{role}};
    GRANT SELECT ON FUTURE TABLES IN SCHEMA {{db}}.{{schema}} TO DATABASE ROLE {{db}}.{{role}};
    GRANT SELECT ON FUTURE VIEWS IN SCHEMA {{db}}.{{schema}} TO DATABASE ROLE {{db}}.{{role}};
{% endmacro %}

{% macro schema_write_grants(db, schema, role) %}
    GRANT INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {{db}}.{{schema}} TO DATABASE ROLE {{db}}.{{role}};
    GRANT INSERT, UPDATE, DELETE ON FUTURE TABLES IN SCHEMA {{db}}.{{schema}} TO DATABASE ROLE {{db}}.{{role}};
{% endmacro %}

{% macro schema_ddl_grants(db, schema, role) %}
    GRANT CREATE TABLE ON SCHEMA {{db}}.{{schema}} TO DATABASE ROLE {{db}}.{{role}};
    GRANT CREATE VIEW ON SCHEMA {{db}}.{{schema}} TO DATABASE ROLE {{db}}.{{role}};
    GRANT CREATE DYNAMIC TABLE ON SCHEMA {{db}}.{{schema}} TO DATABASE ROLE {{db}}.{{role}};
    GRANT CREATE STAGE ON SCHEMA {{db}}.{{schema}} TO DATABASE ROLE {{db}}.{{role}};
    GRANT CREATE FILE FORMAT ON SCHEMA {{db}}.{{schema}} TO DATABASE ROLE {{db}}.{{role}};
    GRANT CREATE FUNCTION ON SCHEMA {{db}}.{{schema}} TO DATABASE ROLE {{db}}.{{role}};
    GRANT CREATE PROCEDURE ON SCHEMA {{db}}.{{schema}} TO DATABASE ROLE {{db}}.{{role}};
    GRANT CREATE AGENT ON SCHEMA {{db}}.{{schema}} TO DATABASE ROLE {{db}}.{{role}};
    GRANT CREATE SEMANTIC VIEW ON SCHEMA {{db}}.{{schema}} TO DATABASE ROLE {{db}}.{{role}};
    GRANT CREATE CORTEX SEARCH SERVICE ON SCHEMA {{db}}.{{schema}} TO DATABASE ROLE {{db}}.{{role}};
{% endmacro %}

{% macro schema_stage_write_grants(db, schema, role) %}
    GRANT READ, WRITE ON ALL STAGES IN SCHEMA {{db}}.{{schema}} TO DATABASE ROLE {{db}}.{{role}};
    GRANT READ, WRITE ON FUTURE STAGES IN SCHEMA {{db}}.{{schema}} TO DATABASE ROLE {{db}}.{{role}};
{% endmacro %}
