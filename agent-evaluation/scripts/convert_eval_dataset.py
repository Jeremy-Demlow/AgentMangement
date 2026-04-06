#!/usr/bin/env python3
"""
Convert existing evaluation datasets to the GA Cortex Agent Evaluations format.

Transforms tables with question/expected_answer columns to the required format:
- input_query (VARCHAR) — the question
- output (VARIANT) — {"ground_truth_output": "..."} using PARSE_JSON

Usage:
    python convert_eval_dataset.py \
        --source-table db.schema.existing_eval \
        --target-table db.schema.agent_eval_data \
        --question-col question \
        --answer-col expected_answer \
        --connection CONNECTION_NAME

Optional:
    --drop-target    Drop target table if it exists
"""

import argparse
import json
import snowflake.connector
import os


def convert_dataset(
    source_table: str,
    target_table: str,
    question_col: str,
    answer_col: str,
    connection_name: str,
    drop_target: bool = False
):
    conn = snowflake.connector.connect(connection_name=connection_name)
    cursor = conn.cursor()

    try:
        if drop_target:
            print(f"Dropping target table if exists: {target_table}")
            cursor.execute(f"DROP TABLE IF EXISTS {target_table}")

        sql = f"""
        CREATE OR REPLACE TABLE {target_table} AS
        SELECT
            {question_col} AS input_query,
            PARSE_JSON(
                '{{\"ground_truth_output\": \"' || REPLACE({answer_col}, '"', '\\\\"') || '\"}}'
            ) AS output
        FROM {source_table}
        WHERE {question_col} IS NOT NULL
        """

        print(f"Converting {source_table} -> {target_table}")
        print(f"  Question column : {question_col}")
        print(f"  Answer column   : {answer_col}")

        cursor.execute(sql)

        cursor.execute(f"SELECT COUNT(*) FROM {target_table}")
        count = cursor.fetchone()[0]
        print(f"\nCreated {target_table} with {count} rows")

        cursor.execute(f"SELECT input_query, output FROM {target_table} LIMIT 1")
        sample = cursor.fetchone()
        if sample:
            print(f"\nSample row:")
            q = str(sample[0])
            print(f"  input_query : {q[:100]}{'...' if len(q) > 100 else ''}")
            gt = json.loads(sample[1]) if isinstance(sample[1], str) else sample[1]
            print(f"  output      : {json.dumps(gt, indent=4)[:200]}")

        print(f"\nNext steps:")
        print(f"1. Create a YAML evaluation config referencing this table:")
        print(f"""
dataset:
  dataset_type: "CORTEX AGENT"
  table_name: "{target_table}"
  dataset_name: "<unique_dataset_name>"
  column_mapping:
    query_text: "INPUT_QUERY"
    ground_truth: "OUTPUT"

evaluation:
  agent_params:
    agent_name: "<DATABASE>.<SCHEMA>.<AGENT_NAME>"   # must be fully qualified
    agent_type: "CORTEX AGENT"
  run_params:
    label: "Evaluation run"
  source_metadata:
    type: "dataset"                                   # must be lowercase
    dataset_name: "<DATABASE>.<SCHEMA>.<unique_dataset_name>"

metrics:
  - "answer_correctness"
  - "logical_consistency"
""")
        print(f"2. Upload the YAML to a stage (see SKILL.md Step 4.3)")
        print(f"3. Run:")
        print(f"   CALL EXECUTE_AI_EVALUATION(")
        print(f"       'START',")
        print(f"       OBJECT_CONSTRUCT('run_name', '<run_name>'),")
        print(f"       '@<DATABASE>.<SCHEMA>.<STAGE>/config.yaml'")
        print(f"   );")

    finally:
        cursor.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Convert evaluation datasets to GA Cortex Agent Evaluations format"
    )
    parser.add_argument("--source-table", required=True, help="Source table (db.schema.table)")
    parser.add_argument("--target-table", required=True, help="Target table to create (db.schema.table)")
    parser.add_argument("--question-col", default="question", help="Column with questions (default: question)")
    parser.add_argument("--answer-col", default="expected_answer", help="Column with expected answers (default: expected_answer)")
    parser.add_argument("--connection", default=os.getenv("SNOWFLAKE_CONNECTION_NAME", "default"), help="Snowflake connection name")
    parser.add_argument("--drop-target", action="store_true", help="Drop target table if it exists")

    args = parser.parse_args()

    convert_dataset(
        source_table=args.source_table,
        target_table=args.target_table,
        question_col=args.question_col,
        answer_col=args.answer_col,
        connection_name=args.connection,
        drop_target=args.drop_target
    )


if __name__ == "__main__":
    main()
