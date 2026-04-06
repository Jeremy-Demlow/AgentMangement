"""
Fast reload of ski resort data from local CSV files to Snowflake.
Uses PUT + COPY INTO for efficient bulk loading.
"""

import argparse
import logging
from pathlib import Path
from snowflake_connection import SnowflakeConnection
from config import DATABASE, RAW_SCHEMA

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Table mappings: local filename -> Snowflake table name
TABLE_MAPPINGS = {
    'customers.csv.gz': 'CUSTOMERS',
    'lift_scans.csv.gz': 'LIFT_SCANS',
    'pass_usage.csv.gz': 'PASS_USAGE',
    'ticket_sales.csv.gz': 'TICKET_SALES',
    'rentals.csv.gz': 'RENTALS',
    'food_beverage.csv.gz': 'FOOD_BEVERAGE',
    'weather_conditions.csv.gz': 'WEATHER_CONDITIONS',
    'staffing_schedule.csv.gz': 'STAFFING_SCHEDULE',
    'marketing_touches.csv.gz': 'MARKETING_TOUCHES'
}

def main():
    parser = argparse.ArgumentParser(description="Fast reload data from local CSV files to Snowflake.")
    parser.add_argument('--data-dir', type=str, default='../ski_resort_data',
                        help='Directory containing CSV.gz files (default: ../ski_resort_data)')
    parser.add_argument('--connection', type=str, default='blackline',
                        help='Snow CLI connection name (default: blackline)')
    parser.add_argument('--truncate', action='store_true',
                        help='Truncate tables before loading (default: replace with overwrite)')
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        logger.error(f"Data directory not found: {data_dir}")
        return

    logger.info("=" * 80)
    logger.info("FAST RELOAD FROM LOCAL CSV FILES")
    logger.info("=" * 80)
    logger.info(f"Data directory: {data_dir.absolute()}")

    # Connect to Snowflake
    conn = SnowflakeConnection.from_snow_cli(args.connection)
    conn.execute(f"USE DATABASE {DATABASE}")
    conn.execute(f"USE SCHEMA {RAW_SCHEMA}")

    # Create a stage for loading
    conn.execute("CREATE STAGE IF NOT EXISTS ski_resort_stage FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '\"' COMPRESSION = GZIP)")

    for filename, table_name in TABLE_MAPPINGS.items():
        file_path = data_dir / filename
        if not file_path.exists():
            logger.warning(f"Skipping {table_name} - file not found: {file_path}")
            continue

        logger.info(f"Loading {table_name} from {filename}...")

        # PUT file to stage
        put_cmd = f"PUT 'file://{file_path.absolute()}' @ski_resort_stage/{table_name}/ AUTO_COMPRESS=FALSE OVERWRITE=TRUE"
        conn.execute(put_cmd)

        # Truncate if requested
        if args.truncate:
            conn.execute(f"TRUNCATE TABLE {table_name}")

        # COPY INTO table
        copy_cmd = f"""
            COPY INTO {table_name}
            FROM @ski_resort_stage/{table_name}/
            FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '"' COMPRESSION = GZIP)
            PURGE = TRUE
            ON_ERROR = CONTINUE
        """
        result = conn.fetch(copy_cmd)

        # Get count
        count = conn.fetch(f"SELECT COUNT(*) FROM {table_name}")[0][0]
        logger.info(f"  ✓ {table_name}: {count:,} rows loaded")

    # Clean up stage
    conn.execute("REMOVE @ski_resort_stage")

    logger.info("\n" + "=" * 80)
    logger.info("RELOAD COMPLETE!")
    logger.info("=" * 80)

    # Verification summary
    results = conn.fetch("""
        SELECT 'CUSTOMERS' as t, COUNT(*) as c FROM CUSTOMERS
        UNION ALL SELECT 'LIFT_SCANS', COUNT(*) FROM LIFT_SCANS
        UNION ALL SELECT 'PASS_USAGE', COUNT(*) FROM PASS_USAGE
        UNION ALL SELECT 'TICKET_SALES', COUNT(*) FROM TICKET_SALES
        UNION ALL SELECT 'RENTALS', COUNT(*) FROM RENTALS
        UNION ALL SELECT 'FOOD_BEVERAGE', COUNT(*) FROM FOOD_BEVERAGE
        UNION ALL SELECT 'WEATHER_CONDITIONS', COUNT(*) FROM WEATHER_CONDITIONS
        UNION ALL SELECT 'STAFFING_SCHEDULE', COUNT(*) FROM STAFFING_SCHEDULE
        UNION ALL SELECT 'MARKETING_TOUCHES', COUNT(*) FROM MARKETING_TOUCHES
    """)

    for r in results:
        logger.info(f"  {r[0]:<20} {r[1]:>10,} rows")

    conn.close()
    logger.info("\n✓ Ready for dbt run!")

if __name__ == "__main__":
    main()
