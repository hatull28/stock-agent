"""
Determinism and threshold-proximity checker for the 12 Micha criteria.

Fetches one frozen DataFrame and runs the full 12-criterion evaluation N times
against identical input to diagnose score flipping. Also prints the raw input
values for every deterministic criterion so marginal cases are visible.

Usage: python diagnostics/stability_check.py
Change TICKER below to test a different stock.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import truststore
truststore.inject_into_ssl()
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import pandas as pd
from config import BENCHMARK
from data import get_price_history
from analysis import full_micha_analysis
from blind_profiler import build_blind_profile

TICKER  = "AAPL"   # change here to test another stock
N_RUNS  = 10

_DETERMINISTIC = {
    "1_price_above_sma150",
    "2_sma150_slope_positive",
    "3_price_above_sma50",
    "4_sma50_above_sma150",
    "5_golden_cross_recent",
    "6_atr_shock_recent",
    "9_volume_expansion",
    "10_volume_dryup_before",
    "11_higher_highs_lows",
    "12_rs_vs_sp500",
}


def main():
    print("=" * 68)
    print(f"STABILITY CHECK — {TICKER}   N={N_RUNS} runs on frozen data")
    print("=" * 68)
    print()

    print(f"Fetching {TICKER} and benchmark ({BENCHMARK})... ", end="", flush=True)
    data = get_price_history(TICKER)
    benchmark_data = get_price_history(BENCHMARK)
    print("done\n")

    # ── Section 1: Profile hash stability ────────────────────────────────────
    print("─" * 68)
    print("SECTION 1 — Profile hash stability")
    print("─" * 68)

    hashes = [build_blind_profile(data)["profile_hash"] for _ in range(N_RUNS)]
    unique_hashes = set(hashes)

    if len(unique_hashes) == 1:
        print(f"PASS — hash is identical across all {N_RUNS} calls.")
        print(f"  {hashes[0][:32]}...")
    else:
        print(f"CRITICAL — profile_hash is NOT reproducible ({len(unique_hashes)} unique values seen).")
        print("  build_blind_profile() is not a pure function.")
        print("  The ledger's tamper-evidence guarantee is void until this is fixed.")
        for i, h in enumerate(hashes):
            print(f"  Run {i+1}: {h}")
        sys.exit(1)
    print()

    # ── Section 2: N full criterion runs ─────────────────────────────────────
    print("─" * 68)
    print(f"SECTION 2 — {N_RUNS} full evaluations on the same frozen DataFrame")
    print("─" * 68)

    all_criteria_runs = []
    all_scores        = []
    reasons_7         = []
    reasons_8         = []

    for i in range(N_RUNS):
        print(f"  Run {i+1}/{N_RUNS}...", end=" ", flush=True)
        result = full_micha_analysis(TICKER, data, benchmark_data)
        all_criteria_runs.append(result["criteria"])
        all_scores.append(result["score"])
        reasons_7.append(result["ai_reasons"].get("7", ""))
        reasons_8.append(result["ai_reasons"].get("8", ""))
        print(f"score={result['score']}/12")

    print()
    print(f"Score distribution : {all_scores}")
    print(f"Unique scores      : {sorted(set(all_scores))}")
    print()

    # per-criterion pass counts
    criteria_keys = sorted(all_criteria_runs[0].keys())
    flipped = []

    print(f"  {'Criterion':<35}  {'Passes':>7}  Type")
    print("  " + "-" * 60)
    for key in criteria_keys:
        passes  = sum(1 for run in all_criteria_runs if run.get(key))
        c_type  = "deterministic" if key in _DETERMINISTIC else "AI (variance expected)"
        flag    = ""
        if key in _DETERMINISTIC and passes not in (0, N_RUNS):
            flag = "  ⚠ FLIPPED"
            flipped.append((key, passes))
        print(f"  {key:<35}  {passes:>4}/{N_RUNS}  {c_type}{flag}")

    if flipped:
        print()
        for key, passes in flipped:
            print(f"  ⚠ DETERMINISTIC CRITERION FLIPPED: {key} passed {passes}/{N_RUNS}")
            print(f"    Deterministic code must not vary on identical input — this is a bug.")

    # AI rationale strings
    print()
    print("  Criterion 7 (Breakout) rationale per run:")
    for i, r in enumerate(reasons_7, 1):
        print(f"    Run {i:>2}: {r}")

    print()
    print("  Criterion 8 (Retest) rationale per run:")
    for i, r in enumerate(reasons_8, 1):
        print(f"    Run {i:>2}: {r}")
    print()

    # ── Section 3: Threshold proximity ───────────────────────────────────────
    print("─" * 68)
    print("SECTION 3 — Threshold proximity (raw input values vs cutoffs)")
    print("─" * 68)

    close  = data["Close"]
    high   = data["High"]
    low    = data["Low"]
    volume = data["Volume"]

    sma50  = close.rolling(window=50).mean()
    sma150 = close.rolling(window=150).mean()

    price_now   = float(close.iloc[-1])
    sma50_now   = float(sma50.iloc[-1])
    sma150_now  = float(sma150.iloc[-1])
    sma150_past = float(sma150.iloc[-21])

    # C1
    gap1 = price_now - sma150_now
    print(f"C1  price_above_sma150   price={price_now:.2f}  SMA150={sma150_now:.2f}  "
          f"gap={gap1:+.2f}  [{'PASS' if gap1 > 0 else 'FAIL'}]")

    # C2
    slope2 = sma150_now - sma150_past
    print(f"C2  sma150_slope_pos     SMA150_now={sma150_now:.2f}  SMA150_20d={sma150_past:.2f}  "
          f"delta={slope2:+.2f}  [{'PASS' if slope2 > 0 else 'FAIL'}]")

    # C3
    gap3 = price_now - sma50_now
    print(f"C3  price_above_sma50    price={price_now:.2f}  SMA50={sma50_now:.2f}  "
          f"gap={gap3:+.2f}  [{'PASS' if gap3 > 0 else 'FAIL'}]")

    # C4
    gap4 = sma50_now - sma150_now
    print(f"C4  sma50_above_sma150   SMA50={sma50_now:.2f}  SMA150={sma150_now:.2f}  "
          f"gap={gap4:+.2f}  [{'PASS' if gap4 > 0 else 'FAIL'}]")

    # C5 — golden cross (25-day window, must also be currently above)
    w5       = 26
    s50_w    = sma50.iloc[-w5:]
    s150_w   = sma150.iloc[-w5:]
    was_below5   = s50_w.shift(1) <= s150_w.shift(1)
    is_above5    = s50_w > s150_w
    cross5       = bool((was_below5 & is_above5).any()) and (sma50_now > sma150_now)
    # days since most recent cross (50-day lookback)
    w5b      = 51
    s50_wb   = sma50.iloc[-w5b:]
    s150_wb  = sma150.iloc[-w5b:]
    mask5b   = (s50_wb.shift(1) <= s150_wb.shift(1)) & (s50_wb > s150_wb)
    days_ago5 = int(mask5b.values[::-1].argmax()) if mask5b.any() else None
    print(f"C5  golden_cross_recent  cross_in_25d={cross5}  SMA50-SMA150={gap4:+.2f}  "
          f"days_since_cross={days_ago5}  [{'PASS' if cross5 else 'FAIL'}]")

    # C6 — ATR shock, upward only
    prev_close = close.shift(1)
    tr6  = pd.concat([high - low,
                      (high - prev_close).abs(),
                      (low  - prev_close).abs()], axis=1).max(axis=1)
    atr6      = tr6.rolling(window=14).mean()
    atr_pct6  = float((atr6.iloc[-1] / close.iloc[-1]) * 100)
    thresh6   = atr_pct6 + 3.0
    up_moves6 = (close.pct_change() * 100).iloc[-10:]
    max_up6   = float(up_moves6.max())
    print(f"C6  atr_shock_recent     atr_pct={atr_pct6:.2f}%  threshold={thresh6:.2f}%  "
          f"max_up_10d={max_up6:.2f}%  [{'PASS' if max_up6 > thresh6 else 'FAIL'}]")

    # C9 — volume expansion
    bg_vol     = float(volume.iloc[-70:-20].mean())
    recent_vol = float(volume.iloc[-5:].mean())
    ratio9     = recent_vol / bg_vol
    print(f"C9  volume_expansion     recent/bg={ratio9:.3f}  threshold=1.250  "
          f"[{'PASS' if ratio9 > 1.25 else 'FAIL'}]")

    # C10 — volume dry-up
    prior_vol = float(volume.iloc[-20:-5].mean())
    ratio10   = prior_vol / bg_vol
    print(f"C10 volume_dryup         prior/bg={ratio10:.3f}  threshold=0.900  "
          f"[{'PASS' if ratio10 < 0.90 else 'FAIL'}]")

    # C11 — higher highs & lows
    rec11 = close.iloc[-63:]
    pri11 = close.iloc[-126:-63]
    rh, rl = float(rec11.max()), float(rec11.min())
    ph, pl = float(pri11.max()), float(pri11.min())
    pass11 = rh > ph and rl > pl
    print(f"C11 higher_highs_lows    rec_max={rh:.2f} vs pri_max={ph:.2f}  "
          f"rec_min={rl:.2f} vs pri_min={pl:.2f}  [{'PASS' if pass11 else 'FAIL'}]")

    # C12 — RS vs S&P500
    stock_ret = float((close.iloc[-1] / close.iloc[-126]) - 1)
    bench_c   = benchmark_data["Close"]
    bench_ret = float((bench_c.iloc[-1] / bench_c.iloc[-126]) - 1)
    diff12    = stock_ret - bench_ret
    print(f"C12 rs_vs_sp500          stock_6m={stock_ret*100:.2f}%  "
          f"bench_6m={bench_ret*100:.2f}%  diff={diff12*100:+.2f}%  "
          f"[{'PASS' if diff12 > 0 else 'FAIL'}]")

    print()
    print("Notes:")
    print("  C7 and C8 are AI-judged (temperature 0.2) — flip is expected and benign.")
    print("  Any flip in C1–C6, C9–C12 on identical input is a determinism bug.")
    print("  Values close to their threshold are the most likely candidates to flip")
    print("  between runs if underlying data changes by even one tick.")


if __name__ == "__main__":
    main()
