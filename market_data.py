# ==========================================
# Commodity & Macro Intelligence Dashboard
# Incremental Data Collection Pipeline (Day 3)
# ==========================================

import pandas as pd
import yfinance as yf
from datetime import timedelta
import os

# Import our database helpers
from database.db import init_db, upsert_dataframe, query

# ==========================================
# CONFIGURATION
# ==========================================

# Core assets (map directly to the 'raw_prices' table)
# Keys match the 'asset' column in our schema
CORE_ASSETS = {
    "Gold": "GC=F",
    "Oil": "CL=F",
    "Bitcoin": "BTC-USD",
    "EURUSD": "EURUSD=X",
}

# Macro factors fetched via yfinance (maps to 'macro_data' table)
MACRO_ASSETS = {
    "DXY_Close": "DX-Y.NYB"
}

# ==========================================
# DATABASE CONNECTION & STATE CHECK
# ==========================================

def get_latest_date(conn, table, entity_col, entity_name):
    """
    Queries the database to find the most recent date we have data for a specific asset/series.
    """
    sql = f"SELECT MAX(date) as max_date FROM {table} WHERE {entity_col} = ?"
    df = query(conn, sql, params=(entity_name,))
    
    max_date_str = df['max_date'].iloc[0]
    if max_date_str:
        return pd.to_datetime(max_date_str)
    return None


def fetch_incremental_data(ticker, start_date=None, default_period="2y"):
    """
    Fetches data from yfinance. If start_date is provided, fetches from that date forward.
    Otherwise, falls back to the default backfill period.
    """
    if start_date:
        # Fetch from the day after our last record to avoid overlapping
        fetch_start = (start_date + timedelta(days=1)).strftime('%Y-%m-%d')
        print(f"  -> Fetching new data from {fetch_start} onward...")
        df = yf.download(ticker, start=fetch_start, interval="1d", auto_adjust=False)
    else:
        print(f"  -> No existing data found. Running {default_period} backfill...")
        df = yf.download(ticker, period=default_period, interval="1d", auto_adjust=False)

    if df.empty:
        print(f"  -> WARNING: No new data returned for {ticker}.")
        return df

    # FIX: Flatten the MultiIndex columns that newer yfinance versions return
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df.reset_index(inplace=True)
    return df

# ==========================================
# PIPELINE EXECUTION
# ==========================================

def run_pipeline():
    conn = init_db()
    print("Database connected. Starting incremental data pull...\n")

    # 1. Process Core Assets (raw_prices)
    for asset_name, ticker in CORE_ASSETS.items():
            print(f"Processing Core Asset: {asset_name} ({ticker})")
            
            last_date = get_latest_date(conn, "raw_prices", "asset", asset_name)
            df = fetch_incremental_data(ticker, start_date=last_date)
            
            if not df.empty:
                # Flatten columns if yfinance returns a MultiIndex
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)

                if 'Date' not in df.columns and df.index.name == 'Date':
                    df = df.reset_index()
                
                df = df.rename(columns={"Date": "date", "Close": "close"})
                df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
                df["asset"] = asset_name
                
                # --- EXPLICIT DATE BLACKLIST ---
                # Completely discard the corrupted date for all assets before processing
                df = df[df["date"] != "2026-07-06"]
                
                # Force whatever remains to be purely numeric
                df["close"] = pd.to_numeric(df["close"], errors="coerce")
                
                # Final clean and drop missing records
                clean_df = df[["date", "asset", "close"]].dropna()
                
                rows_added = upsert_dataframe(conn, "raw_prices", clean_df)
                print(f"  -> Upserted {rows_added} rows into raw_prices.\n")

    # 2. Process Macro Factors (macro_data)
    for series_name, ticker in MACRO_ASSETS.items():
        print(f"Processing Macro Factor: {series_name} ({ticker})")
        
        last_date = get_latest_date(conn, "macro_data", "series", series_name)
        df = fetch_incremental_data(ticker, start_date=last_date)
        
        if not df.empty:
            # Clean and reshape for the macro_data table (date, series, value)
            df = df.rename(columns={"Date": "date", "Close": "value"})
            df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
            df["series"] = series_name
            
            clean_df = df[["date", "series", "value"]].ffill().dropna()
            
            # Upsert
            rows_added = upsert_dataframe(conn, "macro_data", clean_df)
            print(f"  -> Upserted {rows_added} rows into macro_data.\n")

    conn.close()
    print("Data ingestion complete! SQLite database is up to date.")

if __name__ == "__main__":
    run_pipeline()