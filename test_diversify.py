from ai_layer import propose_diversifiers
from fundamentals import get_fundamentals
from config import PORTFOLIO

target = ["Healthcare", "Financials", "Energy", "Consumer Discretionary", "Industrials"]
portfolio_sectors = ["Technology"]

print("Asking AI for diversifying candidates...\n")
candidates = propose_diversifiers(portfolio_sectors, target, PORTFOLIO)

print("PROPOSED (before verification):")
for c in candidates:
    print(f"  {c['ticker']:6} {c['company']} ({c['sector']}) - {c['why']}")

# --- Stage 2: verify each against real data ---
print("\nVERIFYING against real data...")
for c in candidates:
    ticker = c["ticker"]
    f = get_fundamentals(ticker)
    # if yfinance has no market cap, the ticker is likely invalid
    if f.get("market_cap"):
        print(f"  VALID:   {ticker} - {f['name']} - actual sector: {f['sector']}")
    else:
        print(f"  INVALID: {ticker} - no data, dropping")