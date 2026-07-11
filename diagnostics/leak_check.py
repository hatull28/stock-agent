"""
Adversarial leak test for the blind_profiler anonymization.

For each PORTFOLIO ticker, feeds the anonymized 40-day profile to DeepSeek N=5 times
and asks it to identify the equity. Also runs a control with the original identified
prompt (ticker + calendar dates + absolute prices).

Usage:
    python diagnostics/leak_check.py

Output: per-ticker hit rates (blind and control) plus aggregate. Does not render a
pass/fail — you read the numbers and decide. Blind-chance baseline is ~37.5% (top-3
guesses from an 8-ticker universe).
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import truststore
truststore.inject_into_ssl()
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from config import PORTFOLIO
from data import get_price_history
from blind_profiler import build_blind_profile, format_profile_table
from ai_layer import client, MODEL, summarize_recent_action

N = 5  # identification attempts per ticker

_BLIND_PROMPT = """\
Below is 40 days of indexed OHLC and relative volume data for an anonymous US-listed equity.

Encoding:
- Day 1 Close = 100.00. All O/H/L/C values are percentages of that anchor.
- V_ratio = each day's volume divided by the mean volume over the 40-day window.

{table}

Name the most likely ticker symbol for this equity. Give your top 3 guesses ranked by
confidence (1 = most likely). If you genuinely cannot identify it, use UNKNOWN.
Do not hedge — commit to your best guesses.

Respond ONLY with valid JSON:
{{"guesses": ["TICKER1", "TICKER2", "TICKER3"]}}"""

_CONTROL_PROMPT = """\
Below is 40 days of raw OHLCV data for {ticker}.

{table}

Name the most likely ticker symbol. Give your top 3 guesses ranked by confidence.
Respond ONLY with valid JSON:
{{"guesses": ["TICKER1", "TICKER2", "TICKER3"]}}"""


def _parse_guesses(raw):
    """Extract the guesses list from a model response. Returns [] on parse failure."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    try:
        parsed = json.loads(cleaned)
        return [g.upper() for g in parsed.get("guesses", [])]
    except (json.JSONDecodeError, AttributeError):
        return []


def run_identification(prompt, correct_ticker, n=N):
    """
    Run the identification prompt n times.
    Returns (hit_count, responses) where hit_count is how many runs named the correct ticker
    in the top 3, and responses is the list of raw guess lists for inspection.
    """
    hits = 0
    responses = []
    for _ in range(n):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=120,
                temperature=0.2,
            )
            raw = resp.choices[0].message.content
            guesses = _parse_guesses(raw)
            responses.append(guesses)
            if correct_ticker.upper() in guesses:
                hits += 1
        except Exception as e:
            print(f"      [warn] API error: {e}")
            responses.append([])
    return hits, responses


def main():
    blind_results   = {}   # ticker -> hit count
    control_results = {}   # ticker -> hit count
    blind_responses   = {}
    control_responses = {}

    print("=" * 64)
    print("LEAK CHECK — Criteria 7/8 Anonymizer Audit")
    print("=" * 64)
    print(f"Tickers : {PORTFOLIO}")
    print(f"Model   : {MODEL}")
    print(f"Runs/ticker: {N}   |   Blind-chance baseline: ~{3/8*100:.1f}% (top-3, 8 tickers)")
    print()

    for ticker in PORTFOLIO:
        print(f"  {ticker}")
        data = get_price_history(ticker)

        # --- blind mode ---
        profile = build_blind_profile(data)
        table_blind = format_profile_table(profile["rows"])
        blind_prompt = _BLIND_PROMPT.format(table=table_blind)

        print(f"    blind  : ", end="", flush=True)
        b_hits, b_resp = run_identification(blind_prompt, ticker)
        blind_results[ticker] = b_hits
        blind_responses[ticker] = b_resp
        print(f"{b_hits}/{N}  guesses: {b_resp}")

        # --- control mode ---
        table_control = summarize_recent_action(data)
        control_prompt = _CONTROL_PROMPT.format(ticker=ticker, table=table_control)

        print(f"    control: ", end="", flush=True)
        c_hits, c_resp = run_identification(control_prompt, ticker)
        control_results[ticker] = c_hits
        control_responses[ticker] = c_resp
        print(f"{c_hits}/{N}  guesses: {c_resp}")
        print()

    # --- summary table ---
    print("=" * 64)
    print("RESULTS")
    print("=" * 64)
    header = f"{'Ticker':<8}  {'Blind':>8}  {'Blind%':>8}  {'Control':>9}  {'Control%':>9}"
    print(header)
    print("-" * len(header))
    for ticker in PORTFOLIO:
        b = blind_results[ticker]
        c = control_results[ticker]
        flag = "  <-- LEAKS" if b / N > 3 / 8 else ""
        print(f"{ticker:<8}  {b}/{N}{'':>5}  {b/N*100:>6.1f}%  {c}/{N}{'':>6}  {c/N*100:>7.1f}%{flag}")

    total_blind   = sum(blind_results.values())
    total_control = sum(control_results.values())
    total_runs    = N * len(PORTFOLIO)
    print()
    print(f"Aggregate blind hit rate  : {total_blind}/{total_runs} = {total_blind/total_runs*100:.1f}%")
    print(f"Aggregate control hit rate: {total_control}/{total_runs} = {total_control/total_runs*100:.1f}%")
    print()
    print("Blind-chance baseline: ~37.5%  (3 guesses from 8-ticker universe)")
    print("'<-- LEAKS' = ticker hit rate exceeded blind chance in this run.")
    print()

    # --- per-ticker leak hypotheses ---
    leakers = [t for t in PORTFOLIO if blind_results[t] / N > 3 / 8]
    if leakers:
        print("Leaking tickers — hypotheses:")
        for t in leakers:
            rate = blind_results[t] / N * 100
            print(f"  {t} ({rate:.0f}%): review its V_ratio pattern — an outsized spike "
                  f"(earnings, news event) may fingerprint it even in relative form. "
                  f"Also check whether its indexed price path sits in a distinctive range "
                  f"not shared by other portfolio names.")
        print()
        print("Next step: inspect the raw guesses above for each leaker to understand "
              "whether the model is pattern-matching price shape, volume, or both.")
    else:
        print("No ticker exceeded blind-chance threshold in this run.")
        print("Interpret with caution: N=5 is a small sample; re-run if you want higher confidence.")


if __name__ == "__main__":
    main()
