import yfinance as yf
import pandas as pd
import os

# Parameters
SLIPPAGE_PCT = 0.0002  # 0.02%
TRADE_COST_FLAT = 2    # $2 per side
capital = 100000
allocation = capital / 4

# Currency pairs mapping
symbols = {
    "USDGBP": "GBPUSD=X",
    "USDEUR": "EURUSD=X",
    "USDJPY": "JPY=X",
    "USDAUD": "AUDUSD=X"
}

# Create folders
os.makedirs("fxdata/market_data", exist_ok=True)
os.makedirs("fxdata/trades", exist_ok=True)

results = {}

# Backtest for each pair
for name, symbol in symbols.items():
    print(f"Fetching data for {name}...")

    # Download 5-minute data for last 60 days
    df = yf.Ticker(symbol).history(interval="5m", period="60d")
    df = df.rename(columns={"Close": "Price"}).dropna()
    df = df[["Price"]]

    # Invert price if USD is base (except for JPY)
    if name != "USDJPY":
        df["Price"] = 1 / df["Price"]

    # Indicators
    df["EMA50"] = df["Price"].ewm(span=50).mean()
    df["EMA200"] = df["Price"].ewm(span=200).mean()
    df["RSI"] = df["Price"].diff().apply(lambda x: max(x, 0)).rolling(14).mean() / \
                (df["Price"].diff().abs().rolling(14).mean() + 1e-9) * 100
    df.dropna(inplace=True)

    # Save market data
    df.to_csv(f"fxdata/market_data/{name}.csv")

    # Backtest
    in_position = False
    entry_price = 0
    units = 0
    cash = allocation
    trades = []

    for i in range(1, len(df)):
        row = df.iloc[i]
        timestamp = df.index[i]
        price = row["Price"]
        ema50 = row["EMA50"]
        ema200 = row["EMA200"]
        rsi = row["RSI"]

        buy_signal = (price > ema200) and (ema50 > ema200) and (rsi > 50)
        sell_signal = not buy_signal

        if not in_position and buy_signal:
            buy_price = price * (1 + SLIPPAGE_PCT)
            trade_cost = TRADE_COST_FLAT
            if buy_price > 0:
                units = (cash - trade_cost) / buy_price
                entry_price = buy_price
                entry_time = timestamp
                cash = 0
                in_position = True

        elif in_position and sell_signal:
            sell_price = price * (1 - SLIPPAGE_PCT)
            cash = (units * sell_price) - TRADE_COST_FLAT
            pnl = (sell_price - entry_price) * units - 2 * TRADE_COST_FLAT  # Round-trip cost
            trades.append({
                "Entry Time": entry_time,
                "Exit Time": timestamp,
                "Entry Price": round(entry_price, 5),
                "Exit Price": round(sell_price, 5),
                "Units": round(units, 5),
                "P&L ($)": round(pnl, 2)
            })
            units = 0
            in_position = False

    # Final valuation
    final_value = cash + (units * df["Price"].iloc[-1] if in_position else 0)
    results[name] = round(final_value, 2)

    # Save trade history
    trades_df = pd.DataFrame(trades)
    trades_df.to_csv(f"fxdata/trades/{name}_trades.csv", index=False)

# Summary
print("\n✅ Final Portfolio Value:")
total_value = sum(results.values())
print(f"\nTotal: ${total_value:.2f}")
for pair, val in results.items():
    print(f"{pair}: ${val}")

