"""
verify_c10.py — Diagnostic for criterion 10 (volume_dryup_before).

Slides through the last ~252 trading days for every stock in PORTFOLIO + WATCHLIST,
re-evaluating the criterion at each point using only data available up to that day.
Reports fire rate, raw prior_vol/background_vol ratios, and data-quality warnings.

Run: python verify_c10.py
"""

import sys
import yfinance as yf
from config import PORTFOLIO, WATCHLIST

TICKERS = PORTFOLIO + WATCHLIST
LOOKBACK_DAYS = 252  # how many past "as-of" dates to evaluate (1 trading year)
MIN_ROWS = 70        # minimum rows needed to compute both windows (matches production)

RATIO_THRESHOLD = 0.9  # criterion fires True when ratio < this


def fetch_2y(ticker):
    stock = yf.Ticker(ticker)
    history = stock.history(period="2y")
    history = history.dropna(subset=["Close"])
    return history


def compute_c10_at(volume_slice):
    """
    Given a slice of volume data ending at a particular 'as-of' date,
    compute background_vol, prior_vol, ratio, and the True/False result.
    Returns (result, ratio, has_data_issue) or None if insufficient rows.
    """
    if len(volume_slice) < MIN_ROWS:
        return None

    background_vol = volume_slice.iloc[-70:-20].mean()
    prior_vol = volume_slice.iloc[-20:-5].mean()

    has_data_issue = (
        background_vol == 0
        or prior_vol != prior_vol  # NaN check
        or background_vol != background_vol
        or volume_slice.iloc[-70:-20].isna().any()
        or volume_slice.iloc[-20:-5].isna().any()
    )

    if background_vol == 0 or background_vol != background_vol:
        return (False, float("nan"), True)

    ratio = prior_vol / background_vol
    result = ratio < RATIO_THRESHOLD
    return (result, ratio, has_data_issue)


print("=" * 70)
print("Criterion 10 (volume_dryup_before) — historical diagnostic")
print(f"Evaluating last {LOOKBACK_DAYS} trading days per ticker")
print(f"Threshold: prior_vol / background_vol < {RATIO_THRESHOLD}")
print()
print("Ratio key:")
print("  < 0.90  → fires True (genuine dry-up)")
print("  0.90–0.95 → just above threshold")
print("  0.95–1.05 → volume roughly flat vs baseline")
print("  > 1.05  → volume elevated vs baseline (opposite of dry-up)")
print("=" * 70)

for ticker in TICKERS:
    print(f"\n{'─'*50}")
    print(f"  {ticker}")
    print(f"{'─'*50}")

    try:
        data = fetch_2y(ticker)
    except Exception as e:
        print(f"  ERROR fetching data: {e}")
        continue

    volume = data["Volume"]
    total_rows = len(volume)
    print(f"  Rows fetched (2y): {total_rows}")

    if total_rows < MIN_ROWS + 1:
        print(f"  SKIP: not enough rows (need {MIN_ROWS + 1}+)")
        continue

    # Determine how many as-of dates we can evaluate
    # We need at least MIN_ROWS rows ending at each point.
    # Start evaluating from index MIN_ROWS-1 (0-based).
    first_eval_idx = MIN_ROWS - 1
    last_eval_idx = total_rows - 1

    # Only look at the most recent LOOKBACK_DAYS as-of dates
    start_idx = max(first_eval_idx, last_eval_idx - LOOKBACK_DAYS + 1)

    results_list = []   # (date, result, ratio, has_data_issue)
    skipped = 0

    for i in range(start_idx, total_rows):
        vol_slice = volume.iloc[: i + 1]
        out = compute_c10_at(vol_slice)
        if out is None:
            skipped += 1
            continue
        result, ratio, has_issue = out
        date = data.index[i]
        results_list.append((date, result, ratio, has_issue))

    if not results_list:
        print(f"  No evaluable points (skipped {skipped})")
        continue

    total_eval = len(results_list)
    true_days = [(d, ratio) for d, result, ratio, _ in results_list if result]
    false_days = [(d, ratio) for d, result, ratio, _ in results_list if not result]
    data_issue_days = sum(1 for _, _, _, issue in results_list if issue)

    ratios = [r for _, _, r, _ in results_list if r == r]  # exclude NaN
    min_ratio = min(ratios) if ratios else float("nan")
    max_ratio = max(ratios) if ratios else float("nan")

    print(f"  Evaluated: {total_eval} days  |  skipped (insufficient rows): {skipped}")
    print(f"  Fired True: {len(true_days)} / {total_eval}  ({100*len(true_days)/total_eval:.1f}%)")
    print(f"  Min ratio seen: {min_ratio:.4f}  |  Max ratio: {max_ratio:.4f}")

    if data_issue_days:
        print(f"  *** DATA QUALITY WARNINGS: {data_issue_days} days had NaN/zero volumes ***")

    if true_days:
        print(f"  First True: {true_days[0][0].date()}  (ratio={true_days[0][1]:.4f})")
        print(f"  Last  True: {true_days[-1][0].date()}  (ratio={true_days[-1][1]:.4f})")
        if len(true_days) > 2:
            sample = true_days[-5:]
            print(f"  Recent True dates: {[str(d.date()) for d, _ in sample]}")
    else:
        print(f"  NEVER fired True in the evaluated window.")
        gap = min_ratio - RATIO_THRESHOLD
        print(f"  Closest approach: ratio={min_ratio:.4f}  (needs to drop {gap:.4f} more to trigger)")

    # Show last 10 ratio values (most recent as-of dates) so we can see direction
    recent_10 = results_list[-10:]
    print(f"  Last 10 ratios (oldest→newest):")
    for date, result, ratio, _ in recent_10:
        flag = " ← TRUE" if result else ""
        print(f"    {date.date()}  ratio={ratio:.4f}{flag}")

print("\n" + "=" * 70)
print("Done.")
