from data import get_price_history
from config import PORTFOLIO, BENCHMARK
from analysis import micha_criteria_1_to_5

benchmark = get_price_history(BENCHMARK)

for ticker in PORTFOLIO:
    data = get_price_history(ticker)
    results = micha_criteria_1_to_5(data)
    print(f"{ticker:6}  golden_cross: {results['5_golden_cross_recent']}")