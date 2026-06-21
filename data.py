import yfinance as yf
import requests

_session = requests.Session()
_session.headers.update({"User-Agent": "Mozilla/5.0"})

def get_price_history(ticker, period="1y"):
    """Fetch ~1 year of daily price data for one stock."""
    stock = yf.Ticker(ticker, session=_session)
    history = stock.history(period=period)
    history = history.dropna(subset=["Close"])   # drop rows with missing close
    return history

# --- test it ---
if __name__ == "__main__":
    import truststore; truststore.inject_into_ssl()
    data = get_price_history("AAPL")
    print(data.tail())
    print("\nColumns:", list(data.columns))
    print("Rows fetched:", len(data))
