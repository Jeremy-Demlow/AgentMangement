This folder holds test data files (CSV, JSON, SQL scripts).

Rules:
- NEVER use production data — always synthetic or anonymized
- Name files to match the test case: e.g., TC-001_sample_orders.csv
- Keep files small (< 100 rows) unless the test specifically needs volume
- SQL scripts that create test data should be idempotent (CREATE OR REPLACE)
