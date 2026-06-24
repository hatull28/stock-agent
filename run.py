import sys, truststore
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
truststore.inject_into_ssl()

from data import get_price_history
from fundamentals import get_fundamentals
from config import PORTFOLIO, BENCHMARK
from analysis import analyze_stock, fetch_etf_returns
from ai_layer import propose_diversifiers

TARGET_SECTORS = ["Healthcare", "Financials", "Energy",
                  "Consumer Discretionary", "Industrials"]


def run_daily_analysis():
    print("Fetching benchmark (S&P500)...")
    benchmark_data = get_price_history(BENCHMARK)

    print("Fetching sector ETF baselines...")
    etf_returns = fetch_etf_returns()

    # === PART A: analyze the portfolio ===
    print("\n=== ANALYZING PORTFOLIO ===")
    portfolio_results = []
    for ticker in PORTFOLIO:
        print(f"  analyzing {ticker}...")
        try:
            result = analyze_stock(ticker, benchmark_data, etf_returns)
            portfolio_results.append(result)
        except Exception as e:
            print(f"  ERROR on {ticker}: {e}")

    # === PART B: generate & analyze diversifier suggestions ===
    print("\n=== GENERATING SUGGESTIONS ===")
    candidates = propose_diversifiers(["Technology"], TARGET_SECTORS, PORTFOLIO)

    suggestion_results = []
    for c in candidates:
        ticker = c["ticker"]
        print(f"  analyzing candidate {ticker}...")
        try:
            # verify it has real data first
            f = get_fundamentals(ticker)
            if not f.get("market_cap"):
                print(f"    skipping {ticker} - no data")
                continue
            result = analyze_stock(ticker, benchmark_data, etf_returns)
            suggestion_results.append(result)
        except Exception as e:
            print(f"    ERROR on {ticker}: {e}")

    # === PART C: rank suggestions (quality first) ===
    # combined score = micha (0-12 -> scale to 10) + peter (0-10), average
    def combined(r):
        micha_scaled = (r["micha_score"] / 12) * 10
        peter = r["peter_score"] or 0
        return (micha_scaled + peter) / 2

    suggestion_results.sort(key=combined, reverse=True)
    top_suggestions = suggestion_results[:3]   # best 3

    return {
        "portfolio": portfolio_results,
        "suggestions": top_suggestions,
    }


# --- run it ---
if __name__ == "__main__":
    results = run_daily_analysis()

    print("\n" + "=" * 50)
    print("PORTFOLIO SUMMARY")
    print("=" * 50)
    for r in results["portfolio"]:
        action = r["verdict"]["action"] if r["verdict"] else "?"
        print(f"  {r['ticker']:6} Micha {r['micha_score']}/12  "
              f"Peter {r['peter_score']}/10  -> {action}")

    print("\n" + "=" * 50)
    print("TOP 3 DIVERSIFIER SUGGESTIONS")
    print("=" * 50)
    for r in results["suggestions"]:
        action = r["verdict"]["action"] if r["verdict"] else "?"
        print(f"  {r['ticker']:6} ({r['sector']:25}) "
              f"Micha {r['micha_score']}/12  Peter {r['peter_score']}/10  -> {action}"),
# === send to Discord ===
  # === generate the written briefing ===
    print("\n" + "=" * 50)
    print("WRITING BRIEFING & BUILDING REPORT...")
    print("=" * 50)
    from ai_layer import write_newspaper
    newspaper = write_newspaper(results["portfolio"], results["suggestions"])

    # === build the HTML report ===
    from report_builder import build_report
    report_path = build_report(results["portfolio"], results["suggestions"], newspaper)
    print(f"Report built: {report_path}")

    # === send summary to Discord ===
    from discord_sender import send_briefing
    ok = send_briefing(results["portfolio"], results["suggestions"])
    print("Sent to Discord!" if ok else "Discord send failed.")

    # === push report to git ===
    import subprocess, datetime
    date_str = datetime.date.today().strftime("%Y-%m-%d")
    subprocess.run(["git", "add", "daily_report.html"], check=True)
    subprocess.run(["git", "commit", "-m", f"Daily report update {date_str}"], check=True)
    subprocess.run(["git", "push"], check=True)
    print("Report pushed to git.")