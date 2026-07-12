-- ==========================================
-- Commodity & Macro Intelligence Dashboard
-- SQLite Schema
-- ==========================================

CREATE TABLE IF NOT EXISTS raw_prices (
    date  TEXT NOT NULL,
    asset TEXT NOT NULL,
    close REAL NOT NULL,
    PRIMARY KEY (date, asset)
);

CREATE TABLE IF NOT EXISTS macro_data (
    date   TEXT NOT NULL,
    series TEXT NOT NULL,
    value  REAL,
    PRIMARY KEY (date, series)
);

CREATE TABLE IF NOT EXISTS analytics_returns (
    date               TEXT NOT NULL,
    asset              TEXT NOT NULL,
    daily_return       REAL,
    volatility_15d     REAL,
    drawdown_15d       REAL,
    rolling_return_15d REAL,
    rolling_return_30d REAL,
    PRIMARY KEY (date, asset)
);

CREATE TABLE IF NOT EXISTS risk_summary (
    asof_date            TEXT NOT NULL,
    asset                TEXT NOT NULL,
    total_return_pct     REAL,
    avg_daily_return_pct REAL,
    daily_volatility_pct REAL,
    sharpe_ratio         REAL,
    max_drawdown_pct     REAL,
    PRIMARY KEY (asof_date, asset)
);

CREATE TABLE IF NOT EXISTS correlation_matrix (
    asof_date   TEXT NOT NULL,
    factor_a    TEXT NOT NULL,
    factor_b    TEXT NOT NULL,
    correlation REAL,
    PRIMARY KEY (asof_date, factor_a, factor_b)
);

CREATE TABLE IF NOT EXISTS analytics_signals (
    date        TEXT NOT NULL,
    asset       TEXT NOT NULL,
    signal      TEXT NOT NULL,
    score       REAL,
    fwd_10d_ret REAL,
    reason      TEXT,
    PRIMARY KEY (date, asset)
);

CREATE INDEX IF NOT EXISTS idx_raw_prices_date ON raw_prices(date);
CREATE INDEX IF NOT EXISTS idx_analytics_returns_date ON analytics_returns(date);
CREATE INDEX IF NOT EXISTS idx_signals_date ON analytics_signals(date);