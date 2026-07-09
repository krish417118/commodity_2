# ==========================================
# Commodity & Macro Intelligence Dashboard
# Database-Backed Analytics Layer (Day 4)
# ==========================================

import pandas as pd
import numpy as np
import os
from fredapi import Fred
from dotenv import load_dotenv

# Updated import path to match your folder structure
from database.db import init_db, upsert_dataframe, query

# ==========================================
# INITIALIZATION
# ==========================================

load_dotenv()
FRED_API_KEY = os.environ.get("FRED_API_KEY")

if not FRED_API_KEY:
    raise RuntimeError("FRED_API_KEY not found in .env file.")

conn = init_db()

# ==========================================
# 1. LOAD & PIVOT RAW DATA
# ==========================================
print("Loading raw prices from database...")

raw_df = query(conn, "SELECT * FROM raw_prices")
raw_df["date"] = pd.to_datetime(raw_df["date"])

# FIX: Aggressively coerce the 'close' column to numeric. 
# Any sneaky strings or bad types will be safely turned into NaN.
raw_df["close"] = pd.to_numeric(raw_df["close"], errors="coerce")

# Pivot from long (db schema) to wide (pandas friendly) for easy math
price_matrix = raw_df.pivot(index="date", columns="asset", values="close").sort_index()

# ==========================================
# 2. TIME-SERIES METRICS (Old Sections 1, 3, 4, 5)
# ==========================================
print("Calculating returns, volatility, and drawdowns...")

# Old Section 1: Daily Returns (1 line replaces 15 lines)
returns = price_matrix.pct_change(fill_method=None)

# Old Section 3: 30D Volatility (1 line replaces 15 lines)
vol_30d = returns.rolling(30).std()

# Old Section 5: Rolling Returns (2 lines replace 20 lines)
rolling_30d = (price_matrix / price_matrix.shift(30)) - 1
rolling_90d = (price_matrix / price_matrix.shift(90)) - 1

# Old Section 4: 60D Drawdown (2 lines replace 15 lines)
rolling_peak = price_matrix.rolling(60).max()
drawdown_60d = (price_matrix - rolling_peak) / rolling_peak

def melt_metric(df, metric_name):
    """Helper to shape wide pandas math back into the long SQLite schema."""
    melted = df.reset_index().melt(id_vars="date", var_name="asset", value_name=metric_name)
    melted["date"] = melted["date"].dt.strftime("%Y-%m-%d")
    return melted

# Merge all these metrics together
df_ret = melt_metric(returns, "daily_return")
df_vol = melt_metric(vol_30d, "volatility_30d")
df_dd = melt_metric(drawdown_60d, "drawdown_60d")
df_r30 = melt_metric(rolling_30d, "rolling_return_30d")
df_r90 = melt_metric(rolling_90d, "rolling_return_90d")

analytics_returns = (
    df_ret
    .merge(df_vol, on=["date", "asset"])
    .merge(df_dd, on=["date", "asset"])
    .merge(df_r30, on=["date", "asset"])
    .merge(df_r90, on=["date", "asset"])
)

# Clean up empty rows and push to database
analytics_returns.dropna(subset=["daily_return", "volatility_30d", "drawdown_60d"], how="all", inplace=True)
n_ret = upsert_dataframe(conn, "analytics_returns", analytics_returns)
print(f"Upserted {n_ret} rows into analytics_returns.")


# ==========================================
# 3. RISK SUMMARY (Old Sections 2 & 7)
# ==========================================
print("Generating point-in-time risk summary...")

summary_data = []
asof_date = pd.Timestamp.today().strftime("%Y-%m-%d")

# We use a loop here because we are calculating single summary numbers per asset, 
# not a time-series matrix.
for asset in price_matrix.columns:
    asset_prices = price_matrix[asset].dropna()
    if asset_prices.empty:
        continue

    # Old Section 2: Cumulative / Total Return
    total_ret = ((asset_prices.iloc[-1] / asset_prices.iloc[0]) - 1) * 100

    # Old Section 7: 60-Day Sharpe & Risk Profile
    asset_returns = asset_prices.pct_change(fill_method=None).dropna()
    latest_returns = asset_returns.tail(60)
    
    avg_ret = latest_returns.mean() * 100
    vol = latest_returns.std() * 100
    sharpe = avg_ret / vol if vol != 0 else 0
    
    latest_prices = asset_prices.tail(60)
    peak = latest_prices.cummax()
    dd = ((latest_prices - peak) / peak).min() * 100

    summary_data.append({
        "asof_date": asof_date,
        "asset": asset,
        "total_return_pct": round(total_ret, 2),
        "avg_daily_return_pct": round(avg_ret, 4),
        "daily_volatility_pct": round(vol, 4),
        "sharpe_ratio": round(sharpe, 4),
        "max_drawdown_pct": round(dd, 2)
    })

risk_summary = pd.DataFrame(summary_data)
n_risk = upsert_dataframe(conn, "risk_summary", risk_summary)
print(f"Upserted {n_risk} rows into risk_summary.")


# ==========================================
# 4. MACRO DATA & CORRELATION (Old Section 6)
# ==========================================
print("Updating macro factors and correlations...")

fred = Fred(api_key=FRED_API_KEY)

def fetch_and_upsert_fred(series_id, series_name):
    try:
        s = fred.get_series(series_id).reset_index()
        s.columns = ["date", "value"]
        s["date"] = s["date"].dt.strftime("%Y-%m-%d")
        s["series"] = series_name
        s["value"] = pd.to_numeric(s["value"], errors="coerce")
        s = s.dropna()
        upsert_dataframe(conn, "macro_data", s)
    except Exception as e:
        print(f"  -> WARNING: Failed to fetch {series_name} from FRED: {e}")

# Pull fresh FRED data
fetch_and_upsert_fred("DGS10", "US10Y_Yield")
fetch_and_upsert_fred("CPIAUCSL", "CPI")

# Pull all macro data from the DB (this includes DXY, which market_data.py already inserted)
macro_df = query(conn, "SELECT * FROM macro_data")
macro_df["date"] = pd.to_datetime(macro_df["date"])
macro_wide = macro_df.pivot(index="date", columns="series", values="value").sort_index()

# Align macro dates to our core asset trading dates (Merge Asof)
aligned_macro = pd.merge_asof(
    pd.DataFrame(index=price_matrix.index), 
    macro_wide, 
    left_index=True, 
    right_index=True, 
    direction="backward"
)

# Build correlation matrix
corr_matrix = pd.DataFrame(index=price_matrix.index)
for col in price_matrix.columns:
    corr_matrix[col] = returns[col]

if "US10Y_Yield" in aligned_macro.columns:
    corr_matrix["US10Y_Yield"] = aligned_macro["US10Y_Yield"]
if "CPI" in aligned_macro.columns:
    corr_matrix["CPI_Inflation"] = aligned_macro["CPI"].pct_change(fill_method=None)
if "DXY_Close" in aligned_macro.columns:
    corr_matrix["DXY_Index"] = aligned_macro["DXY_Close"].pct_change(fill_method=None)

# Calculate and push to DB
corr = corr_matrix.corr()
corr_long = corr.reset_index().melt(id_vars="index", var_name="factor_b", value_name="correlation")
corr_long.rename(columns={"index": "factor_a"}, inplace=True)
corr_long["asof_date"] = asof_date
corr_long = corr_long[["asof_date", "factor_a", "factor_b", "correlation"]].dropna()

n_corr = upsert_dataframe(conn, "correlation_matrix", corr_long)
print(f"Upserted {n_corr} rows into correlation_matrix.")

conn.close()
print("\nAll database analytics updated successfully!")