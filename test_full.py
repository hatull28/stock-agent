from data import get_price_history
from fundamentals import get_fundamentals
from config import BENCHMARK
from analysis import full_micha_analysis
from ai_layer import peter_lynch_score, combined_verdict

ticker = "MSFT"   # the interesting case: weak technicals, strong fundamentals

print(f"Running FULL analysis for {ticker}...\n")

benchmark_data = get_price_history(BENCHMARK)
data = get_price_history(ticker)

# Part 1
micha = full_micha_analysis(ticker, data, benchmark_data)
print(f"MICHA (technical): {micha['score']}/12")

# Part 2
fundamentals = get_fundamentals(ticker)
peter = peter_lynch_score(ticker, fundamentals)
print(f"PETER (fundamental): {peter['peter_score']}/10")

# Part 3
print("\n--- COMBINED VERDICT ---")
verdict = combined_verdict(ticker, micha, peter)
if verdict:
    print(f"Technical meaning: {verdict['micha_meaning']}")
    print(f"Fundamental meaning: {verdict['peter_meaning']}")
    print(f"Short-term (1-6mo): {verdict['short_term']}")
    print(f"Long-term (2-5yr):  {verdict['long_term']}")
    print(f"ACTION: {verdict['action']}")
    print(f"Strategy: {verdict['accumulation_strategy']}")