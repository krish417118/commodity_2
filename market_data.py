# ==========================================
# Commodity & Macro Intelligence Dashboard
# Data Collection + Cleaning Pipeline
# ==========================================

import pandas as pd
import yfinance as yf
import os


# ==========================================
# Create Project Folders
# ==========================================

os.makedirs("data/raw", exist_ok=True)
os.makedirs("data/cleaned", exist_ok=True)


# ==========================================
# PART 2 - DATA COLLECTION
# Download Market Data
# ==========================================
#
# NOTE (Day 1 fix): period was "5mo". Five months is too short a
# history to compute stable 90-day rolling stats or a trustworthy
# correlation matrix (you barely get ~2 independent 90-day windows).
# Bumped to 2 years for backfill. Once the SQLite incremental-load
# step is in place (Day 3), this becomes a one-time backfill and daily
# runs will only ever pull the newest rows.

assets = {
    "gold": "GC=F",
    "oil": "CL=F",
    "btc": "BTC-USD",
    "eurusd": "EURUSD=X",
    # Automated replacement for the old manual data/DXY.csv (Day 1 fix).
    # DX-Y.NYB is the ICE US Dollar Index. If this ticker returns empty
    # data in your environment, swap it for "DX=F" (Dollar Index futures).
    "dxy": "DX-Y.NYB",
    # Optional (not required for Day 1): uncomment to track Henry Hub
    # natural gas alongside the other assets -- ties the dashboard
    # directly to a gas & power company's core commodity exposure.
    # "natgas": "NG=F",
}


def download_market_data(name, ticker, period="2y", interval="1d"):

    print(f"\nDownloading {name.upper()} data...")

    df = yf.download(
        ticker,
        period=period,
        interval=interval,
        auto_adjust=False,
    )

    if df.empty:
        print(f"WARNING: no data returned for {name.upper()} ({ticker}). "
              f"Check the ticker symbol.")
        return df

    # Move Date index into a column
    df.reset_index(inplace=True)

    file_path = f"data/raw/{name}.csv"

    df.to_csv(file_path, index=False)

    print(f"Saved raw data: {file_path}")

    return df


# Download all assets

for name, ticker in assets.items():
    download_market_data(name, ticker)


print("\nRaw market datasets created successfully!")


# ==========================================
# PART 3 - DATA CLEANING
# Create analyst-ready datasets
# ==========================================

def clean_data(file_path):
    """
    Clean raw market datasets
    """

    df = pd.read_csv(file_path)

    # Convert Date to datetime
    df["Date"] = pd.to_datetime(df["Date"])

    # Sort by date and reset to a clean sequential index.
    # (Day 1 fix: downstream analytics assumes a 0..n-1 index when
    # aligning derived Series/DataFrames by position -- sorting
    # without reset_index left the old non-sequential index in place,
    # which is fragile once you start joining frames back together.)
    df = df.sort_values("Date").reset_index(drop=True)

    # Remove duplicate rows
    df = df.drop_duplicates()

    # Check missing values
    print("\nMissing Values:")
    print(df.isnull().sum())

    # Fill missing values using previous day's value
    df = df.ffill()

    # Remove remaining missing rows
    df = df.dropna()

    # Standardize column names
    df.columns = [
        column.replace(" ", "_")
        for column in df.columns
    ]

    return df


# Raw files

raw_files = {
    "gold": "data/raw/gold.csv",
    "oil": "data/raw/oil.csv",
    "btc": "data/raw/btc.csv",
    "forex": "data/raw/eurusd.csv",
    "dxy": "data/raw/dxy.csv",
}


# Clean all datasets

cleaned_data = {}

for asset, path in raw_files.items():

    print(f"\nCleaning {asset.upper()} dataset...")

    df = clean_data(path)

    cleaned_data[asset] = df

    output_path = f"data/cleaned/clean_{asset}.csv"

    df.to_csv(
        output_path,
        index=False
    )

    print(f"Saved cleaned data: {output_path}")


print("\nAll clean datasets created successfully!")


# ==========================================
# Merge All Assets
# Create master_market_data.csv
# ==========================================
# NOTE: DXY is intentionally left OUT of master_market_data.csv.
# It's a macro comparison factor (used for correlation), not one of
# the four core tracked assets -- market_analytics.py reads
# data/cleaned/clean_dxy.csv directly for that purpose.

gold = cleaned_data["gold"][["Date", "Close"]]
oil = cleaned_data["oil"][["Date", "Close"]]
btc = cleaned_data["btc"][["Date", "Close"]]
forex = cleaned_data["forex"][["Date", "Close"]]


# Rename close price columns

gold = gold.rename(
    columns={"Close": "Gold_Close"}
)

oil = oil.rename(
    columns={"Close": "Oil_Close"}
)

btc = btc.rename(
    columns={"Close": "BTC_Close"}
)

forex = forex.rename(
    columns={"Close": "EURUSD_Close"}
)


# Merge using common dates

master_data = (
    gold
    .merge(oil, on="Date", how="inner")
    .merge(btc, on="Date", how="inner")
    .merge(forex, on="Date", how="inner")
)


# Final sorting

master_data = master_data.sort_values("Date").reset_index(drop=True)


# Save master dataset

master_data.to_csv(
    "data/cleaned/master_market_data.csv",
    index=False
)


print("\nMaster market dataset created successfully!")

print("\nPreview:")
print(master_data.head())