from data import get_price_history
from config import BENCHMARK
from analysis import analyze_stock

benchmark_data = get_price_history(BENCHMARK)
result = analyze_stock("TSM", benchmark_data)

print(f"{result['ticker']} ({result['name']})")
print(f"Sector: {result['sector']}")
print(f"Micha: {result['micha_score']}/12")
print(f"Peter: {result['peter_score']}/10")
print(f"Action: {result['verdict']['action']}")
print(f"Short-term: {result['verdict']['short_term']}")
print(f"Long-term: {result['verdict']['long_term']}")