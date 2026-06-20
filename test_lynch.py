from fundamentals import get_fundamentals
from ai_layer import peter_lynch_score

for ticker in ["MSFT", "TSM"]:
    print(f"\n=== {ticker} ===")
    f = get_fundamentals(ticker)
    result = peter_lynch_score(ticker, f)
    if result:
        print(f"PETER SCORE: {result['peter_score']}/10")
        for crit, val in result["scores"].items():
            print(f"  {crit}: {val}")
        print(f"\nSummary: {result['summary']}")