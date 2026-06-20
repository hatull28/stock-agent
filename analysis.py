import pandas as pd

def micha_criteria_1_to_5(data):
    """Compute Micha Method criteria 1-5 from price history.
    Returns a dict of PASS/FAIL results."""

    close = data["Close"]

    # --- compute the moving averages ---
    sma50 = close.rolling(window=50).mean()
    sma150 = close.rolling(window=150).mean()

    # grab the most recent values (last row)
    price_now = close.iloc[-1]
    sma50_now = sma50.iloc[-1]
    sma150_now = sma150.iloc[-1]
    sma150_past = sma150.iloc[-21]   # ~20 trading days ago

    # --- evaluate each criterion ---
    results = {}
    results["1_price_above_sma150"] = price_now > sma150_now
    results["2_sma150_slope_positive"] = sma150_now > sma150_past
    results["3_price_above_sma50"] = price_now > sma50_now
    results["4_sma50_above_sma150"] = sma50_now > sma150_now

    # Golden cross: SMA50 crossed above SMA150 within last 25 trading days AND is still above today
    window = 26  # 26 points → 25 consecutive pairs
    sma50_w = sma50.iloc[-window:]
    sma150_w = sma150.iloc[-window:]
    was_below = sma50_w.shift(1) <= sma150_w.shift(1)
    is_above  = sma50_w > sma150_w
    cross_happened = bool((was_below & is_above).any()) and (sma50_now > sma150_now)
    results["5_golden_cross_recent"] = cross_happened

    return results

def micha_criteria_6_to_12_code(data, benchmark_data):
    """Compute the code-based Micha criteria: 6, 9, 10, 11, 12.
    (7 and 8 are judged by the AI separately.)
    Returns a dict of PASS/FAIL results."""

    high = data["High"]
    low = data["Low"]
    close = data["Close"]
    volume = data["Volume"]

    results = {}

    # --- 6: ATR shock (a recent day moved > 3% beyond normal range) ---
    # True Range = the bigger of: today's high-low, or gap from yesterday's close
    prev_close = close.shift(1)
    true_range = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    atr = true_range.rolling(window=14).mean()

    # daily % move over the last 10 days vs the typical ATR %
    recent_pct_moves = (close.pct_change().abs() * 100).iloc[-10:]
    atr_pct = (atr.iloc[-1] / close.iloc[-1]) * 100
    # "shock" = any recent day moved more than ATR% + 3%
    results["6_atr_shock_recent"] = bool((recent_pct_moves > (atr_pct + 3)).any())

    # --- 9: Volume expansion (recent volume above its average) ---
    # Use days 21-70 ago as the baseline: excludes both the dry-up window (days 6-20)
    # and the expansion window (days 1-5), so neither contaminates the reference.
    background_vol = volume.iloc[-70:-20].mean()
    recent_vol = volume.iloc[-5:].mean()          # last 5 days
    # expansion = recent volume at least 1.25x the background average
    results["9_volume_expansion"] = bool(recent_vol > 1.25 * background_vol)

    # --- 10: Volume dry-up (a quiet stretch existed before recent action) ---
    # look at days 6-20 ago: was volume below 90% of the background average?
    prior_vol = volume.iloc[-20:-5].mean()
    results["10_volume_dryup_before"] = bool(prior_vol < 0.9 * background_vol)

    # --- 11: Higher highs & higher lows (uptrend structure) ---
    # compare the most recent ~3 months to the prior ~3 months
    recent = close.iloc[-63:]
    prior = close.iloc[-126:-63]
    higher_high = recent.max() > prior.max()
    higher_low = recent.min() > prior.min()
    results["11_higher_highs_lows"] = bool(higher_high and higher_low)

    # --- 12: Relative strength vs S&P500 (stock outperforming index) ---
    # compare 6-month return of stock vs benchmark
    stock_return = (close.iloc[-1] / close.iloc[-126]) - 1
    bench_close = benchmark_data["Close"]
    bench_return = (bench_close.iloc[-1] / bench_close.iloc[-126]) - 1
    results["12_rs_vs_sp500"] = bool(stock_return > bench_return)

    return results
def compute_price_levels(data):
    """Extract real numeric price/SMA levels for cycle and buy-zone calculations."""
    close = data["Close"]
    sma50 = close.rolling(window=50).mean()
    sma150 = close.rolling(window=150).mean()

    price_now = float(close.iloc[-1])
    sma50_val = float(sma50.iloc[-1])
    sma150_val = float(sma150.iloc[-1])

    # how far extended above each SMA
    price_vs_sma50_pct  = (price_now - sma50_val)  / sma50_val  * 100
    price_vs_sma150_pct = (price_now - sma150_val) / sma150_val * 100

    # support levels (reuse same windows as criterion 11)
    recent_3m_low  = float(close.iloc[-63:].min())
    recent_3m_high = float(close.iloc[-63:].max())
    prior_3m_low   = float(close.iloc[-126:-63].min())
    hist = close.iloc[-252:] if len(close) >= 252 else close
    week_52_low = float(hist.min())

    # day-over-day price change
    price_change     = float(close.iloc[-1] - close.iloc[-2])
    price_change_pct = float((close.iloc[-1] / close.iloc[-2] - 1) * 100)
    price_date       = str(close.index[-1].date())

    # how many trading days ago did SMA50 cross above SMA150? (50-day lookback)
    window = 51  # 51 points → 50 consecutive pairs
    sma50_w  = sma50.iloc[-window:]
    sma150_w = sma150.iloc[-window:]
    was_below    = sma50_w.shift(1) <= sma150_w.shift(1)
    is_above     = sma50_w > sma150_w
    cross_mask   = was_below & is_above
    golden_cross_days_ago = int(cross_mask.values[::-1].argmax()) if cross_mask.any() else None

    return {
        "price_now":            price_now,
        "price_change":         price_change,
        "price_change_pct":     price_change_pct,
        "price_date":           price_date,
        "sma50":                sma50_val,
        "sma150":               sma150_val,
        "price_vs_sma50_pct":   price_vs_sma50_pct,
        "price_vs_sma150_pct":  price_vs_sma150_pct,
        "recent_3m_low":        recent_3m_low,
        "recent_3m_high":       recent_3m_high,
        "prior_3m_low":         prior_3m_low,
        "week_52_low":          week_52_low,
        "golden_cross_days_ago": golden_cross_days_ago,
    }


def classify_cycle_stage(criteria, price_levels):
    """Classify the stock's trend cycle stage using computed signals only."""
    if not criteria.get("4_sma50_above_sma150"):
        return "NONE"

    pct_above = price_levels["price_vs_sma50_pct"]
    cross_days = price_levels["golden_cross_days_ago"]

    if cross_days is not None and cross_days <= 50 and pct_above < 10:
        return "EARLY"
    if pct_above >= 22:
        return "LATE"
    return "MID"


def compute_buy_zone(price_levels, cycle_stage):
    """Return a code-grounded accumulation price range. No AI numbers."""
    if cycle_stage == "NONE":
        return None
    sma50 = price_levels["sma50"]
    return {
        "low":   round(sma50, 2),
        "high":  round(sma50 * 1.04, 2),
        "floor": round(price_levels["recent_3m_low"], 2),
    }


def full_micha_analysis(ticker, data, benchmark_data):
    """Run all 12 Micha criteria (10 code + 2 AI) and return combined results."""
    from ai_layer import judge_breakout_and_retest

    # code-based criteria
    part1 = micha_criteria_1_to_5(data)
    part2 = micha_criteria_6_to_12_code(data, benchmark_data)

    # AI-based criteria (7 & 8)
    ai_part = judge_breakout_and_retest(ticker, data)
    reasons = ai_part.pop("_reasons", {})   # pull reasons out separately

    # merge everything into one dict
    all_criteria = {**part1, **part2, **ai_part}

    score = sum(all_criteria.values())

    return {
        "ticker": ticker,
        "score": score,
        "criteria": all_criteria,
        "ai_reasons": reasons,
    }
# --- test it ---
if __name__ == "__main__":
    from data import get_price_history
    from config import PORTFOLIO, BENCHMARK

    print("Fetching benchmark (S&P500)...")
    benchmark_data = get_price_history(BENCHMARK)

    results = []
    for ticker in PORTFOLIO:
        print(f"\nAnalyzing {ticker}...")
        try:
            data = get_price_history(ticker)
            result = full_micha_analysis(ticker, data, benchmark_data)
            results.append(result)
            print(f"  {ticker}: MICHA SCORE {result['score']}/12")
        except Exception as e:
            print(f"  ERROR analyzing {ticker}: {e}")

    # summary table, sorted best to worst
    print("\n" + "=" * 40)
    print("PORTFOLIO MICHA SCORES (best to worst)")
    print("=" * 40)
    results.sort(key=lambda r: r["score"], reverse=True)
    for r in results:
        print(f"  {r['ticker']:6} {r['score']}/12")


def analyze_stock(ticker, benchmark_data):
    """Run the COMPLETE analysis (all 3 parts) for one stock."""
    from data import get_price_history
    from fundamentals import get_fundamentals
    from ai_layer import peter_lynch_score, combined_verdict, analyze_cycle_and_zones

    data = get_price_history(ticker)

    # Part 1: Micha technical
    micha = full_micha_analysis(ticker, data, benchmark_data)

    # Part 2: Peter Lynch fundamental
    fundamentals = get_fundamentals(ticker)
    peter = peter_lynch_score(ticker, fundamentals)

    # Part 3: combined verdict
    verdict = combined_verdict(ticker, micha, peter)

    # Part 4: cycle stage & buy zone (code computes numbers; AI writes prose)
    price_levels = compute_price_levels(data)
    cycle_stage  = classify_cycle_stage(micha["criteria"], price_levels)
    buy_zone     = compute_buy_zone(price_levels, cycle_stage)
    cycle_info   = analyze_cycle_and_zones(ticker, cycle_stage, price_levels, buy_zone, micha["criteria"]) \
                   if buy_zone else {}

    return {
        "ticker": ticker,
        "name": fundamentals.get("name", ticker),
        "sector": fundamentals.get("sector", "Unknown"),
        "micha_score": micha["score"],
        "micha_criteria": micha["criteria"],
        "micha_reasons": micha["ai_reasons"],
        "peter_score": peter["peter_score"] if peter else None,
        "peter_summary": peter["summary"] if peter else "",
        "peter_scores": peter.get("scores", {}) if peter else {},
        "verdict": verdict,
        "cycle_stage":           cycle_stage,
        "cycle_stage_reasoning": cycle_info.get("cycle_stage_reasoning", ""),
        "buy_zone":              buy_zone,
        "buy_zone_narrative":    cycle_info.get("buy_zone_narrative", ""),
        "price_levels":          price_levels,
    }