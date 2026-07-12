# Commodity & Macro Trading Dashboard 

I built this project to track trades for Gold, Bitcoin, and Forex using hard data instead of gut feelings. 

Rather than staring at charts all day, this setup automatically downloads daily prices, runs the math, and outputs clear "BUY" or "SELL" signals into a clean Power BI dashboard. 

##  What I Used
* **Python** (to download the data and run the strategy)
* **SQLite** (to store the data locally on my machine)
* **Power BI** (to visualize the trades and make it look good)

##  How the Strategy Works
The code treats different assets differently:
* **Gold:** Buys the dip when the overall trend is going up.
* **Bitcoin:** Looks for fast, aggressive momentum breakouts.
* **EUR/USD (Forex):** Tracks 10-day highs and lows to catch big channel moves.

**The Safety Net (Macro Filters):** The code doesn't just look at the price. It also checks the broader economy, like the US Dollar Index and Treasury Yields. If a chart says "BUY" but the economy says the opposite, the bot cancels the trade. This prevents losing money on false breakouts.

