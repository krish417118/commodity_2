# ==========================================
# Commodity & Macro Intelligence Dashboard
# Database-Backed Analytics Layer
# ==========================================

import pandas as pd
import numpy as np
import os
from fredapi import Fred
from dotenv import load_dotenv

from database.db import init_db, upsert_dataframe, query

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
raw_df["close"] = pd.to_numeric(raw_df["close"], errors="coerce")

price_matrix = raw_df.pivot(index="date", columns="asset", values="close").sort_index()

# ==========================================
# 2. TIME-SERIES METRICS (15D Lookbacks)
# ==========================================
print("Calculating returns, volatility, and drawdowns...")
returns = price_matrix.pct_change(fill_method=None)
vol_15d = returns.rolling(15).std()
rolling_15d = (price_matrix / price_matrix.shift(15)) - 1
rolling_30d = (price_matrix / price_matrix.shift(30)) - 1
rolling_peak = price_matrix.rolling(15).max()
drawdown_15d = (price_matrix - rolling_peak) / rolling_peak

def melt_metric(df, metric_name):
    melted = df.reset_index().melt(id_vars="date", var_name="asset", value_name=metric_name)
    melted["date"] = melted["date"].dt.strftime("%Y-%m-%d")
    return melted

df_ret = melt_metric(returns, "daily_return")
df_vol = melt_metric(vol_15d, "volatility_15d")
df_dd = melt_metric(drawdown_15d, "drawdown_15d")
df_r15 = melt_metric(rolling_15d, "rolling_return_15d")
df_r30 = melt_metric(rolling_30d, "rolling_return_30d")

analytics_returns = (
    df_ret
    .merge(df_vol, on=["date", "asset"])
    .merge(df_dd, on=["date", "asset"])
    .merge(df_r15, on=["date", "asset"])
    .merge(df_r30, on=["date", "asset"])
)

analytics_returns.dropna(subset=["daily_return", "volatility_15d", "drawdown_15d"], how="all", inplace=True)
n_ret = upsert_dataframe(conn, "analytics_returns", analytics_returns)
print(f"Upserted {n_ret} rows into analytics_returns.")

# ==========================================
# 3. RISK SUMMARY (Last 15 Days Only)
# ==========================================
print("Generating 15-day point-in-time risk summary...")
summary_data = []
asof_date = pd.Timestamp.today().strftime("%Y-%m-%d")

for asset in price_matrix.columns:
    asset_prices = price_matrix[asset].dropna().tail(15)
    if asset_prices.empty or len(asset_prices) < 2: continue

    total_ret = ((asset_prices.iloc[-1] / asset_prices.iloc[0]) - 1) * 100
    asset_returns = asset_prices.pct_change(fill_method=None).dropna()
    avg_ret = asset_returns.mean() * 100
    vol = asset_returns.std() * 100
    sharpe = avg_ret / vol if vol != 0 else 0
    peak = asset_prices.cummax()
    dd = ((asset_prices - peak) / peak).min() * 100

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
# 4. MACRO DATA & CORRELATION (Last 15 Days)
# ==========================================
print("Updating macro factors and correlations (15-day lookback)...")
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
        print(f"  -> WARNING: Failed to fetch {series_name}: {e}")

fetch_and_upsert_fred("DGS10", "US10Y_Yield")
fetch_and_upsert_fred("CPIAUCSL", "CPI")

macro_df = query(conn, "SELECT * FROM macro_data")
macro_df["date"] = pd.to_datetime(macro_df["date"])
macro_wide = macro_df.pivot(index="date", columns="series", values="value").sort_index()

aligned_macro = pd.merge_asof(
    pd.DataFrame(index=price_matrix.index), 
    macro_wide, left_index=True, right_index=True, direction="backward"
)

corr_matrix = pd.DataFrame(index=price_matrix.index)
for col in price_matrix.columns: corr_matrix[col] = returns[col]
if "US10Y_Yield" in aligned_macro.columns: corr_matrix["US10Y_Yield"] = aligned_macro["US10Y_Yield"]
if "CPI" in aligned_macro.columns: corr_matrix["CPI_Inflation"] = aligned_macro["CPI"].pct_change(fill_method=None)
if "DXY_Close" in aligned_macro.columns: corr_matrix["DXY_Index"] = aligned_macro["DXY_Close"].pct_change(fill_method=None)

corr = corr_matrix.tail(15).corr()
corr_long = corr.reset_index().melt(id_vars="index", var_name="factor_b", value_name="correlation")
corr_long.rename(columns={"index": "factor_a"}, inplace=True)
corr_long["asof_date"] = asof_date
corr_long = corr_long[["asof_date", "factor_a", "factor_b", "correlation"]].dropna()

n_corr = upsert_dataframe(conn, "correlation_matrix", corr_long)
print(f"Upserted {n_corr} rows into correlation_matrix.")

conn.close()
print("\nAll database analytics updated successfully!")