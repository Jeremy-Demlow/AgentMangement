#!/usr/bin/env python3
"""
Load evaluation dataset from a local CSV into a Snowflake table.

The CSV is the single source of truth for evaluation questions and ground truth.
Edit the CSV, then run this script to sync changes to Snowflake.

CSV format:
    target_tool,question,ground_truth,test_type
    RevenueAnalytics,"What was Q4 revenue?","Q4 revenue was $2.4M.",in_scope

Usage:
    python load_eval_dataset.py \
        --csv datasets/resort_executive_eval.csv \
        --target-table <DATABASE>.AGENTS.RESORT_EXECUTIVE_EVAL_DATA \
        --connection CONNECTION_NAME

Options:
    --dry-run    Show what would be inserted without writing to Snowflake
"""

import argparse
import csv
import json
import os
import snowflake.connector


def load_dataset(csv_path: str, target_table: str, connection_name: str, dry_run: bool = False):
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            question = row["question"].strip()
            ground_truth = row["ground_truth"].strip()
            target_tool = row.get("target_tool", "").strip()
            test_type = row.get("test_type", "in_scope").strip()

            if not question:
                continue

            rows.append({
                "question": question,
                "ground_truth": ground_truth,
                "target_tool": target_tool,
                "test_type": test_type,
            })

    print(f"Loaded {len(rows)} questions from {csv_path}")
    print()

    for i, r in enumerate(rows, 1):
        label = f"[{r['test_type']}]" if r["test_type"] else ""
        print(f"  {i:>2}. {label:>14} {r['question'][:70]}")

    if dry_run:
        print("\n-- DRY RUN: no changes made to Snowflake --")
        return

    print(f"\nConnecting to Snowflake ({connection_name})...")
    conn = snowflake.connector.connect(connection_name=connection_name)
    cursor = conn.cursor()

    try:
        cursor.execute(f"""
            CREATE OR REPLACE TABLE {target_table} (
                input_query VARCHAR,
                output VARIANT
            )
        """)
        print(f"Created table {target_table}")

        for r in rows:
            gt_escaped = r["ground_truth"].replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
            sql = f"""
                INSERT INTO {target_table} (input_query, output)
                SELECT
                    '{r["question"].replace("'", "''")}',
                    PARSE_JSON('{{"ground_truth_output": "{gt_escaped}"}}')
            """
            cursor.execute(sql)

        cursor.execute(f"SELECT COUNT(*) FROM {target_table}")
        count = cursor.fetchone()[0]
        print(f"Inserted {count} rows into {target_table}")

        cursor.execute(f"SELECT input_query, output:ground_truth_output::STRING FROM {target_table} LIMIT 2")
        for sample in cursor.fetchall():
            print(f"\n  Q: {str(sample[0])[:80]}")
            print(f"  A: {str(sample[1])[:80]}")

        print(f"\nNext: upload your YAML config and run the evaluation.")
        print(f"  See README.md steps 2-5.")

    finally:
        cursor.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Load evaluation dataset from CSV into Snowflake"
    )
    parser.add_argument("--csv", required=True, help="Path to CSV file with questions and ground truth")
    parser.add_argument("--target-table", required=True, help="Target Snowflake table (DB.SCHEMA.TABLE)")
    parser.add_argument("--connection", default=os.getenv("SNOWFLAKE_CONNECTION_NAME", "default"), help="Snowflake connection name")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to Snowflake")

    args = parser.parse_args()

    load_dataset(
        csv_path=args.csv,
        target_table=args.target_table,
        connection_name=args.connection,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
