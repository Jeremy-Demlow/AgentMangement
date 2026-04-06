"""
Load seed data (lifts, locations, products, ticket types) to Snowflake RAW schema
"""

import pandas as pd
import logging
from snowflake_connection import SnowflakeConnection
from config import DATABASE, RAW_SCHEMA

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Load seed data to Snowflake"""
    logger.info("Loading seed data to Snowflake RAW schema...")

    # Connect to Snowflake
    conn = SnowflakeConnection.from_snow_cli('blackline')
    conn.execute(f"USE SCHEMA {DATABASE}.{RAW_SCHEMA}")

    # Load lift metadata
    lifts_df = pd.read_csv('../dbt_ski_resort/seeds/lift_metadata.csv')
    logger.info(f"Loading {len(lifts_df)} lifts...")
    lifts_df.columns = lifts_df.columns.str.upper()
    conn.session.write_pandas(lifts_df, table_name="LIFTS", auto_create_table=False, overwrite=False)

    # Load locations
    locations_df = pd.read_csv('../dbt_ski_resort/seeds/location_metadata.csv')
    logger.info(f"Loading {len(locations_df)} locations...")
    locations_df.columns = locations_df.columns.str.upper()
    conn.session.write_pandas(locations_df, table_name="LOCATIONS", auto_create_table=False, overwrite=False)

    # Load products
    products_df = pd.read_csv('../dbt_ski_resort/seeds/product_catalog.csv')
    logger.info(f"Loading {len(products_df)} products...")
    products_df.columns = products_df.columns.str.upper()
    conn.session.write_pandas(products_df, table_name="PRODUCTS", auto_create_table=False, overwrite=False)

    # Load ticket types
    tickets_df = pd.read_csv('../dbt_ski_resort/seeds/ticket_type_metadata.csv')
    logger.info(f"Loading {len(tickets_df)} ticket types...")
    tickets_df.columns = tickets_df.columns.str.upper()
    conn.session.write_pandas(tickets_df, table_name="TICKET_TYPES", auto_create_table=False, overwrite=False)

    # Verify
    results = conn.fetch("""
        SELECT 'LIFTS' as table_name, COUNT(*) as count FROM LIFTS
        UNION ALL SELECT 'LOCATIONS', COUNT(*) FROM LOCATIONS
        UNION ALL SELECT 'PRODUCTS', COUNT(*) FROM PRODUCTS
        UNION ALL SELECT 'TICKET_TYPES', COUNT(*) FROM TICKET_TYPES
    """)

    logger.info("\nSeed data loaded:")
    for row in results:
        logger.info(f"  {row[0]}: {row[1]} rows")

    conn.close()
    logger.info("\n✓ Seed data loading complete!")

if __name__ == "__main__":
    main()
