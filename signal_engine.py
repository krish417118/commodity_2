# ==========================================
# Commodity & Macro Intelligence Dashboard
# Predictive Signal Engine - Aggressive Tuning
# ==========================================

import pandas as pd
import numpy as np

from database.db import init_db, upsert_dataframe, query

def get_macro_context(conn):
    """Fetches macro data. No longer strictly required to generate base signals."""
    sql = "SELECT date, series, value FROM macro_data"
    macro_df = query(conn, sql)
    
    if macro_df.empty:
        return pd.DataFrame()
        
    macro_df["date"] = pd.to_datetime(macro_df["date"])
    macro_df["value"] = pd.to_numeric(macro_df["value"], errors="coerce")
    
    macro_wide = macro_df.pivot(index="date", columns="series", values="value").sort_index().ffill()
    return macro_wide

def generate_gold_signals(conn, macro_df):
    print("Processing Aggressive Strategy for Gold...")
    sql = "SELECT date, asset, close FROM raw_prices WHERE asset = 'Gold' ORDER BY date"
    df = query(conn, sql)
    if df.empty: return

    df["date"] = pd.to_datetime(df["date"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")

    # FAST MOMENTUM: 5-Day vs 10-Day EMA
    df["ema_5"] = df["close"].ewm(span=5, adjust=False).mean()
    df["ema_10"] = df["close"].ewm(span=10, adjust=False).mean()

    conditions = [
        (df["ema_5"] > df["ema_10"]) & (df["close"] >= df["ema_5"]),
        (df["ema_5"] < df["ema_10"]) & (df["close"] <= df["ema_5"])
    ]
    
    df["signal"] = np.select(conditions, ["BUY", "SELL"], default="HOLD")
    df["reason"] = np.select(conditions, [
        "Aggressive BUY: Fast momentum cross & price above 5-EMA",
        "Aggressive SELL: Momentum breakdown & price below 5-EMA"
    ], default="Choppy consolidation")

    # Forward 10-day return calculation
    df["fwd_10d_ret"] = (df["close"].shift(-10) / df["close"]) - 1

    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    signals_df = df[["date", "asset", "signal", "close", "fwd_10d_ret", "reason"]].rename(columns={"close": "score"})
    
    upsert_dataframe(conn, "analytics_signals", signals_df.dropna(subset=["signal"]))
    print("✅ Success! Generated aggressive Gold signals.")


def generate_bitcoin_signals(conn, macro_df):
    print("Processing Aggressive Strategy for Bitcoin...")
    sql = "SELECT date, asset, close FROM raw_prices WHERE asset = 'Bitcoin' ORDER BY date"
    df = query(conn, sql)
    if df.empty: return

    df["date"] = pd.to_datetime(df["date"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")

    # FAST MACD: 5-period and 13-period (Highly reactive to crypto volatility)
    df["macd_line"] = df["close"].ewm(span=5, adjust=False).mean() - df["close"].ewm(span=13, adjust=False).mean()
    df["macd_signal"] = df["macd_line"].ewm(span=3, adjust=False).mean()
    
    conditions = [
        (df["macd_line"] > df["macd_signal"]),
        (df["macd_line"] < df["macd_signal"])
    ]
    
    df["signal"] = np.select(conditions, ["BUY", "SELL"], default="HOLD")
    df["reason"] = np.select(conditions, [
        "Aggressive BUY: Fast MACD (5,13) crossed bullish",
        "Aggressive SELL: Fast MACD (5,13) crossed bearish"
    ], default="Neutral Momentum")

    # Forward 10-day return calculation
    df["fwd_10d_ret"] = (df["close"].shift(-10) / df["close"]) - 1

    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    signals_df = df[["date", "asset", "signal", "close", "fwd_10d_ret", "reason"]].rename(columns={"close": "score"})
    
    upsert_dataframe(conn, "analytics_signals", signals_df.dropna(subset=["signal"]))
    print("✅ Success! Generated aggressive Bitcoin signals.")


def generate_forex_signals(conn, macro_df):
    print("Processing Aggressive Strategy for EUR/USD...")
    sql = "SELECT date, asset, close FROM raw_prices WHERE asset = 'EURUSD=X' OR asset = 'EURUSD' ORDER BY date"
    df = query(conn, sql)
    if df.empty: return

    df["date"] = pd.to_datetime(df["date"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")

    # MICRO-BREAKOUT: 3-Day Rolling High/Low Channel
    df["rolling_high_3"] = df["close"].shift(1).rolling(window=3).max()
    df["rolling_low_3"] = df["close"].shift(1).rolling(window=3).min()

    conditions = [
        (df["close"] > df["rolling_high_3"]),
        (df["close"] < df["rolling_low_3"])
    ]
    
    df["signal"] = np.select(conditions, ["BUY", "SELL"], default="HOLD")
    df["reason"] = np.select(conditions, [
        "Aggressive BUY: Price cleared 3-day high",
        "Aggressive SELL: Price broke 3-day low"
    ], default="Inside tight 3-day range")

    # Forward 10-day return calculation
    df["fwd_10d_ret"] = (df["close"].shift(-10) / df["close"]) - 1

    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    signals_df = df[["date", "asset", "signal", "close", "fwd_10d_ret", "reason"]].rename(columns={"close": "score"})
    
    upsert_dataframe(conn, "analytics_signals", signals_df.dropna(subset=["signal"]))
    print("✅ Success! Generated aggressive Forex signals.")


if __name__ == "__main__":
    db_conn = init_db()
    print("\n--- RUNNING SIGNAL ENGINE ---")
    
    macro_context = get_macro_context(db_conn)
    generate_gold_signals(db_conn, macro_context)
    generate_bitcoin_signals(db_conn, macro_context)
    generate_forex_signals(db_conn, macro_context)
    
    db_conn.close()
    print("-------------------------------------------\n")