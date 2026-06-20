import yfinance as yf

def get_price_history(ticker, period="1y"):
    """Fetch ~1 year of daily price data for one stock."""
    stock = yf.Ticker(ticker)
    history = stock.history(period=period)
    history = history.dropna(subset=["Close"])   # drop rows with missing close
    return history

# --- test it ---
if __name__ == "__main__":
    data = get_price_history("AAPL")
    print(data.tail())          # show the last 5 days
    print("\nColumns:", list(data.columns))
    print("Rows fetched:", len(data))