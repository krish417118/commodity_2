## Commodity & Macro Trading Dashboard

This project is a market intelligence dashboard that combines technical price analysis with macroeconomic indicators to monitor Gold, Bitcoin, and EUR/USD. The goal is to organize market data into a single workflow that helps evaluate potential trading opportunities rather than relying solely on price charts.

The pipeline automatically collects daily market data, stores it in a local SQLite database, calculates technical and macro indicators, and presents the results through an interactive Power BI dashboard.

# Tech Stack
Python – Data collection, analysis, and signal generation
SQLite – Local database for storing historical market data
Power BI – Interactive dashboard for visualization and analysis

# Strategy Overview
Each asset follows a different rule-based approach:

Gold: Looks for pullbacks within an established uptrend.
Bitcoin: Monitors momentum breakouts to identify periods of strong price acceleration.
EUR/USD: Uses 10-day channel breakouts to highlight potential trend continuation.

# Macro Confirmation
Technical signals are evaluated alongside broader macroeconomic conditions, including the US Dollar Index (DXY) and US Treasury Yields. These indicators provide additional market context and help filter out lower-conviction setups when technical and macro trends are not aligned.

# Purpose
The dashboard is not designed to predict markets with certainty or provide guaranteed “buy/sell” calls. Instead, it delivers structured signals and contextual insights that help traders make informed decisions. By combining asset‑specific strategies with macroeconomic filters, the system emphasizes discipline, consistency, and risk awareness.
