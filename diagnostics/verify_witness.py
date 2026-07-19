"""
verify_witness.py — Verify the prediction ledger against the Discord witness.

The Discord embed footer carries a run timestamp and a 12-char SHA-256 digest,
posted to a server we do not control. The digest fingerprints the ledger entries
for that run. If research_data.json were edited after the fact, recomputing the
digest from the ledger would no longer match what Discord recorded.

COVERAGE NOTE: the digest covers portfolio + suggestion entries only. Watchlist
entries (held=false tickers that appear in WATCHLIST config) are excluded from
the digest because send_briefing() does not receive them. The tool prints which
tickers are covered and which are not, so a mismatch can be diagnosed precisely.

Hardcode RUN_TS and EXPECTED_DIGEST below, then run:
  python diagnostics/verify_witness.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json

# ── Test values — edit these to verify a different run ───────────────────────
RUN_TS          = "2026-07-19T08:08:37Z"
EXPECTED_DIGEST = "6538ddd7199a"
# ─────────────────────────────────────────────────────────────────────────────

LEDGER_FILE = "research_data.json"


def main():
    print("=" * 70)
    print(f"WITNESS VERIFICATION — {RUN_TS}")
    print("=" * 70)
    print()

    # Import the canonical digest function — not a reimplementation.
    from discord_sender import compute_run_digest

    # Import WATCHLIST to distinguish suggestions from watchlist in held=false entries.
    from config import WATCHLIST
    watchlist_set = set(WATCHLIST)

    # Read ledger.
    if not os.path.exists(LEDGER_FILE):
        print(f"ERROR: {LEDGER_FILE} not found. Run the agent at least once first.")
        sys.exit(1)

    all_entries = []
    with open(LEDGER_FILE, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                all_entries.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"WARNING: line {lineno} is not valid JSON ({e}) — skipping")

    run_entries = [e for e in all_entries if e.get("run_ts") == RUN_TS]

    if not run_entries:
        available = sorted({e.get("run_ts", "?") for e in all_entries})
        print(f"ERROR: no entries found for run_ts={RUN_TS!r}")
        print(f"  Available run timestamps in ledger ({len(available)}):")
        for ts in available:
            count = sum(1 for e in all_entries if e.get("run_ts") == ts)
            print(f"    {ts}  ({count} entries)")
        sys.exit(1)

    # Split into portfolio / watchlist / suggestions.
    portfolio   = [e for e in run_entries if e.get("held") is True]
    non_held    = [e for e in run_entries if e.get("held") is not True]
    watchlist   = [e for e in non_held if e["ticker"] in watchlist_set]
    suggestions = [e for e in non_held if e["ticker"] not in watchlist_set]

    port_tickers = sorted(e["ticker"] for e in portfolio)
    sugg_tickers = sorted(e["ticker"] for e in suggestions)
    wl_tickers   = sorted(e["ticker"] for e in watchlist)

    print(f"Ledger entries for this run_ts  : {len(run_entries)}")
    print(f"Portfolio entries  (held=true)  : {len(portfolio):2d}  [{' '.join(port_tickers)}]")
    print(f"Suggestion entries (held=false, not in WATCHLIST) : {len(suggestions):2d}  [{' '.join(sugg_tickers)}]")
    print(f"Watchlist excluded (held=false, in WATCHLIST)     : {len(watchlist):2d}  [{' '.join(wl_tickers)}]")
    print(f"  (note: watchlist is NOT covered by the Discord digest)")
    print()

    # Assemble the digest entries — same set send_briefing() received at runtime.
    digest_entries = portfolio + suggestions

    if not digest_entries:
        print("ERROR: no portfolio or suggestion entries found — cannot compute digest.")
        sys.exit(1)

    # Show the sorted ticker:hash pairs exactly as they enter the hash function.
    sorted_pairs = sorted(digest_entries, key=lambda x: x["ticker"])
    print("Sorted ticker:hash pairs assembled for digest:")
    for e in sorted_pairs:
        h = e.get("profile_hash") or ""
        print(f"  {e['ticker']:<6} : {h}")
    print()

    # Reconstruct the full string that gets hashed — same logic as compute_run_digest.
    digest_src = "|".join(
        f"{e['ticker']}:{e.get('profile_hash', '')}"
        for e in sorted_pairs
    )
    print("Full string hashed:")
    # Print in segments so it's readable without wrapping.
    for pair in digest_src.split("|"):
        print(f"  {pair}")
    print()

    # Compute using the canonical function imported from discord_sender.
    recomputed = compute_run_digest(digest_entries)

    print(f"Recomputed digest : {recomputed}")
    print(f"Expected digest   : {EXPECTED_DIGEST}")
    print()

    if recomputed == EXPECTED_DIGEST:
        print("PASS — ledger matches Discord witness. No tampering detected.")
    else:
        print("FAIL — digest mismatch. Diagnosing...")
        print()
        print("Likely causes (in order of probability):")
        print("  1. Entry count mismatch: digest was computed from a different set of tickers.")
        print(f"     Entries used here: {len(digest_entries)}  "
              f"({len(portfolio)} portfolio + {len(suggestions)} suggestions)")
        print("     If WATCHLIST changed since this run, suggestion/watchlist split may be wrong.")
        print()
        print("  2. profile_hash mismatch on a specific ticker:")
        print("     One ticker's blind profile may have been re-run and the ledger updated.")
        print("     Check each hash against any prior snapshot of the ledger.")
        print()
        print("  3. Formatting drift: separator or sort order changed in compute_run_digest().")
        print("     The full string above is exactly what was hashed — compare to discord_sender.py.")
        print()
        print("  4. Actual tampering: a ticker:hash pair was edited in research_data.json.")
        print("     Compare the hashes above to git history: git show HEAD:research_data.json")
        sys.exit(1)


if __name__ == "__main__":
    main()
