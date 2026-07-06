# ==========================================
# Commodity & Macro Intelligence Dashboard
# Statistical Analytics Layer
# ==========================================

import pandas as pd
import os
from fredapi import Fred   # pip install fredapi
from dotenv import load_dotenv  # pip install python-dotenv

# ==========================================
# Load secrets from .env (Day 1 fix)
# ==========================================
# Never hardcode API keys in source files. Create a local .env file
# (see .env.example) containing:
#   FRED_API_KEY=your_real_key_here
# and add .env to .gitignore before your first commit.

load_dotenv()

FRED_API_KEY = os.environ.get("FRED_API_KEY")

if not FRED_API_KEY:
    raise RuntimeError(
        "FRED_API_KEY not found. Create a .env file (see .env.example) "
        "with FRED_API_KEY=your_key, or export it as an environment variable."
    )


# ==========================================
# Create output folder
# ==========================================

os.makedirs(
    "analysis/outputs",
    exist_ok=True
)


# ==========================================
# Load Master Dataset
# ==========================================

df = pd.read_csv(
    "data/cleaned/master_market_data.csv"
)

df["Date"] = pd.to_datetime(df["Date"])

# Day 1 fix: reset_index after sorting so every Series/DataFrame we
# derive from df below shares the same clean 0..n-1 index. Several
# steps later in this script assign one frame's column into another
# (e.g. returns_matrix["US10Y_Yield"] = macro_df["US10Y_Yield"]) --
# pandas aligns those assignments by index label, so if df kept a
# shuffled index after sort_values, those assignments could silently
# mismatch rows.
df = df.sort_values("Date").reset_index(drop=True)


# Asset columns
assets = {
    "Gold": "Gold_Close",
    "Oil": "Oil_Close",
    "Bitcoin": "BTC_Close",
    "EURUSD": "EURUSD_Close"
}

# Convert all asset prices to numeric once
for column in assets.values():
    df[column] = pd.to_numeric(df[column], errors="coerce")

# ==========================================
# 1. DAILY RETURNS
# ==========================================

returns_list = []   # a container holding multiple DataFrames.

for asset, column in assets.items():
    temp = pd.DataFrame()
    temp["Date"] = df["Date"]
    temp["Asset"] = asset

    # Convert to numeric (force errors to NaN if bad data)
    temp["Close"] = pd.to_numeric(df[column], errors="coerce")

    temp["Daily_Return"] = temp["Close"].pct_change()
    returns_list.append(temp)


daily_returns = pd.concat(
    returns_list,
    ignore_index=True
)

daily_returns.to_csv(
    "analysis/outputs/daily_returns.csv",
    index=False
)


print("Daily returns created")


# ==========================================
# 2. CUMULATIVE RETURNS
# ==========================================

cumulative_summary = []

for asset, column in assets.items():

    daily_return = (
        df[column]
        .pct_change()
    )

    cumulative = (
        (1 + daily_return)
        .cumprod()
    )

    total_return = (
        cumulative.iloc[-1] - 1
    ) * 100


    cumulative_summary.append({
        "Asset": asset,
        "Total_Return_%": round(total_return, 2)
    })


cumulative_returns = pd.DataFrame(
    cumulative_summary
)


cumulative_returns.to_csv(
    "analysis/outputs/cumulative_returns.csv",
    index=False
)


print("Cumulative returns created")


# ==========================================
# 3. 30-Day VOLATILITY
# ==========================================

volatility_list = []


for asset, column in assets.items():

    temp = pd.DataFrame()

    temp["Date"] = df["Date"]
    temp["Asset"] = asset

    temp["30D_Volatility"] = (
        df[column]
        .pct_change()
        .rolling(30)
        .std()
    )

    volatility_list.append(temp)


volatility = pd.concat(
    volatility_list,
    ignore_index=True
)


volatility.to_csv(
    "analysis/outputs/volatility.csv",
    index=False
)


print("Volatility analysis created")


# ==========================================
# 4. ROLLING DRAWDOWN
# ==========================================

drawdown_list = []

for asset, column in assets.items():
    temp = pd.DataFrame()
    temp["Date"] = df["Date"]
    temp["Asset"] = asset

    # Rolling 60-day peak
    rolling_peak = pd.to_numeric(df[column], errors="coerce").rolling(60).max()

    # Rolling drawdown
    temp["Drawdown_60D"] = (pd.to_numeric(df[column], errors="coerce") - rolling_peak) / rolling_peak

    drawdown_list.append(temp)

drawdown_60d = pd.concat(drawdown_list, ignore_index=True)

drawdown_60d.to_csv("analysis/outputs/drawdown_60d.csv", index=False)

print("60-day rolling drawdown analysis created")


# ==========================================
# 5. ROLLING RETURNS
# ==========================================

rolling_list = []


for asset, column in assets.items():

    temp = pd.DataFrame()

    temp["Date"] = df["Date"]
    temp["Asset"] = asset


    temp["30D_Return"] = (
       pd.to_numeric( df[column], errors="coerce") /
         pd.to_numeric( df[column], errors="coerce").shift(30)
    ) - 1


    temp["90D_Return"] = (
         pd.to_numeric( df[column], errors="coerce")/
         pd.to_numeric( df[column], errors="coerce").shift(90)
    ) - 1


    rolling_list.append(temp)


rolling_returns = pd.concat(
    rolling_list,
    ignore_index=True
)


rolling_returns.to_csv(
    "analysis/outputs/rolling_returns.csv",
    index=False
)


print("Rolling returns created")


# ==========================================
# 6. CORRELATION MATRIX
# ==========================================

# -------------------------------
#  Load Macro Data
# -------------------------------
fred = Fred(api_key=FRED_API_KEY)

# US 10Y Treasury Yield (daily, series ID: DGS10)
us10y_df = fred.get_series("DGS10").reset_index()
us10y_df.columns = ["Date", "US10Y_Yield"]
us10y_df["Date"] = pd.to_datetime(us10y_df["Date"])
us10y_df = us10y_df.dropna().sort_values("Date")

# CPI Inflation (monthly, series ID: CPIAUCSL)
cpi_df = fred.get_series("CPIAUCSL").reset_index()
cpi_df.columns = ["Date", "CPI"]
cpi_df["Date"] = pd.to_datetime(cpi_df["Date"])
cpi_df = cpi_df.dropna().sort_values("Date")

# DXY - now collected automatically by market_data.py (Day 1 fix,
# replaces the old manual data/DXY.csv read)
dxy_df = pd.read_csv(
    "data/cleaned/clean_dxy.csv",
    parse_dates=["Date"]
)

dxy_df = dxy_df[["Date", "Close"]].rename(
    columns={"Close": "DXY_Close"}
)

dxy_df["DXY_Close"] = pd.to_numeric(
    dxy_df["DXY_Close"],
    errors="coerce"
)
dxy_df = dxy_df.dropna().sort_values("Date")

# -------------------------------
# Align macro data to asset trading days (Day 1 fix)
# -------------------------------
# The original approach used .reindex(df["Date"]), which only keeps
# EXACT date matches. CPI is monthly and DGS10 follows the US bank
# holiday calendar (not the same calendar as crypto/FX trading days),
# so an exact reindex left almost every row as NaN -- silently
# breaking the correlation numbers, especially against CPI.
#
# merge_asof(direction="backward") instead carries forward the most
# recently published value onto every asset trading day, which is the
# standard way to join a low-frequency series onto a higher-frequency
# one. One consequence worth knowing for your write-up: CPI_Inflation
# below will show ~0% on most days and a step change only on the days
# a new CPI print takes effect -- that's a known simplification, not a
# bug. A future improvement would be to also compute a separate
# monthly-frequency correlation table.

macro_df = pd.DataFrame({"Date": df["Date"]})  # already sorted + reset above

macro_df = pd.merge_asof(macro_df, us10y_df, on="Date", direction="backward")
macro_df = pd.merge_asof(macro_df, cpi_df, on="Date", direction="backward")
macro_df = pd.merge_asof(macro_df, dxy_df, on="Date", direction="backward")

# -------------------------------
# Build Returns + Macro Matrix
# -------------------------------
returns_matrix = pd.DataFrame()
returns_matrix["Date"] = df["Date"]

# Asset returns
for asset, column in assets.items():
    returns_matrix[asset] = pd.to_numeric(df[column], errors="coerce").pct_change()

# Macro factors
returns_matrix["US10Y_Yield"] = macro_df["US10Y_Yield"]           # level, not a return
returns_matrix["CPI_Inflation"] = macro_df["CPI"].pct_change()     # month-over-month % change
returns_matrix["DXY_Index"] = (                                    # daily % change
    pd.to_numeric(
        macro_df["DXY_Close"],
        errors="coerce"
    ).pct_change(fill_method=None)
)  

# -------------------------------
# Correlation Matrix (Last 30 Trading Days)
# -------------------------------

# Keep only the latest 30 trading days
returns_last30 = returns_matrix.tail(30)

# Remove Date column and rows with missing values
correlation = (
    returns_last30
    .drop(columns=["Date"])
    .dropna()
    .corr()
)

correlation.to_csv(
    "analysis/outputs/correlation_30D_matrix.csv",
    index=True
)

print("30-day macro correlation matrix created")

# Full return + macro series also saved for Power BI / further analysis.
# (Day 1 fix: this used to be computed a second time from scratch in a
# separate "8. return matrix" section at the bottom of the script --
# same numbers, wasted computation. Saving it here once instead.)
returns_matrix.to_csv("analysis/outputs/returns_matrix.csv", index=False)

print("Returns matrix created")


# ==========================================
# 7. SHARPE RATIO + RISK/RETURN SUMMARY
# ==========================================


summary = []

for asset, column in assets.items():

    # Daily returns
    returns = (
        pd.to_numeric(df[column], errors='coerce')
        .pct_change()
        .dropna()
    )

    # --- Restrict to latest 60 returns ---
    latest_returns = returns.tail(60)

    avg_return = latest_returns.mean() * 100
    volatility = latest_returns.std() * 100
    sharpe = avg_return / volatility

    # --- Drawdown from latest 60 prices ---
    latest_prices = pd.to_numeric(df[column], errors='coerce').tail(60)
    running_peak = latest_prices.cummax()
    drawdown_series = (latest_prices - running_peak) / running_peak
    max_drawdown = drawdown_series.min() * 100

    summary.append({
        "Asset": asset,
        "Average_Daily_Return_%": round(avg_return, 4),
        "Daily_Volatility_%": round(volatility, 4),
        "Sharpe_Ratio": round(sharpe, 4),
        "Max_Drawdown_%": round(max_drawdown, 2)
    })

risk_return_summary = pd.DataFrame(summary)

risk_return_summary.to_csv(
    "analysis/outputs/risk_return_summary.csv",
    index=False
)

print("Risk-return summary created")

print("\nAll analytics outputs written to analysis/outputs/")