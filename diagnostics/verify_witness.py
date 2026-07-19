"""
verify_witness.py — Verify the prediction ledger against the Discord witness.

The Discord embed footer carries a run timestamp and a 12-char SHA-256 digest,
posted to a server we do not control. If research_data.json were edited after
the fact, recomputing the digest from the ledger would no longer match what
Discord recorded.

ERA DETECTION
The digest function expanded in one commit: before, it covered portfolio +
suggestions (12 entries); after, it covers all 18 (portfolio + suggestions +
watchlist). The verifier detects which era a run belongs to by checking whether
any entry for that run carries a "source" field. The "source" field was added
in the same commit that expanded the digest — so "has source" <-> "new era"
is a genuine causal invariant, not a coincidence.

  New-era run  (source present): digest covers all entries for the run_ts.
  Legacy run   (no source)     : digest covered portfolio + suggestions only.
                                 The split uses config.WATCHLIST to separate
                                 suggestions from watchlist — this may produce
                                 false alarms if the watchlist has changed since.

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


def _print_pairs_and_string(digest_entries):
    """Print sorted ticker:hash table and the full concatenated string."""
    sorted_pairs = sorted(digest_entries, key=lambda x: x["ticker"])
    print("Sorted ticker:hash pairs assembled for digest:")
    for e in sorted_pairs:
        h = e.get("profile_hash") or ""
        print(f"  {e['ticker']:<6} : {h}")
    print()
    print("Full string hashed:")
    for e in sorted_pairs:
        print(f"  {e['ticker']}:{e.get('profile_hash', '')}")
    print()
    return sorted_pairs


def main():
    print("=" * 70)
    print(f"WITNESS VERIFICATION -- {RUN_TS}")
    print("=" * 70)
    print()

    # Import the canonical digest function -- not a reimplementation.
    from discord_sender import compute_run_digest

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
                print(f"WARNING: line {lineno} is not valid JSON ({e}) -- skipping")

    run_entries = [e for e in all_entries if e.get("run_ts") == RUN_TS]

    if not run_entries:
        available = sorted({e.get("run_ts", "?") for e in all_entries})
        print(f"ERROR: no entries found for run_ts={RUN_TS!r}")
        print(f"  Available run timestamps in ledger ({len(available)}):")
        for ts in available:
            count = sum(1 for e in all_entries if e.get("run_ts") == ts)
            print(f"    {ts}  ({count} entries)")
        sys.exit(1)

    # ── Era detection ─────────────────────────────────────────────────────────
    # "source" field was added in the same commit that expanded digest coverage
    # from 12 entries (portfolio+suggestions) to all 18 (all sources).
    has_source = any("source" in e for e in run_entries)

    if has_source:
        # ── New-era path: source field present; digest covers all entries ──────
        portfolio   = [e for e in run_entries if e.get("source") == "portfolio"]
        watchlist   = [e for e in run_entries if e.get("source") == "watchlist"]
        suggestions = [e for e in run_entries if e.get("source") == "suggestion"]
        other       = [e for e in run_entries if e.get("source") not in
                       ("portfolio", "watchlist", "suggestion")]

        digest_entries = portfolio + watchlist + suggestions + other
        era_label = "new (source field present -- digest covers all entries)"
        coverage_note = "ALL entries for this run are covered by the digest."

        print(f"Era detected      : {era_label}")
        print(f"Ledger entries    : {len(run_entries)}")
        print(f"  portfolio       : {len(portfolio):2d}  "
              f"[{' '.join(sorted(e['ticker'] for e in portfolio))}]")
        print(f"  watchlist       : {len(watchlist):2d}  "
              f"[{' '.join(sorted(e['ticker'] for e in watchlist))}]")
        print(f"  suggestion      : {len(suggestions):2d}  "
              f"[{' '.join(sorted(e['ticker'] for e in suggestions))}]")
        if other:
            print(f"  unknown source  : {len(other):2d}  "
                  f"[{' '.join(sorted(e['ticker'] for e in other))}]")
        print(f"  {coverage_note}")

    else:
        # ── Legacy path: no source field; digest covered only portfolio+suggestions
        print("Era detected      : legacy (no source field on any entry)")
        print()
        print("  WARNING: This run predates the source field. The split between")
        print("  suggestions and watchlist is reconstructed using the current")
        print("  config.WATCHLIST. If any ticker has been added to or removed from")
        print("  the watchlist since this run, the reconstruction will be wrong and")
        print("  a FAIL here does NOT necessarily mean tampering.")
        print()

        from config import WATCHLIST
        watchlist_set = set(WATCHLIST)

        portfolio   = [e for e in run_entries if e.get("held") is True]
        non_held    = [e for e in run_entries if e.get("held") is not True]
        watchlist   = [e for e in non_held if e["ticker"] in watchlist_set]
        suggestions = [e for e in non_held if e["ticker"] not in watchlist_set]

        digest_entries = portfolio + suggestions   # watchlist was NOT in digest

        print(f"Ledger entries    : {len(run_entries)}")
        print(f"  portfolio       : {len(portfolio):2d}  "
              f"[{' '.join(sorted(e['ticker'] for e in portfolio))}]")
        print(f"  suggestion      : {len(suggestions):2d}  "
              f"[{' '.join(sorted(e['ticker'] for e in suggestions))}]")
        print(f"  watchlist excl. : {len(watchlist):2d}  "
              f"[{' '.join(sorted(e['ticker'] for e in watchlist))}]")
        print(f"  (watchlist was NOT covered by the digest for legacy runs)")

    print()

    if not digest_entries:
        print("ERROR: no digest entries assembled -- cannot compute digest.")
        sys.exit(1)

    _print_pairs_and_string(digest_entries)

    # Compute using the canonical function imported from discord_sender.
    recomputed = compute_run_digest(digest_entries)

    print(f"Recomputed digest : {recomputed}")
    print(f"Expected digest   : {EXPECTED_DIGEST}")
    print()

    if recomputed == EXPECTED_DIGEST:
        print("PASS -- ledger matches Discord witness. No tampering detected.")
    else:
        print("FAIL -- digest mismatch. Diagnosing...")
        print()
        if not has_source:
            print("  This is a LEGACY run. Most likely cause: the WATCHLIST config")
            print("  has changed since this run, so the suggestion/watchlist split is")
            print("  wrong. Check what the watchlist looked like at run time (git log)")
            print("  before concluding there was tampering.")
            print()
        print("  Other likely causes (new-era or after confirming WATCHLIST unchanged):")
        print(f"  1. Entry count: {len(digest_entries)} entries used here. If the digest")
        print("     was computed from a different count, the hash will not match.")
        print("  2. profile_hash changed: one ticker's hash in the ledger differs from")
        print("     what was hashed at runtime. Compare to git history:")
        print("       git log --all --oneline -- research_data.json")
        print("       git show <commit>:research_data.json | grep <ticker>")
        print("  3. Formatting drift: separator or sort order changed in")
        print("     compute_run_digest(). The full string above is exactly what was")
        print("     hashed -- compare to discord_sender.py.")
        sys.exit(1)


if __name__ == "__main__":
    main()
