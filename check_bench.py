from data import get_price_history

stock = get_price_history("AAPL")
bench = get_price_history("^GSPC")

print("AAPL rows: ", len(stock))
print("GSPC rows: ", len(bench))

# 6-month (126-day) returns
stock_ret = (stock["Close"].iloc[-1] / stock["Close"].iloc[-126]) - 1
bench_ret = (bench["Close"].iloc[-1] / bench["Close"].iloc[-126]) - 1

print(f"AAPL 6mo return:  {stock_ret*100:.1f}%")
print(f"GSPC 6mo return:  {bench_ret*100:.1f}%")
print(f"AAPL outperforming? {stock_ret > bench_ret}")

print(f"\nGSPC latest close: {bench['Close'].iloc[-1]:.2f}")
print(f"GSPC 126d ago:     {bench['Close'].iloc[-126]:.2f}")