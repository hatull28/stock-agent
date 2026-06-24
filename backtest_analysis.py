"""
backtest_analysis.py
Analysis layer for the golden cross backtest.

Takes raw records from backtest_engine.py, deduplicates to one record per
actual cross event, slices by market regime, and reports spread + sample size.

Descriptive only. No recommendations, no changes to the method.
"""

import statistics
from datetime import date

from backtest_engine import run_golden_cross_backtest

# ── Constants ──────────────────────────────────────────────────────────────────

_DEDUP_GAP_DAYS   = 15    # calendar-day gap that marks a new cross event
_SMALL_SAMPLE_N   = 5     # eras below this get an explicit warning
_RAW_SIGNAL_DAYS  = 300   # from engine (325 total − 25 excluded end-of-history)
_TOTAL_SIGNAL_DAYS = 325
_EXCLUDED_EOH      = 25

# Era definitions — ordered, checked in sequence
_ERAS = [
    ("Pre-Crisis (2006 – Aug 2008)",      date(2008, 9, 1)),
    ("Financial Crisis (Sep 2008 – 2009)", date(2010, 1, 1)),
    ("Bull Run (2010 – 2019)",             date(2020, 1, 1)),
    ("COVID / Volatility (2020 – 2022)",   date(2023, 1, 1)),
    ("Recent (2023 – present)",            None),             # open-ended
]


# ── Deduplication ──────────────────────────────────────────────────────────────

def dedup_to_crosses(records):
    """Collapse consecutive signal-day clusters into one record per actual cross.

    Rule: a new cross event starts when there is a gap of more than
    _DEDUP_GAP_DAYS calendar days between consecutive signal-days.
    Keep the FIRST day of each cluster (the actual cross date).

    Why track last_seen (not last_kept): the criterion fires True for ~25
    consecutive trading days per cross. If we compared each new record against
    the last-KEPT record, records within the same cluster could be > 15 cal days
    from the cluster start and falsely counted as new events. Tracking last_seen
    (every record, whether kept or not) correctly identifies breaks in the True
    streak — a gap only appears when the criterion actually went False.
    """
    if not records:
        return []
    crosses = [records[0]]
    last_seen = records[0]["date"]
    for rec in records[1:]:
        if (rec["date"] - last_seen).days > _DEDUP_GAP_DAYS:
            crosses.append(rec)
        last_seen = rec["date"]
    return crosses


# ── Era assignment ─────────────────────────────────────────────────────────────

def _assign_era(d):
    for label, cutoff in _ERAS:
        if cutoff is None or d < cutoff:
            return label
    return _ERAS[-1][0]


# ── Statistics helpers ─────────────────────────────────────────────────────────

def _stats(values):
    """Return (median, min, max, n_pos, n_neg) for a list of floats."""
    if not values:
        return None, None, None, 0, 0
    med   = statistics.median(values)
    lo    = min(values)
    hi    = max(values)
    n_pos = sum(1 for v in values if v > 0)
    n_neg = sum(1 for v in values if v <= 0)
    return med, lo, hi, n_pos, n_neg


def _fmt(v):
    """Format a decimal excess return as a signed percentage string."""
    if v is None:
        return "   N/A  "
    return f"{v * 100:>+7.2f}%"


# ── Report ─────────────────────────────────────────────────────────────────────

def _print_era_table(label, crosses):
    n = len(crosses)
    print(f"\n  {label}    N = {n}")
    print(f"  {'─' * 60}")

    if n == 0:
        print("  (no crosses in this era)")
        return

    horizons = [
        ("30d",  "excess_30"),
        ("60d",  "excess_60"),
        ("90d",  "excess_90"),
    ]
    print(f"  {'Horizon':<8}  {'Median':>8}  {'Min':>8}  {'Max':>8}  {'Pos/Neg':>9}")
    print(f"  {'─' * 8}  {'─' * 8}  {'─' * 8}  {'─' * 8}  {'─' * 9}")
    for hname, hkey in horizons:
        vals = [r[hkey] for r in crosses]
        med, lo, hi, n_pos, n_neg = _stats(vals)
        print(
            f"  {hname:<8}  {_fmt(med)}  {_fmt(lo)}  {_fmt(hi)}"
            f"  {n_pos:>3} / {n_neg:<3}"
        )

    if n < _SMALL_SAMPLE_N:
        print(f"\n  *** SAMPLE TOO SMALL (N={n} < {_SMALL_SAMPLE_N}) — "
              f"no conclusions can be drawn from this era ***")


def analyze(records):
    """Print the full analysis report from the engine's raw record list."""
    W = 62
    bar  = "=" * W
    dash = "─" * W

    # ── Dedup ─────────────────────────────────────────────────────────────────
    crosses = dedup_to_crosses(records)
    n_crosses = len(crosses)

    print(f"\n{bar}")
    print(f"  GOLDEN CROSS BACKTEST — AAPL — 20 YEARS")
    print(bar)
    print(f"  Engine output:    {_TOTAL_SIGNAL_DAYS} raw signal-days total")
    print(f"                    {_EXCLUDED_EOH} excluded (end-of-history, i+90 >= n)")
    print(f"                    {_RAW_SIGNAL_DAYS} records passed to this layer")
    print(f"  Dedup rule:       gap > {_DEDUP_GAP_DAYS} calendar days = new cross event")
    print(f"  Independent crosses: {n_crosses}  ← REAL SAMPLE SIZE (small — keep this in mind)")
    print(dash)

    # Cluster size check (printed for transparency)
    avg_cluster = _RAW_SIGNAL_DAYS / n_crosses if n_crosses else 0
    print(f"  Avg signal-days per cross: {avg_cluster:.1f}  "
          f"(wobble immunity + persistence check in criterion 5 affects cluster length)")

    # ── Per-era breakdown ──────────────────────────────────────────────────────
    era_groups = {label: [] for label, _ in _ERAS}
    for cross in crosses:
        era_groups[_assign_era(cross["date"])].append(cross)

    print(f"\n{bar}")
    print(f"  PER-ERA BREAKDOWN")
    print(bar)

    era_counts = []
    for label, _ in _ERAS:
        _print_era_table(label, era_groups[label])
        era_counts.append(len(era_groups[label]))

    assert sum(era_counts) == n_crosses, "Era counts don't sum to total crosses"

    # ── Overall ────────────────────────────────────────────────────────────────
    print(f"\n{bar}")
    print(f"  OVERALL — all {n_crosses} crosses, 20 years")
    print(bar)

    horizons = [("30d", "excess_30"), ("60d", "excess_60"), ("90d", "excess_90")]
    print(f"  {'Horizon':<8}  {'Median':>8}  {'Min':>8}  {'Max':>8}  {'Pos/Neg':>9}")
    print(f"  {'─' * 8}  {'─' * 8}  {'─' * 8}  {'─' * 8}  {'─' * 9}")
    for hname, hkey in horizons:
        vals = [r[hkey] for r in crosses]
        med, lo, hi, n_pos, n_neg = _stats(vals)
        print(
            f"  {hname:<8}  {_fmt(med)}  {_fmt(lo)}  {_fmt(hi)}"
            f"  {n_pos:>3} / {n_neg:<3}"
        )

    # ── Honesty caveat ─────────────────────────────────────────────────────────
    print(f"\n{bar}")
    print(f"  HONESTY CAVEAT")
    print(bar)
    print(f"  This report covers ONE criterion (criterion 5 — golden cross),")
    print(f"  ONE stock (AAPL — survivorship-selected from a portfolio already")
    print(f"  known to have performed well over this period). Total independent")
    print(f"  crosses: {n_crosses}. Per-era samples range from 0 to ~{max(era_counts)}.")
    print(f"  Single-digit sample sizes mean the spread (min/max) dominates")
    print(f"  the median — treat both as equally important.")
    print(f"  This is a machinery check and a first look at signal behavior")
    print(f"  in historical data. It is NOT a verdict on the Micha Method")
    print(f"  and NOT a recommendation to change any criterion or weighting.")
    print(f"{bar}\n")


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import truststore
    sys.stdout.reconfigure(encoding="utf-8")
    truststore.inject_into_ssl()

    records = run_golden_cross_backtest("AAPL", years=20)
    analyze(records)
