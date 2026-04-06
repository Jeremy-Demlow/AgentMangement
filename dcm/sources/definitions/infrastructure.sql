DEFINE DATABASE {{db}}
    COMMENT = 'Agent Management CI/CD reference framework - ski resort analytics';

DEFINE SCHEMA {{db}}.RAW
    COMMENT = 'Landing zone for ingested ski resort data'
    DATA_RETENTION_TIME_IN_DAYS = 14;

DEFINE SCHEMA {{db}}.STAGING
    COMMENT = 'Type-safe views over RAW tables (dbt staging layer)';

DEFINE SCHEMA {{db}}.MARTS
    COMMENT = 'Dimensional model: dimensions and facts (dbt marts layer)';

DEFINE SCHEMA {{db}}.DOCS
    COMMENT = 'Document storage for Cortex Search';

DEFINE SCHEMA {{db}}.SEMANTIC{{semantic_schema_suffix}}
    WITH MANAGED ACCESS
    COMMENT = 'Semantic views for Cortex Analyst';

DEFINE SCHEMA {{db}}.AGENTS{{agents_schema_suffix}}
    WITH MANAGED ACCESS
    COMMENT = 'Cortex Agents and eval infrastructure';

DEFINE WAREHOUSE {{wh_name}}
WITH
    WAREHOUSE_SIZE = '{{wh_size}}'
    MIN_CLUSTER_COUNT = {{wh_min_clusters}}
    MAX_CLUSTER_COUNT = {{wh_max_clusters}}
    SCALING_POLICY = '{{wh_scaling_policy}}'
    AUTO_SUSPEND = {{wh_auto_suspend}}
    AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE
    STATEMENT_QUEUED_TIMEOUT_IN_SECONDS = {{wh_queued_timeout}}
    STATEMENT_TIMEOUT_IN_SECONDS = {{wh_statement_timeout}}
    COMMENT = 'Agent Management ski resort project warehouse';

DEFINE STAGE {{db}}.AGENTS{{agents_schema_suffix}}.EVAL_CONFIG_STAGE
    COMMENT = 'Stage for agent evaluation config uploads';
