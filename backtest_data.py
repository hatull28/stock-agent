"""
backtest_data.py
Fetch, verify, and cache ~20 years of daily OHLCV for backtesting.

Data layer only — no signals, no criteria, no return calculations.
"""

import datetime
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

BENCHMARK = "^GSPC"
TRADING_DAYS_PER_YEAR = 252
CACHE_DIR = Path(__file__).parent / "backtest_data"

_session = requests.Session()
_session.headers.update({"User-Agent": "Mozilla/5.0"})


# ── Public API ─────────────────────────────────────────────────────────────────

def fetch_history(ticker, years=20, force_refresh=False):
    """Fetch daily OHLCV for ticker and the S&P 500 benchmark.

    Loads from local CSV cache when available and sufficient; only hits
    yfinance when the cache is missing, too short, or force_refresh=True.
    Prints a verification report for both series.

    Returns: (ticker_df, benchmark_df) — verified, NaN-dropped DataFrames.
    """
    CACHE_DIR.mkdir(exist_ok=True)
    ticker_df = _load_or_fetch(ticker.upper(), years, force_refresh)
    bench_df  = _load_or_fetch(BENCHMARK,      years, force_refresh)
    return ticker_df, bench_df


# ── Internal helpers ───────────────────────────────────────────────────────────

def _cache_path(ticker):
    safe = ticker.replace("^", "_")
    return CACHE_DIR / f"{safe}_daily.csv"


def _load_or_fetch(ticker, years, force_refresh):
    path = _cache_path(ticker)
    expected_days = years * TRADING_DAYS_PER_YEAR
    min_acceptable = int(expected_days * 0.80)   # allow up to 20% shortfall

    if not force_refresh and path.exists():
        df = _read_cache(path)
        if len(df) >= min_acceptable:
            print(f"[{ticker}] Cache hit — {len(df):,} rows from {path.name}")
            _verify(ticker, df, years, from_cache=True)
            return df
        print(
            f"[{ticker}] Cache too short "
            f"({len(df):,} rows, need >= {min_acceptable:,}), re-fetching."
        )

    df_raw   = _yfinance_fetch(ticker, years)
    df_clean = _verify(ticker, df_raw, years, from_cache=False)
    _write_cache(df_clean, path)
    print(f"[{ticker}] Saved {len(df_clean):,} rows -> {path.name}\n")
    return df_clean


def _yfinance_fetch(ticker, years):
    end   = datetime.date.today()
    # +10-day buffer so the window isn't clipped by weekends at the boundary
    start = end - datetime.timedelta(days=int(years * 365.25) + 10)
    print(f"[{ticker}] Fetching from yfinance ({start} -> {end})...")
    stock = yf.Ticker(ticker, session=_session)
    return stock.history(start=str(start), end=str(end))


def _read_cache(path):
    return pd.read_csv(path, index_col=0, parse_dates=True)


def _write_cache(df, path):
    out = df.copy()
    # Strip timezone so the CSV round-trips without encoding issues
    if hasattr(out.index, "tz") and out.index.tz is not None:
        out.index = out.index.tz_localize(None)
    out.to_csv(path)


def _verify(ticker, df, years, from_cache):
    """Print a verification report and return the NaN-dropped DataFrame."""
    expected_days = years * TRADING_DAYS_PER_YEAR
    sep = "-" * 56
    tag = "[cache]" if from_cache else "[fresh]"

    print(f"\n{'=' * 56}")
    print(f"  VERIFICATION: {ticker}  {tag}")
    print(f"{'=' * 56}")

    if df is None or len(df) == 0:
        print("  ERROR: No data returned — check ticker symbol or network.")
        print(f"{'=' * 56}\n")
        return pd.DataFrame()

    # ── NaN audit ─────────────────────────────────────────────────────────────
    raw_rows = len(df)
    nan_rows = int(df.isna().any(axis=1).sum())
    df_clean = df.dropna()
    clean_rows = len(df_clean)

    if nan_rows:
        print(f"  NaN rows found:   {nan_rows}  (dropped -> {clean_rows:,} rows remain)")
    else:
        print(f"  NaN rows:         0  (clean)")
    print(f"  Total rows:       {clean_rows:,}")

    # ── Date range ────────────────────────────────────────────────────────────
    first = df_clean.index[0]
    last  = df_clean.index[-1]
    first_d = first.date() if hasattr(first, "date") else first
    last_d  = last.date()  if hasattr(last,  "date") else last
    actual_years = (last_d - first_d).days / 365.25

    print(f"  First date:       {first_d}")
    print(f"  Last date:        {last_d}")
    print(f"  Actual span:      {actual_years:.1f} years")

    # ── Coverage check ────────────────────────────────────────────────────────
    if clean_rows < int(expected_days * 0.75):
        print(
            f"  WARNING: only {clean_rows:,} of ~{expected_days:,} expected trading days "
            f"-- yfinance may have truncated history for this ticker"
        )
    else:
        pct = 100 * clean_rows / expected_days
        print(f"  Coverage:         {clean_rows:,} / ~{expected_days:,} expected  ({pct:.0f}%)")

    # ── Gap detection ─────────────────────────────────────────────────────────
    dates = df_clean.index
    gaps = []
    for i in range(1, len(dates)):
        delta = (dates[i] - dates[i - 1]).days
        if delta > 5:
            d0 = dates[i - 1].date() if hasattr(dates[i - 1], "date") else dates[i - 1]
            d1 = dates[i].date()     if hasattr(dates[i],     "date") else dates[i]
            gaps.append((d0, d1, delta))

    if gaps:
        print(f"  Gaps > 5 days:    {len(gaps)} found")
        for g0, g1, gd in gaps[:8]:
            print(f"      {g0}  ->  {g1}  ({gd} calendar days)")
        if len(gaps) > 8:
            print(f"      ... and {len(gaps) - 8} more")
    else:
        print(f"  Gaps > 5 days:    none")

    print(f"{'=' * 56}\n")
    return df_clean


# ── Standalone test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import truststore
    sys.stdout.reconfigure(encoding="utf-8")
    truststore.inject_into_ssl()

    print("=" * 56)
    print("  PASS 1: fresh fetch (or existing cache)")
    print("=" * 56 + "\n")
    aapl, gspc = fetch_history("AAPL", years=20)
    print(f"Returned  AAPL: {aapl.shape}   ^GSPC: {gspc.shape}")

    print("\n" + "=" * 56)
    print("  PASS 2: must load entirely from cache")
    print("=" * 56 + "\n")
    aapl2, gspc2 = fetch_history("AAPL", years=20)
    print(f"Returned  AAPL: {aapl2.shape}   ^GSPC: {gspc2.shape}")
