import json
from pathlib import Path

_JSON_PATH = Path(__file__).parent / "portfolio.json"

_DEFAULTS = {
    "portfolio": ["AAPL", "NVDA", "MSFT", "GOOGL", "TSM", "AMZN", "ASML", "META"],
    "watchlist": ["DELL", "INTC", "FSLR", "NKE", "TSLA"],
    "benchmark": "^GSPC",
}

try:
    with open(_JSON_PATH, encoding="utf-8") as _f:
        _cfg = json.load(_f)
    PORTFOLIO  = [t.strip().upper() for t in _cfg.get("portfolio", _DEFAULTS["portfolio"])]
    WATCHLIST  = [t.strip().upper() for t in _cfg.get("watchlist", _DEFAULTS["watchlist"])]
    BENCHMARK  = _cfg.get("benchmark", _DEFAULTS["benchmark"]).strip()
except FileNotFoundError:
    print("WARNING: portfolio.json not found, using defaults.")
    PORTFOLIO, WATCHLIST, BENCHMARK = _DEFAULTS["portfolio"], _DEFAULTS["watchlist"], _DEFAULTS["benchmark"]
except Exception as _e:
    print(f"WARNING: portfolio.json could not be parsed ({_e}), using defaults.")
    PORTFOLIO, WATCHLIST, BENCHMARK = _DEFAULTS["portfolio"], _DEFAULTS["watchlist"], _DEFAULTS["benchmark"]
