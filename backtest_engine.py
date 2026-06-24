"""
backtest_engine.py
Walk-forward backtest engine — criterion 5 (golden cross) on AAPL, 20-year history.

Finds every trading day the golden cross criterion fired and records the forward
excess return over ^GSPC at 30, 60, and 90 trading days.

Walk-forward discipline
-----------------------
For each day i, the SIGNAL is computed on data[0:i+1] — strictly no lookahead.
The FORWARD RETURN uses data[i] through data[i+N] — a separate, future window.
These two sides are never mixed.

Output: raw list of records. No aggregation here — that is a later layer.
"""

import time

from analysis import micha_criteria_1_to_5
from backtest_data import fetch_history

# Minimum history rows before the signal is meaningful (SMA150 needs >= 150 rows)
_MIN_ROWS = 150

# Maximum forward window in trading days (signals within 90 days of end are excluded)
_N_FORWARD = 90


def run_golden_cross_backtest(ticker="AAPL", years=20):
    """Walk-forward scan for golden cross signals and forward excess returns.

    Returns a list of dicts:
        [{"date": date, "excess_30": float, "excess_60": float, "excess_90": float}, ...]

    Prints a verification summary and a preview of the first 10 records.
    """
    # ── 1. Load data ───────────────────────────────────────────────────────────
    print(f"Loading data for {ticker} + benchmark...")
    stock_df, bench_df = fetch_history(ticker, years=years)

    # Align on the intersection of dates (guard against any off-by-one mismatches)
    common_idx = stock_df.index.intersection(bench_df.index)
    stock_df = stock_df.loc[common_idx].copy()
    bench_df = bench_df.loc[common_idx].copy()

    n = len(stock_df)
    dates = stock_df.index

    # Pre-extract Close as numpy arrays for O(1) forward-return lookups
    stock_close = stock_df["Close"].values
    bench_close = bench_df["Close"].values

    print(f"Aligned series: {n:,} trading days  ({dates[0].date()} → {dates[-1].date()})\n")

    # ── 2. Walk-forward loop ───────────────────────────────────────────────────
    all_signals  = 0   # total days criterion returned True
    excluded_end = 0   # signals dropped because i + 90 >= n
    records      = []

    t_start = time.time()
    scan_start = _MIN_ROWS - 1   # first i where SMA150 is defined (0-indexed)

    for i in range(scan_start, n):

        # Progress pulse — confirms the loop is alive
        if (i - scan_start) % 500 == 0 and i > scan_start:
            elapsed = time.time() - t_start
            pct = 100 * (i - scan_start) / (n - scan_start)
            print(f"  ... {i - scan_start:,} / {n - scan_start:,} days scanned "
                  f"({pct:.0f}%)  [{elapsed:.0f}s]")

        # ── SIGNAL SIDE ───────────────────────────────────────────────────────
        # Only data[0 : i+1] is visible here — day i+1 and beyond are never seen.
        slice_df = stock_df.iloc[0 : i + 1]
        criteria = micha_criteria_1_to_5(slice_df)

        if not criteria["5_golden_cross_recent"]:
            continue

        all_signals += 1

        # ── EDGE CASE: incomplete forward window ──────────────────────────────
        # A signal at day i needs data through day i+90. If that exceeds the
        # series, we cannot compute a complete outcome — exclude it.
        if i + _N_FORWARD >= n:
            excluded_end += 1
            continue

        # ── FORWARD SIDE ──────────────────────────────────────────────────────
        # stock_close and bench_close are separate arrays; no slice of signal data
        # is involved here.
        s0 = stock_close[i]
        b0 = bench_close[i]

        stock_ret_30 = stock_close[i + 30] / s0 - 1
        stock_ret_60 = stock_close[i + 60] / s0 - 1
        stock_ret_90 = stock_close[i + 90] / s0 - 1

        bench_ret_30 = bench_close[i + 30] / b0 - 1
        bench_ret_60 = bench_close[i + 60] / b0 - 1
        bench_ret_90 = bench_close[i + 90] / b0 - 1

        records.append({
            "date":       dates[i].date(),
            "excess_30":  stock_ret_30 - bench_ret_30,
            "excess_60":  stock_ret_60 - bench_ret_60,
            "excess_90":  stock_ret_90 - bench_ret_90,
        })

    elapsed_total = time.time() - t_start

    # ── 3. Summary ────────────────────────────────────────────────────────────
    days_scanned = n - scan_start
    print(f"\n{'=' * 54}")
    print(f"  WALK-FORWARD RESULTS: {ticker}  (criterion 5 — golden cross)")
    print(f"{'=' * 54}")
    print(f"  Total days scanned:          {days_scanned:>6,}")
    print(f"  Signal days (criterion True):{all_signals:>6,}")
    print(f"  Excluded (end of history):   {excluded_end:>6,}  [i+90 >= {n}]")
    print(f"  Valid records:               {len(records):>6,}")
    print(f"  Runtime:                     {elapsed_total:.1f}s")
    print(f"{'=' * 54}")

    # Sanity check
    assert all_signals == excluded_end + len(records), \
        "Count mismatch: signals != excluded + valid"

    # ── 4. Preview table ──────────────────────────────────────────────────────
    if records:
        print(f"\n  First {min(10, len(records))} records:\n")
        print(f"  {'Date':<12}  {'Excess 30d':>11}  {'Excess 60d':>11}  {'Excess 90d':>11}")
        print(f"  {'-'*12}  {'-'*11}  {'-'*11}  {'-'*11}")
        for r in records[:10]:
            print(f"  {str(r['date']):<12}  "
                  f"{r['excess_30']*100:>+10.2f}%  "
                  f"{r['excess_60']*100:>+10.2f}%  "
                  f"{r['excess_90']*100:>+10.2f}%")
    print()

    return records


# ── Standalone entry point ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import truststore
    sys.stdout.reconfigure(encoding="utf-8")
    truststore.inject_into_ssl()

    records = run_golden_cross_backtest("AAPL", years=20)
    print(f"{len(records)} records ready for aggregation layer.")
