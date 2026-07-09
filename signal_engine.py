# ==========================================
# Commodity & Macro Intelligence Dashboard
# Predictive Signal Engine (Day 5) - INSTITUTIONAL TUNING
# Pure Pandas Implementation (Python 3.14 Compatible)
# ==========================================

import pandas as pd
import numpy as np

from database.db import init_db, upsert_dataframe, query

def get_macro_context(conn):
    """Fetches and prepares macroeconomic data to act as trade filters."""
    sql = "SELECT date, series, value FROM macro_data"
    macro_df = query(conn, sql)
    
    if macro_df.empty:
        return pd.DataFrame()
        
    macro_df["date"] = pd.to_datetime(macro_df["date"])
    macro_df["value"] = pd.to_numeric(macro_df["value"], errors="coerce")
    
    macro_wide = macro_df.pivot(index="date", columns="series", values="value").sort_index().ffill()
    
    if "US10Y_Yield" in macro_wide.columns:
        macro_wide["yield_sma_10"] = macro_wide["US10Y_Yield"].rolling(10).mean()
    if "DXY_Close" in macro_wide.columns:
        macro_wide["dxy_sma_10"] = macro_wide["DXY_Close"].rolling(10).mean()
        
    return macro_wide


def generate_gold_signals(conn, macro_df):
    print("Processing Institutional Regime-Filtered Strategy for Gold...")
    sql = "SELECT date, asset, close FROM raw_prices WHERE asset = 'Gold' ORDER BY date"
    df = query(conn, sql)
    if df.empty: return

    df["date"] = pd.to_datetime(df["date"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.set_index("date").join(macro_df, how="left").ffill().reset_index()

    # Technicals & Volatility Bands
    df["ema_20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["sma_20"] = df["close"].rolling(window=20).mean()
    df["std_20"] = df["close"].rolling(window=20).std()
    df["upper_band"] = df["sma_20"] + (1.5 * df["std_20"])
    
    # 1. The Chop Detector: Short-term vol vs Long-term vol
    df["std_5"] = df["close"].rolling(window=5).std()
    df["vol_ratio"] = df["std_5"] / df["std_20"]

    # 2. Exact Crossovers (Prevents spamming signals in a trend)
    df["prev_close"] = df["close"].shift(1)
    df["prev_ema"] = df["ema_20"].shift(1)
    
    df["bull_cross"] = (df["prev_close"] <= df["prev_ema"]) & (df["close"] > df["ema_20"])
    df["bear_cross"] = (df["prev_close"] >= df["prev_ema"]) & (df["close"] < df["ema_20"])
    
    req_cols = ["ema_20", "upper_band", "vol_ratio", "US10Y_Yield", "yield_sma_10"]
    if not all(c in df.columns for c in req_cols): return
    df = df.dropna(subset=req_cols).copy()

    conditions = [
        (df["close"] > df["upper_band"]),
        df["bear_cross"] & (df["US10Y_Yield"] > df["yield_sma_10"]) & (df["vol_ratio"] > 0.8),
        df["bull_cross"] & (df["US10Y_Yield"] < df["yield_sma_10"]) & (df["vol_ratio"] > 0.8),
    ]
    signals = ["SELL", "SELL", "BUY"] 
    reasons = [
        "Take Profit: Price overextended past 1.5 Std Dev band",
        "Trend Reversal (SELL): EMA Breakdown + Rising Yields",
        "Breakout (BUY): EMA Reclaimed + Falling Yields"
    ]
    
    df["signal"] = np.select(conditions, signals, default="HOLD")
    df["reason"] = np.select(conditions, reasons, default="Riding current trend or market is chopping")

    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    signals_df = df[["date", "asset", "signal", "close", "reason"]].rename(columns={"close": "score"})
    upsert_dataframe(conn, "analytics_signals", signals_df)
    print("✅ Success! Generated robust Gold signals.")


def generate_bitcoin_signals(conn, macro_df):
    print("Processing Advanced Volatility-Filtered Strategy for Bitcoin...")
    sql = "SELECT date, asset, close FROM raw_prices WHERE asset = 'BTC-USD' ORDER BY date"
    df = query(conn, sql)
    if df.empty: return

    df["date"] = pd.to_datetime(df["date"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.set_index("date").join(macro_df, how="left").ffill().reset_index()

    # 1. Baseline Trend Filter (The 50-day EMA)
    df["ema_50"] = df["close"].ewm(span=50, adjust=False).mean()

    # 2. Volatility Squeeze Expansion (Bollinger Band Width)
    df["sma_20"] = df["close"].rolling(window=20).mean()
    df["std_20"] = df["close"].rolling(window=20).std()
    df["bb_width"] = (df["std_20"] * 4) / df["sma_20"]
    df["bb_width_sma_20"] = df["bb_width"].rolling(window=20).mean()

    # 3. Native RSI
    change = df["close"].diff()
    gain = change.mask(change < 0, 0.0)
    loss = -change.mask(change > 0, 0.0)
    df["rsi"] = 100 - (100 / (1 + (gain.ewm(com=13, min_periods=14).mean() / loss.ewm(com=13, min_periods=14).mean())))

    # 4. Fast MACD & Crossovers
    df["macd_line"] = df["close"].ewm(span=8, adjust=False).mean() - df["close"].ewm(span=21, adjust=False).mean()
    df["macd_hist"] = df["macd_line"] - df["macd_line"].ewm(span=5, adjust=False).mean()
    df["prev_macd_hist"] = df["macd_hist"].shift(1)
    
    df["macd_cross_up"] = (df["prev_macd_hist"] <= 0) & (df["macd_hist"] > 0)
    df["macd_cross_down"] = (df["prev_macd_hist"] >= 0) & (df["macd_hist"] < 0)

    req_cols = ["ema_50", "bb_width", "bb_width_sma_20", "rsi", "macd_hist", "DXY_Close", "dxy_sma_10"]
    if not all(c in df.columns for c in req_cols): return
    df = df.dropna(subset=req_cols).copy()

    conditions = [
        # BUY: MACD Cross + Trend Alignment (> 50 EMA) + Volatility Expanding + Macro Tailwinds
        df["macd_cross_up"] & (df["close"] > df["ema_50"]) & (df["bb_width"] > df["bb_width_sma_20"]) & (df["DXY_Close"] < df["dxy_sma_10"]),
        
        # SELL: MACD Fade OR Price structurally falls below the 50-day EMA
        df["macd_cross_down"] | (df["close"] < df["ema_50"])
    ]
    signals = ["BUY", "SELL"]
    reasons = [
        "Volatile Breakout (BUY): Trend Alignment + Volatility Expansion + Macro",
        "Exit/SELL: Momentum fade or structural 50-EMA trend broken"
    ]
    
    df["signal"] = np.select(conditions, signals, default="HOLD")
    df["reason"] = np.select(conditions, reasons, default="Consolidating or Trend Active")

    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    signals_df = df[["date", "asset", "signal", "close", "reason"]].rename(columns={"close": "score"})
    upsert_dataframe(conn, "analytics_signals", signals_df)
    print("✅ Success! Generated volatility-filtered Bitcoin signals.")


def generate_forex_signals(conn, macro_df):
    print("Processing Institutional Breakout for EUR/USD...")
    sql = "SELECT date, asset, close FROM raw_prices WHERE asset = 'EURUSD=X' OR asset = 'EUR/USD' ORDER BY date"
    df = query(conn, sql)
    if df.empty: return

    df["date"] = pd.to_datetime(df["date"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.set_index("date").join(macro_df, how="left").ffill().reset_index()

    df["rolling_high"] = df["close"].shift(1).rolling(window=10).max()
    df["rolling_low"] = df["close"].shift(1).rolling(window=10).min()
    
    df["prev_close"] = df["close"].shift(1)
    df["bull_break"] = (df["prev_close"] <= df["rolling_high"]) & (df["close"] > df["rolling_high"])
    df["bear_break"] = (df["prev_close"] >= df["rolling_low"]) & (df["close"] < df["rolling_low"])

    req_cols = ["rolling_high", "rolling_low", "DXY_Close", "dxy_sma_10"]
    if not all(c in df.columns for c in req_cols): return
    df = df.dropna(subset=req_cols).copy()

    conditions = [
        df["bull_break"] & (df["DXY_Close"] < df["dxy_sma_10"]),
        df["bear_break"] & (df["DXY_Close"] > df["dxy_sma_10"])
    ]
    signals = ["BUY", "SELL"]
    reasons = [
        "Channel Breakout (BUY): 10-day High Cleared + Weak USD",
        "Channel Breakdown (SELL): 10-day Low Lost + Strong USD"
    ]
    
    df["signal"] = np.select(conditions, signals, default="HOLD")
    df["reason"] = np.select(conditions, reasons, default="Trading within range")

    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    signals_df = df[["date", "asset", "signal", "close", "reason"]].rename(columns={"close": "score"})
    upsert_dataframe(conn, "analytics_signals", signals_df)
    print("✅ Success! Generated robust Forex signals.")


if __name__ == "__main__":
    db_conn = init_db()
    print("\n--- RUNNING INSTITUTIONAL SIGNAL ENGINE ---")
    
    macro_context = get_macro_context(db_conn)
    generate_gold_signals(db_conn, macro_context)
    generate_bitcoin_signals(db_conn, macro_context)
    generate_forex_signals(db_conn, macro_context)
    
    db_conn.close()
    print("-------------------------------------------\n")