from data import get_price_history
from config import BENCHMARK
from analysis import micha_criteria_6_to_12_code

benchmark = get_price_history(BENCHMARK)

for ticker in ["AAPL", "NVDA", "MSFT", "TSM", "ASML", "META"]:
    data = get_price_history(ticker)
    results = micha_criteria_6_to_12_code(data, benchmark)
    print(f"{ticker:6}  9_expansion: {results['9_volume_expansion']}   "
          f"10_dryup: {results['10_volume_dryup_before']}")