import json
import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_CACHE_FILE = Path(__file__).parent / "masthead_cache.json"

# Curated queries — rotated by day-of-year so the masthead varies daily
_QUERIES = [
    "stock market trading floor",
    "city skyline finance architecture",
    "wall street new york",
    "skyscraper glass office building",
    "financial district urban",
]


def get_masthead_image():
    """Return today's masthead image, fetching from Unsplash on the first run of each day.

    Returns: {"url": "...", "photographer": "...", "profile_url": "..."} or None on failure.
    Caches in masthead_cache.json — same-day re-runs skip the API call entirely.
    On any failure falls back to yesterday's cached image, then to None (no image).
    """
    today = date.today().isoformat()

    cache = _load_cache()

    if today in cache:
        return cache[today]

    api_key = os.getenv("UNSPLASH_ACCESS_KEY")
    if not api_key:
        print("  Unsplash: UNSPLASH_ACCESS_KEY not set, skipping masthead image.")
        return _latest_cached(cache)

    query = _QUERIES[date.today().timetuple().tm_yday % len(_QUERIES)]

    try:
        import requests as _req
        resp = _req.get(
            "https://api.unsplash.com/photos/random",
            params={"query": query, "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {api_key}"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        result = {
            "url":           data["urls"]["regular"],
            "photographer":  data["user"]["name"],
            "profile_url":   data["user"]["links"]["html"]
                             + "?utm_source=the_wire&utm_medium=referral",
        }
        cache[today] = result
        _save_cache(cache)
        safe_name = result['photographer'].encode('ascii', errors='replace').decode()
        print(f"  Unsplash: fetched photo by {safe_name} ({query})")
        return result
    except Exception as e:
        print(f"  Unsplash fetch skipped: {e}")
        return _latest_cached(cache)


def _load_cache():
    if _CACHE_FILE.exists():
        try:
            with open(_CACHE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_cache(cache):
    with open(_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def _latest_cached(cache):
    """Return the most recently cached entry, or None."""
    if not cache:
        return None
    return cache[max(cache.keys())]
