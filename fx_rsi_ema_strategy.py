import yfinance as yf
import pandas as pd
import os

# Parameters
SLIPPAGE_PCT = 0.0002  # 0.02%
TRADE_COST_FLAT = 2    # $2 per trade
capital = 1000000
allocation = capital / 4

# Currency pairs mapping
symbols = {
    "USDGBP": "GBPUSD=X",
    "USDEUR": "EURUSD=X",
    "USDJPY": "JPY=X",
    "USDAUD": "AUDUSD=X"
}

# Create folders
os.makedirs("market_data", exist_ok=True)
os.makedirs("trades", exist_ok=True)

results = {}

for name, symbol in symbols.items():
    print(f"Fetching data for {name}...")

    df = yf.Ticker(symbol).history(interval="5m", period="60d")
    df = df.rename(columns={"Close": "Price"}).dropna()
    df = df[["Price"]]

    if name != "USDJPY":
        df["Price"] = 1 / df["Price"]

    # Indicators
    df["EMA50"] = df["Price"].ewm(span=50).mean()
    df["EMA200"] = df["Price"].ewm(span=200).mean()
    df["RSI"] = df["Price"].diff().apply(lambda x: max(x, 0)).rolling(14).mean() / \
                (df["Price"].diff().abs().rolling(14).mean() + 1e-9) * 100
    df.dropna(inplace=True)
    df.to_csv(f"market_data/{name}.csv")

    in_position = False
    entry_price = 0
    units = 0
    cash = allocation
    trades = []

    total_slippage_cost = 0
    total_transaction_cost = 0
    gross_pnl = 0

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
            slippage = buy_price - price
            trade_cost = TRADE_COST_FLAT
            if buy_price > 0:
                units = (cash - trade_cost) / buy_price
                entry_price = price  # true price, for gross pnl
                entry_time = timestamp
                cash = 0
                in_position = True
                total_slippage_cost += slippage * units
                total_transaction_cost += trade_cost

        elif in_position and sell_signal:
            sell_price = price * (1 - SLIPPAGE_PCT)
            slippage = price - sell_price
            cash = (units * sell_price) - TRADE_COST_FLAT
            exit_price = price  # true price, for gross pnl
            trade_cost = TRADE_COST_FLAT
            gross_trade_pnl = (exit_price - entry_price) * units
            net_trade_pnl = gross_trade_pnl - (2 * TRADE_COST_FLAT) - ((entry_price * SLIPPAGE_PCT) + (exit_price * SLIPPAGE_PCT)) * units
            trades.append({
                "Entry Time": entry_time,
                "Exit Time": timestamp,
                "Entry Price": round(entry_price, 5),
                "Exit Price": round(exit_price, 5),
                "Units": round(units, 5),
                "Gross P&L ($)": round(gross_trade_pnl, 2),
                "Net P&L ($)": round(net_trade_pnl, 2)
            })
            gross_pnl += gross_trade_pnl
            total_slippage_cost += slippage * units
            total_transaction_cost += trade_cost
            units = 0
            in_position = False

    final_value = cash + (units * df["Price"].iloc[-1] if in_position else 0)
    net_pnl = final_value - allocation
    results[name] = {
        "Final Value": round(final_value, 2),
        "Gross P&L": round(gross_pnl, 2),
        "Slippage Cost": round(total_slippage_cost, 2),
        "Transaction Cost": round(total_transaction_cost, 2),
        "Net P&L": round(net_pnl, 2)
    }

    trades_df = pd.DataFrame(trades)
    trades_df.to_csv(f"trades/{name}_trades.csv", index=False)

# Final Summary
print("\n Portfolio Summary:")
total = 0
total_slip = 0
total_fee = 0
total_gross = 0
total_net = 0
for pair, r in results.items():
    print(f"\n{pair}")
    print(f"  Final Value       : ${r['Final Value']}")
    print(f"  Gross P&L         : ${r['Gross P&L']}")
    print(f"  Slippage Cost     : ${r['Slippage Cost']}")
    print(f"  Transaction Cost  : ${r['Transaction Cost']}")
    print(f"  Net P&L           : ${r['Net P&L']}")
    total += r["Final Value"]
    total_slip += r["Slippage Cost"]
    total_fee += r["Transaction Cost"]
    total_gross += r["Gross P&L"]
    total_net += r["Net P&L"]

print(f"\n TOTALS")
print(f"  Portfolio Final Value : ${round(total, 2)}")
print(f"  Total Gross P&L       : ${round(total_gross, 2)}")
print(f"  Total Slippage Cost   : ${round(total_slip, 2)}")
print(f"  Total Transaction Cost: ${round(total_fee, 2)}")
print(f"  Total Net P&L         : ${round(total_net, 2)}")

