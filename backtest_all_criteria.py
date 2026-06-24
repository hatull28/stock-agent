"""
backtest_all_criteria.py
Walk-forward backtest of all 10 DETERMINISTIC Micha criteria,
across all 8 portfolio tickers. Per-stock only — no pooling.

Criteria 7 & 8 (AI-judged) are excluded — they cannot be backtested without
lookahead bias. This file covers: 1, 2, 3, 4, 5, 6, 9, 10, 11, 12.

Walk-forward discipline:
  Signal  : computed on stock_df.iloc[0:i+1]  — strictly no lookahead
  Forward : separate numpy arrays, indices i+30, i+60, i+90

Output:
  Terminal — compact cross-stock matrix (criteria × tickers, 30d median)
  File     — backtest_report.txt, full per-stock per-era detail
"""

import json
import statistics
import sys
import time
from datetime import date
from pathlib import Path

from analysis import micha_criteria_1_to_5, micha_criteria_6_to_12_code
from backtest_data import fetch_history

# ── Portfolio ──────────────────────────────────────────────────────────────────

_PORTFOLIO_FILE = Path(__file__).parent / "portfolio.json"


def _load_portfolio():
    with open(_PORTFOLIO_FILE) as f:
        return json.load(f)["portfolio"]


# ── Walk-forward parameters ────────────────────────────────────────────────────

_MIN_ROWS  = 150   # SMA150 needs this; covers all other criteria too
_N_FORWARD = 90    # exclude signals within 90 trading days of end

# ── Criterion metadata ─────────────────────────────────────────────────────────

# (key, short label, dedup gap calendar days, rationale)
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

_SMALL_N             = 5
_SHORT_HISTORY_YEARS = 15.0   # flag tickers with less than this


# ── Walk-forward engine ────────────────────────────────────────────────────────

def run_all_criteria(ticker="AAPL", years=20):
    """Walk-forward scan for all 10 deterministic criteria.

    Returns:
        (raw_records, all_signal_counts, excluded_end, n_total, first_date, last_date)
    """
    print(f"Loading data for {ticker} + benchmark...")
    stock_df, bench_df = fetch_history(ticker, years=years)

    # Normalize tz: fresh yfinance data is tz-aware; cached CSV reads back tz-naive.
    # Strip tz from both so the intersection works regardless of fetch order.
    if hasattr(stock_df.index, "tz") and stock_df.index.tz is not None:
        stock_df.index = stock_df.index.tz_localize(None)
    if hasattr(bench_df.index, "tz") and bench_df.index.tz is not None:
        bench_df.index = bench_df.index.tz_localize(None)

    common_idx = stock_df.index.intersection(bench_df.index)
    stock_df = stock_df.loc[common_idx].copy()
    bench_df = bench_df.loc[common_idx].copy()

    n = len(stock_df)
    dates = stock_df.index
    first_date = dates[0].date()
    last_date  = dates[-1].date()
    stock_close = stock_df["Close"].values
    bench_close = bench_df["Close"].values

    actual_years = (last_date - first_date).days / 365.25
    print(f"Aligned: {n:,} trading days  ({first_date} → {last_date},  {actual_years:.1f}yr)\n")

    raw_records       = {key: [] for key, *_ in _CRITERIA}
    all_signal_counts = {key: 0  for key, *_ in _CRITERIA}
    excluded_end      = {key: 0  for key, *_ in _CRITERIA}

    t0 = time.time()
    scan_start = _MIN_ROWS - 1

    for i in range(scan_start, n):
        if (i - scan_start) % 1000 == 0 and i > scan_start:
            pct = 100 * (i - scan_start) / (n - scan_start)
            print(f"  ... {i - scan_start:,} / {n - scan_start:,}  ({pct:.0f}%)  "
                  f"[{time.time() - t0:.0f}s]")

        slice_s = stock_df.iloc[0:i + 1]
        slice_b = bench_df.iloc[0:i + 1]

        c1to5  = micha_criteria_1_to_5(slice_s)
        c6to12 = micha_criteria_6_to_12_code(slice_s, slice_b)
        all_c  = {**c1to5, **c6to12}

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

    return raw_records, all_signal_counts, excluded_end, n, first_date, last_date


# ── Deduplication ──────────────────────────────────────────────────────────────

def dedup(records, gap_days):
    """Keep the first record of each True-streak event.

    Compares each record against the last-SEEN date (not last-kept) so that
    long continuous streaks do not get falsely split when the gap from the
    cluster start exceeds gap_days inside the same streak.
    """
    if not records:
        return []
    out = [records[0]]
    last_seen = records[0]["date"]
    for rec in records[1:]:
        if (rec["date"] - last_seen).days > gap_days:
            out.append(rec)
        last_seen = rec["date"]
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


# ── Full per-stock detail report ───────────────────────────────────────────────

W = 70


def print_report(raw_records, all_signal_counts, excluded_end, n_total,
                 ticker="AAPL", first_date=None, last_date=None, file=None):
    """Print full per-criterion + per-era breakdown for one ticker."""

    def p(*args, **kw):
        print(*args, file=file, **kw)

    def bar():
        p("=" * W)

    def dash():
        p("─" * W)

    actual_years = ((last_date - first_date).days / 365.25
                    if first_date and last_date else None)
    span_str = (f"{first_date} → {last_date} ({actual_years:.1f}yr)"
                if actual_years else "unknown span")

    bar()
    p(f"  {ticker} — MICHA METHOD BACKTEST")
    p(f"  Data span: {span_str}")
    if actual_years and actual_years < _SHORT_HISTORY_YEARS:
        p(f"  *** SHORT HISTORY: only {actual_years:.1f}yr — samples will be smaller ***")
    bar()

    # ── 1. Diagnostic ──────────────────────────────────────────────────────────
    p()
    p("  DIAGNOSTIC — RAW SIGNAL-DAYS AND DEDUP")
    dash()
    p(f"  {'Criterion':<30}  {'Raw':>5}  {'Excl':>5}  {'Valid':>5}  "
      f"{'Gap':>5}  {'Events':>6}")
    dash()

    criterion_crosses = {}
    for key, label, gap, _ in _CRITERIA:
        raw    = raw_records[key]
        valid  = len(raw)
        excl   = excluded_end[key]
        crosses = dedup(raw, gap)
        criterion_crosses[key] = crosses
        p(f"  {label:<30}  {all_signal_counts[key]:>5}  {excl:>5}  "
          f"{valid:>5}  {gap:>4}d  {len(crosses):>6}")

    p()
    p("  'Events' = independent occurrences after dedup (the real sample size)")
    p()

    # ── 2. Ranked headline table ───────────────────────────────────────────────
    bar()
    p("  RANKED BY OVERALL 30d MEDIAN EXCESS RETURN")
    bar()

    rows = []
    for key, label, gap, _ in _CRITERIA:
        crosses = criterion_crosses[key]
        n       = len(crosses)
        med30, lo30, hi30, pos30, neg30 = _stats([r["excess_30"] for r in crosses])
        med60, *_ = _stats([r["excess_60"] for r in crosses])
        med90, *_ = _stats([r["excess_90"] for r in crosses])
        rows.append((med30 or 0, label, n, med30, med60, med90, pos30, neg30))

    rows.sort(key=lambda r: r[0], reverse=True)

    p(f"  {'Criterion':<30}  {'N':>4}  {'Med 30d':>8}  "
      f"{'Med 60d':>8}  {'Med 90d':>8}  {'Pos/Neg':>9}")
    dash()
    for _, label, n, med30, med60, med90, pos, neg in rows:
        flag = "  [!]" if n < _SMALL_N else ""
        p(f"  {label:<30}  {n:>4}  {_pct(med30)}  "
          f"{_pct(med60)}  {_pct(med90)}  {pos:>3}/{neg:<3}{flag}")

    p()
    p("  [!] = N < 5 in overall sample — treat all figures with extreme caution")
    p()

    # ── 3. Per-criterion era detail ────────────────────────────────────────────
    bar()
    p("  PER-CRITERION DETAIL — ERA BREAKDOWN")
    bar()

    for _, label, n_overall, med30, med60, med90, pos30, neg30 in rows:
        key = next(k for k, (lbl, *_) in _KEY_TO_META.items() if lbl == label)
        _, gap, rationale = _KEY_TO_META[key]
        crosses = criterion_crosses[key]
        n = len(crosses)

        p()
        p(f"  {label}   (N={n} events, dedup gap >{gap}d)")
        p(f"  Dedup rule: {rationale}")
        dash()

        if n == 0:
            p(f"  No signal-days survived dedup — criterion never fired on "
              f"{ticker} in this period.")
            continue

        era_groups = {lbl: [] for lbl, _ in _ERAS}
        for cross in crosses:
            era_groups[_assign_era(cross["date"])].append(cross)

        for era_label, _ in _ERAS:
            era_crosses = era_groups[era_label]
            ne = len(era_crosses)
            p(f"\n    {era_label}   N={ne}")
            if ne == 0:
                p("      (no events in this era)")
                continue
            p(f"    {'Horizon':<8}  {'Median':>8}  {'Min':>8}  {'Max':>8}  {'Pos/Neg':>9}")
            p(f"    {'─'*8}  {'─'*8}  {'─'*8}  {'─'*8}  {'─'*9}")
            for hname, hkey in [("30d", "excess_30"), ("60d", "excess_60"),
                                 ("90d", "excess_90")]:
                vals = [r[hkey] for r in era_crosses]
                med, lo, hi, pos, neg = _stats(vals)
                p(f"    {hname:<8}  {_pct(med)}  {_pct(lo)}  {_pct(hi)}  "
                  f"{pos:>3}/{neg:<3}")
            if ne < _SMALL_N:
                p(f"\n    *** SAMPLE TOO SMALL (N={ne} < {_SMALL_N}) — "
                  f"no conclusions from this era ***")

        p(f"\n    Overall   N={n}")
        p(f"    {'Horizon':<8}  {'Median':>8}  {'Min':>8}  {'Max':>8}  {'Pos/Neg':>9}")
        p(f"    {'─'*8}  {'─'*8}  {'─'*8}  {'─'*8}  {'─'*9}")
        for hname, hkey in [("30d", "excess_30"), ("60d", "excess_60"),
                             ("90d", "excess_90")]:
            vals = [r[hkey] for r in crosses]
            med, lo, hi, pos, neg = _stats(vals)
            p(f"    {hname:<8}  {_pct(med)}  {_pct(lo)}  {_pct(hi)}  {pos:>3}/{neg:<3}")
        if n < _SMALL_N:
            p(f"\n    *** OVERALL SAMPLE TOO SMALL (N={n} < {_SMALL_N}) ***")

    p()


# ── Cross-stock summary matrix ─────────────────────────────────────────────────

def print_cross_stock_matrix(all_results, tickers, file=None):
    """Rows = 10 criteria, cols = tickers, cell = 30d median excess return (N events)."""

    def p(*args, **kw):
        print(*args, file=file, **kw)

    COL = 12   # chars per ticker column (content + padding)
    LABEL_W = 22

    total_w = LABEL_W + COL * len(tickers)

    p()
    p("=" * total_w)
    p("  CROSS-STOCK SUMMARY MATRIX — 30d MEDIAN EXCESS RETURN")
    p("  Per-stock only. NOT pooled across tickers (see closing caveat).")
    p("  Cell: +X.X%(N)  where N = independent events after dedup")
    p("=" * total_w)

    # Header
    hdr = f"  {'Criterion':<{LABEL_W - 2}}"
    for t in tickers:
        hdr += f"{t:^{COL}}"
    p(hdr)
    p("  " + "─" * (LABEL_W - 2 + COL * len(tickers)))

    # Data rows
    for key, label, gap, _ in _CRITERIA:
        short_label = label[:LABEL_W - 2]
        row = f"  {short_label:<{LABEL_W - 2}}"
        for ticker in tickers:
            if ticker not in all_results:
                cell = "—"
            else:
                raw_records = all_results[ticker][0]
                crosses = dedup(raw_records[key], gap)
                n = len(crosses)
                if n == 0:
                    cell = "—(0)"
                else:
                    med, *_ = _stats([r["excess_30"] for r in crosses])
                    cell = f"{med * 100:+.1f}%({n})" if med is not None else "N/A"
            row += f"{cell:^{COL}}"
        p(row)

    # History spans
    p()
    p("  History spans per ticker:")
    for ticker in tickers:
        if ticker not in all_results:
            continue
        _, _, _, _, first_date, last_date = all_results[ticker]
        if first_date and last_date:
            yrs = (last_date - first_date).days / 365.25
            flag = "  *** SHORT HISTORY ***" if yrs < _SHORT_HISTORY_YEARS else ""
            p(f"    {ticker:<6}: {first_date} → {last_date} ({yrs:.1f}yr){flag}")
    p()


# ── Closing caveat ─────────────────────────────────────────────────────────────

def _print_closing_caveat(tickers, short_history_tickers, file=None):

    def p(*args, **kw):
        print(*args, file=file, **kw)

    W_C = 72
    p("=" * W_C)
    p("  CLOSING CAVEAT")
    p("=" * W_C)
    p("  Results are PER-STOCK — NOT pooled across tickers (by design).")
    p("  These 8 stocks are highly correlated (large-cap US tech + semis).")
    p("  Pooling across them would inflate apparent N and create false")
    p("  confidence that is not supported by truly independent observations.")
    p("  Cross-stock comparison is deliberately left to the human reader.")
    p()
    p("  All 8 tickers are SURVIVORSHIP-SELECTED — known portfolio members")
    p("  that have already performed well. Results are not representative")
    p("  of the broader stock universe.")
    p()
    p("  10 DETERMINISTIC criteria only — criteria 7 & 8 (AI-judged) excluded.")
    if short_history_tickers:
        p()
        p(f"  SHORT HISTORY: {', '.join(short_history_tickers)}")
        p("  These tickers have fewer years of data; era samples are smaller.")
    p()
    p("  Sustained criteria (C1/C2/C3/C4/C11/C12) produce very few independent")
    p("  events by design — 'True for 3 years' counts as one event, not 756.")
    p("  Small event counts mean min/max spread dominates the median.")
    p()
    p("  This is a first look at signal behavior across the portfolio names.")
    p("  It is NOT a verdict on the Micha Method and NOT a recommendation")
    p("  to reweight criteria or adjust the portfolio.")
    p("=" * W_C)
    p()


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import truststore
    sys.stdout.reconfigure(encoding="utf-8")
    truststore.inject_into_ssl()

    tickers = _load_portfolio()

    print(f"\nRunning walk-forward backtest for {len(tickers)} tickers: "
          f"{', '.join(tickers)}")
    print("Each ticker scans ~20yr of daily data. This takes several minutes.\n")

    all_results = {}
    for ticker in tickers:
        print(f"\n{'#' * 70}")
        print(f"#  {ticker}")
        print(f"{'#' * 70}")
        all_results[ticker] = run_all_criteria(ticker, years=20)

    # Identify short-history tickers
    short_history = [
        t for t in tickers
        if t in all_results
        and all_results[t][4] is not None
        and all_results[t][5] is not None
        and (all_results[t][5] - all_results[t][4]).days / 365.25 < _SHORT_HISTORY_YEARS
    ]

    # ── Terminal: cross-stock matrix + caveat ──────────────────────────────────
    print_cross_stock_matrix(all_results, tickers, file=None)
    _print_closing_caveat(tickers, short_history, file=None)

    # ── File: full per-stock detail + matrix + caveat ──────────────────────────
    report_path = Path(__file__).parent / "backtest_report.txt"
    print(f"Writing full detail report to {report_path.name} ...")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("MICHA METHOD BACKTEST — ALL 8 PORTFOLIO TICKERS\n")
        f.write("Per-stock only. NOT pooled. Descriptive only.\n")
        f.write(f"Generated: {date.today()}\n")
        f.write("=" * 70 + "\n\n")

        for ticker in tickers:
            if ticker not in all_results:
                continue
            raw_records, signal_counts, excluded_end, n_total, first_date, last_date = \
                all_results[ticker]
            print_report(raw_records, signal_counts, excluded_end, n_total,
                         ticker=ticker, first_date=first_date, last_date=last_date,
                         file=f)
            f.write("\n\n")

        print_cross_stock_matrix(all_results, tickers, file=f)
        _print_closing_caveat(tickers, short_history, file=f)

    print(f"Done. Full report saved to {report_path.name}")
