import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    timeout=120.0,
)

MODEL = "deepseek/deepseek-chat"   # change here anytime


def summarize_recent_action(data, days=40):
    """Build a compact text summary of recent price/volume for the AI to read."""
    recent = data.iloc[-days:]
    lines = []
    for date, row in recent.iterrows():
        lines.append(
            f"{date.date()}  "
            f"O:{row['Open']:.2f} H:{row['High']:.2f} "
            f"L:{row['Low']:.2f} C:{row['Close']:.2f} "
            f"Vol:{int(row['Volume'])}"
        )
    return "\n".join(lines)


def judge_breakout_and_retest(ticker, data):
    """Ask the AI to judge Micha criteria 7 (breakout) and 8 (retest).

    The prompt is anonymized: no ticker symbol, no calendar dates, no absolute prices.
    OHLC values are indexed to Day 1 Close = 100.00; volume is expressed as a ratio
    of the 40-day mean. This prevents the model from pattern-matching against its
    training-data memory of what a specific stock did on a specific date.
    """
    from blind_profiler import build_blind_profile, format_profile_table

    profile = build_blind_profile(data)
    price_table = format_profile_table(profile["rows"])

    prompt = f"""You are a strict technical analyst applying the Micha Method.
Analyze the following 40 trading days of an anonymous equity.

Encoding:
- Day 1 Close = 100.00. All O/H/L/C values are percentages of that anchor.
- V_ratio = each day's volume divided by the mean volume over the 40-day window.

Judge exactly two criteria:
- Criterion 7 (Breakout quality): Did the stock make a CLEAN breakout above a
  recent resistance/consolidation, with a strong move rather than a weak, choppy push?
- Criterion 8 (Retest quality): After any breakout, did price pull back to the
  breakout level and HOLD it (a successful retest), rather than falling back through?

If there is no clear breakout in this window, criterion 7 is FAIL and criterion 8
is FAIL (nothing to retest).

Daily data (oldest to newest):
{price_table}

Respond ONLY with valid JSON, no other text, in exactly this format:
{{
  "criterion_7_breakout": {{"pass": true or false, "reason": "one sentence"}},
  "criterion_8_retest": {{"pass": true or false, "reason": "one sentence"}}
}}"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
        temperature=0.2
    )

    raw = response.choices[0].message.content

    # strip markdown code fences if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    # parse the JSON text into a Python dictionary
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        print(f"  WARNING: could not parse AI response for {ticker}, retrying...")
        retry_prompt = (
            "Return ONLY this JSON, no other text:\n"
            '{"criterion_7_breakout":{"pass":true,"reason":"one sentence"},'
            '"criterion_8_retest":{"pass":false,"reason":"one sentence"}}\n\n'
            "Use the price data provided. Was there a clean breakout? Was there a successful retest?"
        )
        retry_resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": raw},
                {"role": "user", "content": retry_prompt},
            ],
            max_tokens=400,
        )
        retry_raw = retry_resp.choices[0].message.content.strip()
        if retry_raw.startswith("```"):
            retry_raw = retry_raw.split("```")[1]
            if retry_raw.startswith("json"):
                retry_raw = retry_raw[4:]
            retry_raw = retry_raw.strip()
        try:
            parsed = json.loads(retry_raw)
        except json.JSONDecodeError:
            print(f"  WARNING: retry also failed for {ticker}, defaulting both to FAIL")
            return {"7_breakout_quality": False, "8_retest_quality": False,
                    "_profile_hash": profile["profile_hash"]}

    # convert to the same simple format as our other criteria
    return {
        "7_breakout_quality": bool(parsed["criterion_7_breakout"]["pass"]),
        "8_retest_quality": bool(parsed["criterion_8_retest"]["pass"]),
        "_reasons": {
            "7": parsed["criterion_7_breakout"]["reason"],
            "8": parsed["criterion_8_retest"]["reason"],
        },
        "_profile_hash": profile["profile_hash"],
    }
def peter_lynch_score(ticker, fundamentals):
    """Ask the AI to score the 10 Peter Lynch criteria (1-10 each) from real data."""

    # build a clean readable list of the real numbers
    facts = []
    for key, value in fundamentals.items():
        facts.append(f"  {key}: {value}")
    facts_text = "\n".join(facts)

    prompt = f"""You are Peter Lynch analyzing {ticker} for long-term investment.
Below are the ACTUAL fundamental figures. Do not invent numbers; reason only from these.
Note: some ratios may look unusual (e.g. very high ROE from buybacks) - interpret sensibly.
Some values may be null if unavailable - score those criteria conservatively.

Fundamentals:
{facts_text}

Score each of these 10 criteria from 1 (poor) to 10 (excellent).

IMPORTANT — data availability:
- Criteria 1, 2, 4, 5, 7: score freely from the fundamentals above.
- Criteria 3, 6, 8, 9, 10: NO specific data was provided for these (no net income trend,
  no competitive positioning, no management data, no industry rank). Score these at exactly 5
  unless the available fundamentals strongly imply otherwise (e.g. FCF=negative implies
  poor cash quality). Do NOT invent narrative; just score 5 as neutral.

1. Revenue Growth
2. EPS Growth
3. Net Income Trend  [no trend data — default 5 unless earnings_growth implies otherwise]
4. Balance Sheet Strength
5. Cash Flow Quality
6. Moat & Competitive Edge  [no competitive data — default 5]
7. Valuation (P/E, PEG, FCF yield)
8. Management quality  [no management data — default 5]
9. Industry strength  [no industry data — default 5]
10. Long-term compounding potential  [infer from available data only]

Respond ONLY with valid JSON in exactly this format:
{{
  "scores": {{
    "revenue_growth": <1-10>,
    "eps_growth": <1-10>,
    "net_income_trend": <1-10>,
    "balance_sheet": <1-10>,
    "cash_flow": <1-10>,
    "moat": <1-10>,
    "valuation": <1-10>,
    "management": <1-10>,
    "industry": <1-10>,
    "long_term_compounding": <1-10>
  }},
  "summary": "2-3 sentence long-term fundamental assessment based only on the data above. Do NOT claim the company has a strong moat, excellent management, or dominant industry position — those criteria have no data backing. Stick to what the numbers show."
}}"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000,
        temperature=0.2
    )

    raw = response.choices[0].message.content

    # strip markdown fences (same as before)
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        print(f"  WARNING: could not parse Peter Lynch response for {ticker}")
        return None

    scores = parsed["scores"]
    # Peter score = average of the 10 criteria, on a 0-10 scale
    peter_score = sum(scores.values()) / len(scores)

    return {
        "ticker": ticker,
        "peter_score": round(peter_score, 1),
        "scores": scores,
        "summary": parsed.get("summary", ""),
    }




def combined_verdict(ticker, micha_result, peter_result):
    """Synthesize Micha (technical) + Peter (fundamental) into a final verdict."""

    micha_score = micha_result["score"]
    peter_score = peter_result["peter_score"]

    prompt = f"""You are an investment analyst combining two analyses for {ticker}.

MICHA METHOD (technical health, 0-12): {micha_score}/12
  This measures trend strength, breakouts, volume, and relative strength.
  A high score = technically strong/uptrending. A low score = weak/below trend.

PETER LYNCH (fundamental quality, 0-10): {peter_score}/10
  This measures business quality, growth, valuation, and moat.
  Fundamental summary: {peter_result['summary']}

Provide a verdict. Remember: a stock can be fundamentally strong but technically
weak (possible buy-the-dip), or technically strong but fundamentally weak (momentum
but risky). Reason about the COMBINATION.

Rules:
- The "action" field MUST be exactly one of: BUY NOW, WAIT FOR PULLBACK, AVOID, ACCUMULATE.
  No other strings are accepted.
- The "short_term" field MUST be consistent with the "action" field. If action is AVOID or
  WAIT FOR PULLBACK, short_term must not recommend buying. If action is BUY NOW or ACCUMULATE,
  short_term must not say to wait or avoid.
- The "accumulation_strategy" field must NOT mention specific dollar price targets. Describe
  only the approach (tranching, sizing, triggers) — specific price zones are provided
  separately by the system.

Respond ONLY with valid JSON in this format:
{{
  "micha_meaning": "1 sentence on what the technical score means here",
  "peter_meaning": "1 sentence on what the fundamental score means here",
  "short_term": "recommendation for 1-6 months, consistent with the action",
  "long_term": "recommendation for 2-5 years",
  "action": "BUY NOW / WAIT FOR PULLBACK / AVOID / ACCUMULATE",
  "accumulation_strategy": "1-2 sentences on approach only, no specific price targets"
}}"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000,
        temperature=0
    )

    raw = response.choices[0].message.content
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        print(f"  WARNING: could not parse verdict for {ticker}")
        return None

    # Validate and normalise the action string
    _allowed = {"BUY NOW", "WAIT FOR PULLBACK", "AVOID", "ACCUMULATE"}
    raw_action = (parsed.get("action") or "").upper().strip()
    if raw_action not in _allowed:
        if "BUY" in raw_action:
            parsed["action"] = "BUY NOW"
        elif any(w in raw_action for w in ("WAIT", "PULL", "HOLD", "WATCH")):
            parsed["action"] = "WAIT FOR PULLBACK"
        elif any(w in raw_action for w in ("AVOID", "SELL", "REDUCE")):
            parsed["action"] = "AVOID"
        else:
            parsed["action"] = "WAIT FOR PULLBACK"
        print(f"  NOTE: normalised action '{raw_action}' → '{parsed['action']}' for {ticker}")

    # Hard Micha floor: very weak technicals override bullish actions
    if micha_score <= 2 and parsed.get("action") in ("BUY NOW", "ACCUMULATE"):
        parsed["action"] = "AVOID"
        print(f"  NOTE: Micha {micha_score}/12 ≤ 2 — overriding action to AVOID for {ticker}")
    elif micha_score <= 4 and parsed.get("action") == "BUY NOW":
        parsed["action"] = "ACCUMULATE"
        print(f"  NOTE: Micha {micha_score}/12 ≤ 4 — downgrading BUY NOW to ACCUMULATE for {ticker}")

    # Contradiction check: action and short_term must point the same direction
    _bullish_action = parsed.get("action") in ("BUY NOW", "ACCUMULATE")
    _bearish_words  = ("wait", "pullback", "caution", "weakness", "avoid", "deteriorat", "concern")
    _bullish_words  = ("buy", "accumulate", "opportunit", "strong", "upside")
    _short = (parsed.get("short_term") or "").lower()
    _contradiction = (
        (_bullish_action and any(w in _short for w in _bearish_words)) or
        (not _bullish_action and all(w not in _short for w in _bearish_words) and
         any(w in _short for w in _bullish_words))
    )
    if _contradiction:
        print(f"  NOTE: action/short_term contradiction detected for {ticker} — retrying once")
        _fix_prompt = (
            f"Your previous response had action='{parsed['action']}' but short_term contained "
            f"contradictory language. Rewrite ONLY the short_term field so it is consistent "
            f"with action='{parsed['action']}'. Return ONLY valid JSON with all 6 original "
            f"fields, keeping everything else identical except short_term."
        )
        try:
            _retry = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "user",      "content": prompt},
                    {"role": "assistant", "content": raw},
                    {"role": "user",      "content": _fix_prompt},
                ],
                max_tokens=600,
                temperature=0,
            )
            _retry_raw = _retry.choices[0].message.content.strip()
            if _retry_raw.startswith("```"):
                _retry_raw = _retry_raw.split("```")[1]
                if _retry_raw.startswith("json"):
                    _retry_raw = _retry_raw[4:]
                _retry_raw = _retry_raw.strip()
            _retry_parsed = json.loads(_retry_raw)
            parsed["short_term"] = _retry_parsed.get("short_term", parsed["short_term"])
        except Exception as e:
            print(f"  WARNING: contradiction retry failed for {ticker}: {e}")

    return parsed


def analyze_cycle_and_zones(ticker, cycle_stage, price_levels, buy_zone, criteria):
    """Write 2 sentences of prose around code-computed cycle stage and buy zone.
    All dollar amounts are locked in the prompt — the AI only provides framing."""

    cross = price_levels["golden_cross_days_ago"]
    cross_str = f"{cross} trading days ago" if cross is not None else "not within last 50 days"

    facts = f"""Computed facts for {ticker}:
- Current price: ${price_levels['price_now']:.2f}
- SMA50: ${price_levels['sma50']:.2f} (price is {price_levels['price_vs_sma50_pct']:+.1f}% vs SMA50)
- SMA150: ${price_levels['sma150']:.2f} (price is {price_levels['price_vs_sma150_pct']:+.1f}% vs SMA150)
- Recent 3-month low (support floor): ${price_levels['recent_3m_low']:.2f}
- 52-week low: {f"${price_levels['week_52_low']:.2f}" if price_levels['week_52_low'] is not None else "N/A (insufficient history)"}
- Golden cross occurred: {cross_str}
- Higher highs & higher lows: {criteria.get("11_higher_highs_lows", False)}
- Code-computed cycle stage: {cycle_stage}
- Computed buy zone: ${buy_zone['low']:.2f} – ${buy_zone['high']:.2f} (floor support: ${buy_zone['floor']:.2f})"""

    prompt = f"""{facts}

Write exactly two sentences:
1. Explain in one sentence WHY this stock is classified as {cycle_stage} in its trend cycle, citing the specific numbers above.
2. Describe the buy zone (${buy_zone['low']:.2f}–${buy_zone['high']:.2f}) in one sentence, naming which price level anchors the lower bound and where the floor support sits.

DO NOT invent any prices. Use only the numbers in the facts block above.

Respond ONLY with valid JSON:
{{
  "cycle_stage_reasoning": "one sentence",
  "buy_zone_narrative": "one sentence"
}}"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
        temperature=0.2
    )

    raw = response.choices[0].message.content
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        print(f"  WARNING: could not parse cycle/zone response for {ticker}")
        return {}

    return {
        "cycle_stage_reasoning": parsed.get("cycle_stage_reasoning", ""),
        "buy_zone_narrative":    parsed.get("buy_zone_narrative", ""),
    }


def propose_diversifiers(portfolio_sectors, target_sectors, current_holdings, n=5):
    """Ask the AI to propose real stock tickers from sectors the portfolio lacks."""

    prompt = f"""A stock portfolio is heavily concentrated in these sectors:
{', '.join(portfolio_sectors)}

The portfolio ALREADY HOLDS these stocks - do NOT suggest any of them:
{', '.join(current_holdings)}

To improve diversification, suggest {n} real, well-known, large-cap US-listed stocks
from these UNDERREPRESENTED sectors: {', '.join(target_sectors)}.

Rules:
- Only suggest real, currently-listed companies with well-known ticker symbols.
- Do NOT suggest any stock already held (listed above).
- Prefer established, high-quality companies (this will be verified against real data).
- Spread suggestions across the target sectors, don't cluster in one.
- Do NOT suggest any technology companies.

Respond ONLY with valid JSON in this format:
{{
  "candidates": [
    {{"ticker": "XXX", "company": "name", "sector": "sector", "why": "one sentence"}}
  ]
}}"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000,
        temperature=0.2
    )

    raw = response.choices[0].message.content
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        print("  WARNING: could not parse diversifier suggestions")
        return []

    # Layer 2: filter out any holdings even if the AI ignored the instruction
    candidates = parsed["candidates"]
    filtered = [c for c in candidates if c["ticker"].upper() not in
                [h.upper() for h in current_holdings]]

    return filtered

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000,
        temperature=0.2
    )

    raw = response.choices[0].message.content
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        print("  WARNING: could not parse diversifier suggestions")
        return []

    return parsed["candidates"]




def _get_market_snapshot():
    """Fetch latest close and daily change for S&P 500, NASDAQ, and Dow."""
    import yfinance as yf
    indices = {"S&P 500": "^GSPC", "NASDAQ": "^IXIC", "Dow Jones": "^DJI"}
    lines = []
    for label, symbol in indices.items():
        try:
            hist = yf.Ticker(symbol).history(period="5d")
            hist = hist.dropna(subset=["Close"])
            if len(hist) >= 2:
                prev_close = hist["Close"].iloc[-2]
                last_close = hist["Close"].iloc[-1]
                chg = last_close - prev_close
                pct = (chg / prev_close) * 100
                sign = "+" if chg >= 0 else ""
                lines.append(f"{label}: {last_close:,.2f} ({sign}{pct:.2f}%)")
        except Exception:
            pass
    return "\n".join(lines) if lines else "Market data unavailable."


def write_newspaper(portfolio_results, suggestions, watchlist_results=None):
    """Turn all analysis results into a readable daily newspaper."""
    from datetime import datetime
    today = datetime.now()
    date_str = today.strftime("%A, %B %d, %Y")

    market_snapshot = _get_market_snapshot()

    _CRIT_NAMES = {
        "1_price_above_sma150": "Price>SMA150",
        "2_sma150_slope_positive": "SMA150 rising",
        "3_price_above_sma50": "Price>SMA50",
        "4_sma50_above_sma150": "SMA50>SMA150",
        "5_golden_cross_recent": "Golden cross",
        "6_atr_shock_recent": "ATR shock",
        "7_breakout_quality": "Breakout",
        "8_retest_quality": "Retest",
        "9_volume_expansion": "Vol expansion",
        "10_volume_dryup_before": "Vol dry-up",
        "11_higher_highs_lows": "Higher H&L",
        "12_rs_vs_sp500": "RS vs S&P",
    }

    def _crit_summary(r):
        crit = r.get("micha_criteria") or {}
        passing = [_CRIT_NAMES.get(k, k) for k, v in crit.items() if v]
        failing = [_CRIT_NAMES.get(k, k) for k, v in crit.items() if not v]
        return f"passes: {', '.join(passing) or 'none'}. fails: {', '.join(failing) or 'none'}"

    # build a compact data summary for the AI to write from
    lines = ["PORTFOLIO:"]
    for r in portfolio_results:
        v = r["verdict"] or {}
        lines.append(
            f"- {r['ticker']} ({r['name']}): Micha {r['micha_score']}/12, "
            f"Peter {r['peter_score']}/10, Action: {v.get('action','?')}. "
            f"Short-term: {v.get('short_term','')}. "
            f"Technicals: {_crit_summary(r)}. "
            f"Fundamentals: {r['peter_summary']}"
        )

    lines.append("\nDIVERSIFIER SUGGESTIONS (new sectors):")
    for r in suggestions:
        v = r["verdict"] or {}
        lines.append(
            f"- {r['ticker']} ({r['name']}, {r['sector']}): "
            f"Micha {r['micha_score']}/12, Peter {r['peter_score']}/10, "
            f"Action: {v.get('action','?')}. Why: {v.get('long_term','')}"
        )

    if watchlist_results:
        lines.append("\nWATCHLIST (under consideration, not yet held):")
        for r in watchlist_results:
            v = r["verdict"] or {}
            lines.append(
                f"- {r['ticker']} ({r['name']}): Micha {r['micha_score']}/12, "
                f"Peter {r['peter_score']}/10, Action: {v.get('action','?')}."
            )

    data_summary = "\n".join(lines)

    prompt = f"""You are writing a daily stock newspaper for an investor.
Today is {date_str}.

Start with a 2-3 sentence market opening that mentions today's day of the week and
references the real index moves below. Be specific — mention the actual numbers.
Then cover the portfolio and suggestions as described.

MARKET SNAPSHOT (use these exact numbers, do not invent others):
{market_snapshot}

Structure:
1. Market opening — mention the day, the index moves, and the overall tone.
2. PORTFOLIO section: a brief note on each holding — its technical/fundamental
   standing and what to do. Group similar situations if helpful.
3. SUGGESTIONS section: present the diversifier ideas and why they'd strengthen
   a tech-heavy portfolio.
4. A one-line bottom-line takeaway.

Keep it concise and readable — daily brief, not an essay. Use the real scores
and actions. Do not invent any numbers beyond what is given above.
End with a brief reminder that this is analysis, not financial advice.

PORTFOLIO DATA:
{data_summary}"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
        temperature=0.2
    )

    return response.choices[0].message.content




# --- test it ---
if __name__ == "__main__":
    from data import get_price_history

    ticker = "ASML"
    data = get_price_history(ticker)
    print(f"Asking AI to judge breakout & retest for {ticker}...\n")
    result = judge_breakout_and_retest(ticker, data)

    print(f"Criterion 7 (breakout): {'PASS' if result['7_breakout_quality'] else 'FAIL'}")
    print(f"  reason: {result['_reasons']['7']}")
    print(f"Criterion 8 (retest):   {'PASS' if result['8_retest_quality'] else 'FAIL'}")
    print(f"  reason: {result['_reasons']['8']}")