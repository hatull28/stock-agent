from data import get_price_history

def inspect(ticker):
    data = get_price_history(ticker)
    close = data["Close"]

    sma50 = close.rolling(window=50).mean()
    sma150 = close.rolling(window=150).mean()

    print(f"\n=== {ticker} ===")
    print(f"  Rows fetched:   {len(data)}")
    print(f"  Latest close:   {close.iloc[-1]:.2f}")
    print(f"  SMA50 now:      {sma50.iloc[-1]:.2f}")
    print(f"  SMA150 now:     {sma150.iloc[-1]:.2f}")
    print(f"  SMA150 ~20d ago:{sma150.iloc[-21]:.2f}")
    print(f"  52-week range:  {close.min():.2f}  to  {close.max():.2f}")
    # show the last 5 closes to eyeball for weird jumps
    print(f"  Last 5 closes:  {[round(c,2) for c in close.iloc[-5:]]}")

if __name__ == "__main__":
    for t in ["MSFT", "META", "AAPL"]:   # two suspects + one healthy for comparison
        inspect(t)