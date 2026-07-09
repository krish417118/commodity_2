-- ==========================================
-- Commodity & Macro Intelligence Dashboard
-- SQLite Schema (Day 2)
-- ==========================================
--
-- Design notes:
-- * Long/tidy format (date, entity, value...) rather than one column
--   per asset. This is what makes Power BI slicers ("pick an asset")
--   trivial instead of needing a separate visual per asset.
-- * Composite primary keys double as the uniqueness constraint that
--   makes "INSERT OR REPLACE" a safe, idempotent upsert -- re-running
--   the pipeline on a day you already have never creates a duplicate row.
-- * "asof_date" (risk_summary, correlation_matrix) means "the day this
--   snapshot was computed", not a trading day -- these are point-in-time
--   summaries (e.g. Sharpe over the latest 60 days), not daily series.
--   Storing one row per run date lets you trend "how has my 60-day
--   Sharpe changed over the last month" in Power BI, which a single
--   overwritten snapshot could never show.

CREATE TABLE IF NOT EXISTS raw_prices (
    date  TEXT NOT NULL,       -- ISO format YYYY-MM-DD
    asset TEXT NOT NULL,       -- 'Gold' | 'Oil' | 'Bitcoin' | 'EURUSD'
    close REAL NOT NULL,
    PRIMARY KEY (date, asset)
);

CREATE TABLE IF NOT EXISTS macro_data (
    date   TEXT NOT NULL,
    series TEXT NOT NULL,      -- 'US10Y_Yield' | 'CPI' | 'DXY_Close'
    value  REAL,
    PRIMARY KEY (date, series)
);

CREATE TABLE IF NOT EXISTS analytics_returns (
    date               TEXT NOT NULL,
    asset              TEXT NOT NULL,
    daily_return       REAL,
    volatility_30d     REAL,
    drawdown_60d       REAL,
    rolling_return_30d REAL,
    rolling_return_90d REAL,
    PRIMARY KEY (date, asset)
);

CREATE TABLE IF NOT EXISTS risk_summary (
    asof_date            TEXT NOT NULL,   -- date this 60-day snapshot was computed
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

-- Day 5 will populate this; created now so the schema is stable and
-- Power BI can be pointed at it from Day 6 onward without a rebuild.
CREATE TABLE IF NOT EXISTS analytics_signals (
    date   TEXT NOT NULL,
    asset  TEXT NOT NULL,
    signal TEXT NOT NULL,      -- 'BUY' | 'HOLD' | 'SELL'
    score  REAL,
    reason TEXT,               -- plain-language justification, shown in the dashboard
    PRIMARY KEY (date, asset)
);

CREATE INDEX IF NOT EXISTS idx_raw_prices_date ON raw_prices(date);
CREATE INDEX IF NOT EXISTS idx_analytics_returns_date ON analytics_returns(date);
CREATE INDEX IF NOT EXISTS idx_signals_date ON analytics_signals(date);