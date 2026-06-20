import yfinance as yf

def get_fundamentals(ticker):
    """Fetch key fundamental data points for a stock."""
    stock = yf.Ticker(ticker)
    info = stock.info

    # pull the fields we care about (with safe defaults if missing)
    data = {
        "name": info.get("longName", ticker),
        "sector": info.get("sector", "Unknown"),
        "industry": info.get("industry", "Unknown"),
        "market_cap": info.get("marketCap"),
        "pe_ratio": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "peg_ratio": info.get("trailingPegRatio"),
        "revenue_growth": info.get("revenueGrowth"),
        "earnings_growth": info.get("earningsGrowth"),
        "profit_margin": info.get("profitMargins"),
        "debt_to_equity": info.get("debtToEquity"),
        "free_cash_flow": info.get("freeCashflow"),
        "return_on_equity": info.get("returnOnEquity"),
    }
    return data


# --- test it ---
if __name__ == "__main__":
    for ticker in ["AAPL", "MSFT", "TSM", "ASML"]:
        print(f"\n=== {ticker} ===")
        f = get_fundamentals(ticker)
        for key, value in f.items():
            print(f"  {key}: {value}")