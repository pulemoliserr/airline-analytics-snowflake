import os
import pandas as pd
import snowflake.connector

# Load local .env variables if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

print("Connecting to Snowflake...")
conn = snowflake.connector.connect(
    account=os.environ["SNOWFLAKE_ACCOUNT"],
    user=os.environ["SNOWFLAKE_USER"],
    password=os.environ["SNOWFLAKE_PASSWORD"],
    warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
    database=os.environ["SNOWFLAKE_DATABASE"],
    schema=os.environ["SNOWFLAKE_SCHEMA"],
    role=os.environ["SNOWFLAKE_ROLE"]
)

os.makedirs("data", exist_ok=True)

tables = {
    "AIRLINE_ANALYTICS.BACKFILL.gld_daily_airport_traffic": "data/gld_daily_airport_traffic.csv",
    "AIRLINE_ANALYTICS.BACKFILL.gld_hourly_flight_activity": "data/gld_hourly_flight_activity.csv",
    "AIRLINE_ANALYTICS.BACKFILL.gld_airline_traffic": "data/gld_airline_traffic.csv",
    "AIRLINE_ANALYTICS.BACKFILL.gld_route_analysis": "data/gld_route_analysis.csv"
}

for table_name, file_path in tables.items():
    print(f"Exporting {table_name}...")
    query = f"SELECT * FROM {table_name}"
    df = pd.read_sql(query, conn)
    df.to_csv(file_path, index=False)
    print(f"Saved {len(df)} rows to {file_path}")

conn.close()
print("All tables successfully exported to the 'data/' folder!")