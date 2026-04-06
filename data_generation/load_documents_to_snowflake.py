"""
Load documents to Snowflake and create Cortex Search service.
"""

import json
from snowflake_connection import SnowflakeConnection
from config import DATABASE, WAREHOUSE, DOCS_SCHEMA

_DOCS_TABLE = f"{DATABASE}.{DOCS_SCHEMA}.RESORT_DOCUMENTS"
_SEARCH_SVC = f"{DATABASE}.{DOCS_SCHEMA}.RESORT_DOCS_SEARCH"

def main():
    print("Connecting to Snowflake...")
    conn = SnowflakeConnection.from_snow_cli("snowflake_agents")

    print("Creating documents table...")
    conn.sql(f"""
        CREATE TABLE IF NOT EXISTS {_DOCS_TABLE} (
            DOC_ID VARCHAR(50) PRIMARY KEY,
            DOC_TYPE VARCHAR(50),
            TITLE VARCHAR(500),
            CONTENT TEXT,
            SOURCE_FILE VARCHAR(200),
            CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
        )
    """).collect()

    conn.sql(f"TRUNCATE TABLE {_DOCS_TABLE}").collect()

    print("Loading documents...")
    with open('documents.json') as f:
        documents = json.load(f)

    for doc in documents:
        content = doc['content'].replace("'", "''")
        title = doc['title'].replace("'", "''")

        sql = f"""
            INSERT INTO {_DOCS_TABLE}
            (DOC_ID, DOC_TYPE, TITLE, CONTENT, SOURCE_FILE)
            VALUES ('{doc['doc_id']}', '{doc['doc_type']}', '{title}', '{content}', '{doc['source_file']}')
        """
        conn.sql(sql).collect()
        print(f"   {doc['doc_id']}: {doc['title']}")

    result = conn.sql(f"SELECT COUNT(*) as cnt FROM {_DOCS_TABLE}").to_pandas()
    print(f"\nTotal documents loaded: {result['CNT'].iloc[0]}")

    print("\nCreating Cortex Search Service...")
    try:
        conn.sql(f"""
            CREATE OR REPLACE CORTEX SEARCH SERVICE {_SEARCH_SVC}
              ON CONTENT
              ATTRIBUTES DOC_TYPE, TITLE
              WAREHOUSE = {WAREHOUSE}
              TARGET_LAG = '1 hour'
              AS (
                SELECT DOC_ID, DOC_TYPE, TITLE, CONTENT, SOURCE_FILE
                FROM {_DOCS_TABLE}
              )
        """).collect()
        print("   Cortex Search Service created!")
    except Exception as e:
        print(f"   Search service creation: {e}")

    print("\nDone!")
    conn.close()


if __name__ == '__main__':
    main()
