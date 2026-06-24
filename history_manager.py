import json
import os

HISTORY_FILE = "score_history.json"
_MAX_ENTRIES = 30


def save_scores(date_str, scores_dict):
    """Append today's Micha scores for all tickers; keep last 30 entries per ticker.

    Args:
        date_str: "2026-06-24"
        scores_dict: {"AAPL": 9, "NVDA": 7, ...}
    """
    data = {}
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}

    for ticker, score in scores_dict.items():
        entries = data.get(ticker, [])
        entries = [e for e in entries if e["date"] != date_str]
        entries.append({"date": date_str, "score": int(score)})
        data[ticker] = entries[-_MAX_ENTRIES:]

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_history(ticker):
    """Return the last 7 score entries for a ticker, oldest first.

    Returns: [{"date": "2026-06-18", "score": 7}, ..., {"date": "2026-06-24", "score": 9}]
    Returns [] if ticker has no history yet.
    """
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    return data.get(ticker, [])[-7:]
