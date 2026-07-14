# ==========================================
# Commodity, Crypto & Forex Intelligence Dashboard
# Predictive Signal Engine - Institutional Tuning & Backtest Module
# ==========================================

import pandas as pd
import numpy as np

# Note: For standalone testing, database imports can be swapped with local CSV ingestion.
try:
    from database.db import init_db, upsert_dataframe, query
except ImportError:
    print("Database module not found. Engine will run in simulation/backtest mode.")

def get_macro_context(macro_df):
    """
    Pivots the raw macroeconomic dataset to ensure aligned time-series indexing.
    """
    if macro_df.empty:
        return pd.DataFrame()
        
    macro_df["date"] = pd.to_datetime(macro_df["date"])
    macro_df["value"] = pd.to_numeric(macro_df["value"], errors="coerce")
    
    macro_wide = macro_df.pivot(index="date", columns="series", values="value").sort_index().ffill()
    return macro_wide

def generate_gold_signals(df, macro_df):
    """
    Gold Strategy: Macro-Filtered Structural Trend
    Optimized Parameters: 20/30 EMA Crossover, 30-Day DXY & Real Yield Macro Smoothing.
    """
    print("Processing Optimized Macro-Filtered Strategy for Gold...")
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")

    # 1. Structural Trend: Optimized 20-Day vs 30-Day EMA
    df["ema_20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema_30"] = df["close"].ewm(span=30, adjust=False).mean()

    # 2. Volatility Buffer: 14-Day ATR Proxy
    df["tr"] = df["close"].diff().abs()
    df["atr"] = df["tr"].ewm(span=14, adjust=False).mean()

    # 3. Macro Filter A: U.S. Dollar Index (DXY) Trend Validation (30-Day Span)
    if not macro_df.empty and "DXY_Close" in macro_df.columns:
        df = df.merge(macro_df[["DXY_Close"]], left_on="date", right_index=True, how="left").ffill()
        df["dxy_ma30"] = df["DXY_Close"].rolling(30).mean()
        dxy_bullish = (df["DXY_Close"] < df["dxy_ma30"])
        dxy_bearish = (df["DXY_Close"] > df["dxy_ma30"])
    else:
        dxy_bullish = True
        dxy_bearish = True

    # 4. Macro Filter B: Real Yield Dynamic Proxy (30-Day Span)
    if not macro_df.empty and "US10Y_Yield" in macro_df.columns and "CPI" in macro_df.columns:
        df = df.merge(macro_df[["US10Y_Yield", "CPI"]], left_on="date", right_index=True, how="left").ffill()
        df["inflation_yoy"] = df["CPI"].pct_change(252) * 100 
        df["real_yield"] = df["US10Y_Yield"] - df["inflation_yoy"].fillna(0)
        df["ry_ma30"] = df["real_yield"].rolling(30).mean()
        ry_bullish = (df["real_yield"] < df["ry_ma30"])
        ry_bearish = (df["real_yield"] > df["ry_ma30"])
    else:
        ry_bullish = True
        ry_bearish = True

    # 5. Signal Execution Logic: Strict adherence to cross-asset alignments
    conditions = [
        (df["ema_20"] > df["ema_30"]) & (df["close"] >= df["ema_20"] - 0.5 * df["atr"]) & (dxy_bullish | ry_bullish),
        (df["ema_20"] < df["ema_30"]) & (df["close"] <= df["ema_20"] + 0.5 * df["atr"]) & (dxy_bearish | ry_bearish)
    ]
    
    df["signal"] = np.select(conditions, ["BUY", "SELL"], default="HOLD")
    return df

def generate_bitcoin_signals(df):
    """
    Bitcoin Strategy: Adaptive MACD-V + Regime Detection
    Optimized Parameters: 10/20 MACD-V lengths, Signal 7, ER lookback 14, ER Threshold 0.40.
    """
    print("Processing Optimized Adaptive MACD-V Strategy for Bitcoin...")
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")

    # 1. Volatility Proxy (ATR Calculation on slow length)
    df["tr"] = df["close"].diff().abs()
    df["atr_20"] = df["tr"].ewm(span=20, adjust=False).mean()

    # 2. MACD-V (Volatility Adjusted MACD)
    ema_10 = df["close"].ewm(span=10, adjust=False).mean()
    ema_20 = df["close"].ewm(span=20, adjust=False).mean()
    macd_raw = ema_10 - ema_20
    
    # Normalize absolute spread into volatility units
    df["macd_v"] = (macd_raw / df["atr_20"]) * 100
    df["macd_v_signal"] = df["macd_v"].ewm(span=7, adjust=False).mean()

    # 3. Market Regime Detection (Kaufman's Efficiency Ratio - 14 Period)
    net_change = (df["close"] - df["close"].shift(14)).abs()
    sum_changes = df["tr"].rolling(14).sum()
    df["er"] = net_change / sum_changes

    # 4. Signal Logic Execution (Strict 0.40 threshold for high efficiency trending)
    conditions = [
        (df["er"] > 0.40) & (df["macd_v"] > df["macd_v_signal"]) & (df["macd_v"] > -50),
        (df["er"] > 0.40) & (df["macd_v"] < df["macd_v_signal"]) & (df["macd_v"] < 50)
    ]
    
    df["signal"] = np.select(conditions, ["BUY", "SELL"], default="HOLD")
    return df

def generate_forex_signals(df):
    """
    EUR/USD Strategy: ATR Volatility Breakout + Structural Trend Conviction
    Optimized Parameters: 30-Day MA, 1.5x ATR(20), ER > 0.25 (20d), 50-EMA Trend Filter.
    """
    print("Processing Optimized ATR Breakout Strategy for EUR/USD...")
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")

    # 1. Baseline and ATR Volatility Bands
    df["ma_30"] = df["close"].rolling(window=30).mean()
    df["tr"] = df["close"].diff().abs()
    df["atr_20"] = df["tr"].rolling(window=20).mean()

    # Dynamic breakout thresholds
    df["upper_band"] = df["ma_30"] + (1.5 * df["atr_20"])
    df["lower_band"] = df["ma_30"] - (1.5 * df["atr_20"])

    # 2. Market Regime Detection (Kaufman's ER - 20 Period)
    net_change = (df["close"] - df["close"].shift(20)).abs()
    sum_changes = df["tr"].rolling(20).sum()
    df["er"] = net_change / sum_changes

    # 3. Structural Trend Overlay (50-Period EMA to prevent mean-reversion whipsaws)
    df["ema_50"] = df["close"].ewm(span=50, adjust=False).mean()

    # 4. Signal Execution Logic
    conditions = [
        (df["er"] > 0.25) & (df["close"] > df["upper_band"]) & (df["close"] > df["ema_50"]),
        (df["er"] > 0.25) & (df["close"] < df["lower_band"]) & (df["close"] < df["ema_50"])
    ]
    
    df["signal"] = np.select(conditions, ["BUY", "SELL"], default="HOLD")
    return df

def run_vectorized_backtest(df, asset_name, tx_cost):
    """
    Vectorized Backtesting Engine
    Translates raw signals into positions, calculates execution slippage/fees,
    and derives risk-adjusted performance metrics.
    """
    df = df.copy()
    df["asset_return"] = df["close"].pct_change().fillna(0)
    
    # State machine for holding positions
    positions = []
    current_pos = 0
    for idx, row in df.iterrows():
        sig = row["signal"]
        if sig == "BUY":
            current_pos = 1
        elif sig == "SELL":
            current_pos = -1
        # HOLD maintains previous position implicitly
        positions.append(current_pos)
    
    df["position"] = positions
    
    # Shift positions forward by 1 to prevent look-ahead bias (execute at next open)
    df["position_lag"] = df["position"].shift(1).fillna(0)
    df["strat_return_gross"] = df["position_lag"] * df["asset_return"]
    
    # Transaction cost logic
    df["trades"] = df["position"].diff().abs().fillna(0)
    df["strat_return_net"] = df["strat_return_gross"] - (df["trades"] * tx_cost)
    
    # Compounding metrics
    cum_net = (1 + df["strat_return_net"]).cumprod() - 1
    total_ret = cum_net.iloc[-1] * 100
    
    # Risk Profile
    avg_ret = df["strat_return_net"].mean()
    std_ret = df["strat_return_net"].std()
    sharpe = (avg_ret / std_ret) * np.sqrt(252) if std_ret > 0 else 0
    
    cum_series = (1 + df["strat_return_net"]).cumprod()
    max_dd = ((cum_series - cum_series.cummax()) / cum_series.cummax()).min() * 100
    
    print(f"\n--- Backtest Results: {asset_name} ---")
    print(f"Total Net Return: {total_ret:.2f}%")
    print(f"Sharpe Ratio:     {sharpe:.2f}")
    print(f"Max Drawdown:     {max_dd:.2f}%")
    print(f"Total Trades:     {int(df['trades'].sum())}")
    print("---------------------------------------\n")
    return df

if __name__ == "__main__":
    print("\n--- RUNNING OPTIMIZED SIGNAL ENGINE & BACKTEST SUITE ---")
    
    # Simulated 2-Year Market Data Generation for verification
    dates = pd.date_range(start="2024-07-15", end="2026-07-14", freq="B")
    n_days = len(dates)
    np.random.seed(42)

    gold_prices = 2355 * np.exp(np.cumsum(np.random.normal(0.0006, 0.009, n_days)))
    btc_prices = 58000 * np.exp(np.cumsum(np.random.normal(0.001, 0.025, n_days)))
    eur_prices = 1.08 * np.exp(np.cumsum(np.random.normal(0.00002, 0.0035, n_days)))
    dxy_prices = 104 * np.exp(np.cumsum(-0.6 * np.random.normal(0.00002, 0.0035, n_days) + np.random.normal(0, 0.002, n_days)))
    us10y = 4.2 + np.cumsum(np.random.normal(0, 0.04, n_days))
    
    # CPI Approximation
    cpi_values = [313.0]
    for i in range(1, n_days):
        cpi_values.append(cpi_values[-1] * (1 + np.random.normal(0.002, 0.001)) if i % 21 == 0 else cpi_values[-1])
        
    df_gold = pd.DataFrame({"date": dates, "close": gold_prices})
    df_btc = pd.DataFrame({"date": dates, "close": btc_prices})
    df_eur = pd.DataFrame({"date": dates, "close": eur_prices})
    
    df_macro = pd.DataFrame({
        "date": dates.tolist() * 3,
        "series": ["DXY_Close"]*n_days + ["US10Y_Yield"]*n_days + ["CPI"]*n_days,
        "value": dxy_prices.tolist() + us10y.tolist() + cpi_values
    })

    # Execution Flow
    macro_context = get_macro_context(df_macro)
    
    gold_signals = generate_gold_signals(df_gold, macro_context)
    run_vectorized_backtest(gold_signals, "Gold (Macro EMA Filter)", tx_cost=0.0003)
    
    btc_signals = generate_bitcoin_signals(df_btc)
    run_vectorized_backtest(btc_signals, "Bitcoin (MACD-V + ER Regime)", tx_cost=0.0003)
    
    eur_signals = generate_forex_signals(df_eur)
    run_vectorized_backtest(eur_signals, "EUR/USD (ATR Breakout + Trend Overlay)", tx_cost=0.00015)