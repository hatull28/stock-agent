"""
backtest_all_criteria.py
Walk-forward backtest of all 10 DETERMINISTIC Micha criteria on AAPL, 20 years.

Criteria 7 & 8 (AI-judged) are excluded — they cannot be backtested without
lookahead bias. This file covers: 1, 2, 3, 4, 5, 6, 9, 10, 11, 12.

Walk-forward discipline (same as backtest_engine.py):
  Signal  : computed on stock_df.iloc[0:i+1]  — strictly no lookahead
  Forward : separate numpy arrays, indices i+30, i+60, i+90

Output: terminal report only. Descriptive — no recommendations.
"""

import statistics
import time
from datetime import date

from analysis import micha_criteria_1_to_5, micha_criteria_6_to_12_code
from backtest_data import fetch_history

# ── Walk-forward parameters ────────────────────────────────────────────────────

_MIN_ROWS  = 150   # SMA150 needs this; covers all other criteria too
_N_FORWARD = 90    # exclude signals within 90 trading days of end

# ── Criterion metadata ─────────────────────────────────────────────────────────

# (key in criteria dict, short label, dedup gap in calendar days, rationale)
_CRITERIA = [
    ("1_price_above_sma150",    "C1  price > SMA150",       6,
     "sustained trend — gap >6 tolerates holiday weekends without splitting a streak"),
    ("2_sma150_slope_positive", "C2  SMA150 slope up",       6,
     "sustained trend — same as C1"),
    ("3_price_above_sma50",     "C3  price > SMA50",         6,
     "sustained trend, cycles faster — same gap rule"),
    ("4_sma50_above_sma150",    "C4  SMA50 > SMA150",        6,
     "sustained trend, months-long — same gap rule"),
    ("5_golden_cross_recent",   "C5  golden cross",         15,
     "25-day window; gap >15 separates distinct cross events (cluster avg ~25 trading days)"),
    ("6_atr_shock_recent",      "C6  ATR shock (up)",       10,
     "10-day look-back window — gap >10 separates distinct shock events"),
    ("9_volume_expansion",      "C9  volume expansion",      8,
     "5-day window — gap >8 separates distinct expansion bursts"),
    ("10_volume_dryup_before",  "C10 volume dry-up",        21,
     "15-day window moves slowly — gap >21 (~15 trading days) separates events"),
    ("11_higher_highs_lows",    "C11 higher highs & lows",   6,
     "3-mo vs 3-mo comparison — sustained, same gap rule as C1"),
    ("12_rs_vs_sp500",          "C12 RS vs S&P500",          6,
     "6-mo comparison — sustained outperformance, same gap rule"),
]

_KEY_TO_META = {key: (label, gap, rationale) for key, label, gap, rationale in _CRITERIA}

# ── Era definitions ────────────────────────────────────────────────────────────

_ERAS = [
    ("Pre-Crisis (2006–Aug 2008)",      date(2008, 9, 1)),
    ("Financial Crisis (Sep 2008–2009)", date(2010, 1, 1)),
    ("Bull Run (2010–2019)",             date(2020, 1, 1)),
    ("COVID/Volatility (2020–2022)",     date(2023, 1, 1)),
    ("Recent (2023–present)",            None),
]

_SMALL_N = 5


# ── Walk-forward engine ────────────────────────────────────────────────────────

def run_all_criteria(ticker="AAPL", years=20):
    """Walk-forward scan for all 10 deterministic criteria.

    Returns: dict {criterion_key: [{"date": date, "excess_30": float, ...}, ...]}
    """
    print(f"Loading data for {ticker} + benchmark...")
    stock_df, bench_df = fetch_history(ticker, years=years)

    common_idx = stock_df.index.intersection(bench_df.index)
    stock_df = stock_df.loc[common_idx].copy()
    bench_df = bench_df.loc[common_idx].copy()

    n = len(stock_df)
    dates = stock_df.index
    stock_close = stock_df["Close"].values
    bench_close = bench_df["Close"].values

    print(f"Aligned: {n:,} trading days  ({dates[0].date()} → {dates[-1].date()})\n")

    raw_records = {key: [] for key, *_ in _CRITERIA}
    all_signal_counts = {key: 0 for key, *_ in _CRITERIA}
    excluded_end = {key: 0 for key, *_ in _CRITERIA}

    t0 = time.time()
    scan_start = _MIN_ROWS - 1

    for i in range(scan_start, n):
        if (i - scan_start) % 1000 == 0 and i > scan_start:
            pct = 100 * (i - scan_start) / (n - scan_start)
            print(f"  ... {i - scan_start:,} / {n - scan_start:,}  ({pct:.0f}%)  "
                  f"[{time.time() - t0:.0f}s]")

        slice_s = stock_df.iloc[0:i + 1]
        slice_b = bench_df.iloc[0:i + 1]

        c1to5 = micha_criteria_1_to_5(slice_s)
        c6to12 = micha_criteria_6_to_12_code(slice_s, slice_b)
        all_c = {**c1to5, **c6to12}

        # Pre-compute forward returns once (shared across all criteria)
        near_end = (i + _N_FORWARD >= n)
        if not near_end:
            s0 = stock_close[i]
            b0 = bench_close[i]
            fwd = {
                "excess_30": stock_close[i + 30] / s0 - 1 - (bench_close[i + 30] / b0 - 1),
                "excess_60": stock_close[i + 60] / s0 - 1 - (bench_close[i + 60] / b0 - 1),
                "excess_90": stock_close[i + 90] / s0 - 1 - (bench_close[i + 90] / b0 - 1),
            }

        for key, *_ in _CRITERIA:
            if not all_c.get(key, False):
                continue
            all_signal_counts[key] += 1
            if near_end:
                excluded_end[key] += 1
                continue
            raw_records[key].append({"date": dates[i].date(), **fwd})

    elapsed = time.time() - t0
    print(f"\nScan complete — {n - scan_start:,} days in {elapsed:.1f}s\n")

    return raw_records, all_signal_counts, excluded_end, n


# ── Deduplication ──────────────────────────────────────────────────────────────

def dedup(records, gap_days):
    """Keep the first record of each True-streak event.

    A new event is declared when the gap between consecutive signal-days exceeds
    gap_days calendar days (meaning the criterion was False for that interval).

    Critical: compare each record against the LAST-SEEN record (whether kept or
    not), not the last-KEPT record. Using last-kept causes false splits within
    long continuous True streaks because after gap_days calendar days inside the
    same streak, the gap from the cluster-start exceeds the threshold.
    """
    if not records:
        return []
    out = [records[0]]
    last_seen = records[0]["date"]
    for rec in records[1:]:
        if (rec["date"] - last_seen).days > gap_days:
            out.append(rec)       # new event: gap in True signal detected
        last_seen = rec["date"]  # always advance, kept or not
    return out


# ── Statistics ─────────────────────────────────────────────────────────────────

def _stats(values):
    if not values:
        return None, None, None, 0, 0
    return (
        statistics.median(values),
        min(values),
        max(values),
        sum(1 for v in values if v > 0),
        sum(1 for v in values if v <= 0),
    )


def _pct(v):
    return "   N/A  " if v is None else f"{v * 100:>+7.2f}%"


def _assign_era(d):
    for label, cutoff in _ERAS:
        if cutoff is None or d < cutoff:
            return label
    return _ERAS[-1][0]


# ── Report ─────────────────────────────────────────────────────────────────────

W = 70

def _bar():  print("=" * W)
def _dash(): print("─" * W)


def _overall_row(key, crosses):
    label, gap, _ = _KEY_TO_META[key]
    n = len(crosses)
    vals_30 = [r["excess_30"] for r in crosses]
    med30, lo30, hi30, pos30, neg30 = _stats(vals_30)
    med60, *_ = _stats([r["excess_60"] for r in crosses])
    med90, *_ = _stats([r["excess_90"] for r in crosses])
    return (med30 or 0, label, n, med30, med60, med90, pos30, neg30)


def print_report(raw_records, all_signal_counts, excluded_end, n_total):

    # ── 1. Diagnostic ──────────────────────────────────────────────────────────
    _bar()
    print("  DIAGNOSTIC — RAW SIGNAL-DAYS AND DEDUP")
    _bar()
    print(f"  {'Criterion':<30}  {'Raw':>5}  {'Excl':>5}  {'Valid':>5}  "
          f"{'Gap':>5}  {'Events':>6}")
    _dash()

    criterion_crosses = {}
    for key, label, gap, _ in _CRITERIA:
        raw = raw_records[key]
        valid = len(raw)
        excl = excluded_end[key]
        crosses = dedup(raw, gap)
        criterion_crosses[key] = crosses
        print(f"  {label:<30}  {all_signal_counts[key]:>5}  {excl:>5}  "
              f"{valid:>5}  {gap:>4}d  {len(crosses):>6}")

    print()
    print("  'Events' = independent occurrences after dedup (the real sample size)")
    print()

    # ── 2. Ranked headline table ───────────────────────────────────────────────
    _bar()
    print("  RANKED BY OVERALL 30d MEDIAN EXCESS RETURN")
    _bar()

    rows = []
    for key, label, gap, _ in _CRITERIA:
        crosses = criterion_crosses[key]
        rows.append(_overall_row(key, crosses))

    rows.sort(key=lambda r: r[0], reverse=True)

    print(f"  {'Criterion':<30}  {'N':>4}  {'Med 30d':>8}  "
          f"{'Med 60d':>8}  {'Med 90d':>8}  {'Pos/Neg':>9}")
    _dash()
    for _, label, n, med30, med60, med90, pos, neg in rows:
        flag = "  [!]" if n < _SMALL_N else ""
        print(f"  {label:<30}  {n:>4}  {_pct(med30)}  "
              f"{_pct(med60)}  {_pct(med90)}  {pos:>3}/{neg:<3}{flag}")

    print()
    print("  [!] = N < 5 in overall sample — treat all figures with extreme caution")
    print()

    # ── 3. Per-criterion detail ────────────────────────────────────────────────
    _bar()
    print("  PER-CRITERION DETAIL — ERA BREAKDOWN")
    _bar()

    for _, label, n_overall, med30, med60, med90, pos30, neg30 in rows:
        # find key from label
        key = next(k for k, (lbl, *_) in _KEY_TO_META.items() if lbl == label)
        _, gap, rationale = _KEY_TO_META[key]
        crosses = criterion_crosses[key]
        n = len(crosses)

        print()
        print(f"  {label}   (N={n} events, dedup gap >{gap}d)")
        print(f"  Dedup rule: {rationale}")
        _dash()

        if n == 0:
            print("  No signal-days survived dedup — criterion never fired on AAPL in this period.")
            continue

        era_groups = {lbl: [] for lbl, _ in _ERAS}
        for cross in crosses:
            era_groups[_assign_era(cross["date"])].append(cross)

        for era_label, _ in _ERAS:
            era_crosses = era_groups[era_label]
            ne = len(era_crosses)
            print(f"\n    {era_label}   N={ne}")
            if ne == 0:
                print("      (no events in this era)")
                continue
            print(f"    {'Horizon':<8}  {'Median':>8}  {'Min':>8}  {'Max':>8}  {'Pos/Neg':>9}")
            print(f"    {'─'*8}  {'─'*8}  {'─'*8}  {'─'*8}  {'─'*9}")
            for hname, hkey in [("30d", "excess_30"), ("60d", "excess_60"), ("90d", "excess_90")]:
                vals = [r[hkey] for r in era_crosses]
                med, lo, hi, pos, neg = _stats(vals)
                print(f"    {hname:<8}  {_pct(med)}  {_pct(lo)}  {_pct(hi)}  "
                      f"{pos:>3}/{neg:<3}")
            if ne < _SMALL_N:
                print(f"\n    *** SAMPLE TOO SMALL (N={ne} < {_SMALL_N}) — "
                      f"no conclusions from this era ***")

        # Overall for this criterion
        print(f"\n    Overall   N={n}")
        print(f"    {'Horizon':<8}  {'Median':>8}  {'Min':>8}  {'Max':>8}  {'Pos/Neg':>9}")
        print(f"    {'─'*8}  {'─'*8}  {'─'*8}  {'─'*8}  {'─'*9}")
        for hname, hkey in [("30d", "excess_30"), ("60d", "excess_60"), ("90d", "excess_90")]:
            vals = [r[hkey] for r in crosses]
            med, lo, hi, pos, neg = _stats(vals)
            print(f"    {hname:<8}  {_pct(med)}  {_pct(lo)}  {_pct(hi)}  {pos:>3}/{neg:<3}")
        if n < _SMALL_N:
            print(f"\n    *** OVERALL SAMPLE TOO SMALL (N={n} < {_SMALL_N}) ***")

    # ── 4. Closing caveat ──────────────────────────────────────────────────────
    print()
    _bar()
    print("  CLOSING CAVEAT")
    _bar()
    print("  ONE stock (AAPL) — survivorship-selected from a portfolio already")
    print("  known to have performed well over 20 years.")
    print("  10 DETERMINISTIC criteria only — criteria 7 & 8 (AI-judged) excluded.")
    print("  Sustained criteria (C1/C2/C3/C4/C11/C12) have very few independent")
    print("  events by design — 'True for 3 years' counts as one event, not 756.")
    print("  Small event counts mean the min/max spread dominates the median.")
    print("  The ranking reflects ONE stock's history and may not generalize.")
    print("  This is a machinery check and component inspection — NOT a verdict")
    print("  on the Micha Method and NOT a recommendation to reweight criteria.")
    _bar()
    print()


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import truststore
    sys.stdout.reconfigure(encoding="utf-8")
    truststore.inject_into_ssl()

    raw_records, all_signal_counts, excluded_end, n_total = run_all_criteria("AAPL", years=20)
    print_report(raw_records, all_signal_counts, excluded_end, n_total)
