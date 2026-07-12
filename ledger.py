import json
from datetime import datetime, timezone

LEDGER_FILE = "research_data.json"


def _json_default(obj):
    """Coerce numpy scalar types that json.dumps can't handle."""
    try:
        import numpy as np
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)
    except ImportError:
        pass
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


def _lynch_category(r):
    """Mirror the lynchSticker() JS function in report_builder.py:1921-1931."""
    rg, eg = r.get("revenue_growth"), r.get("earnings_growth")
    mc, peg, fcf = r.get("market_cap"), r.get("peg_ratio"), r.get("free_cash_flow")
    if peg is not None and peg < 0.8 and rg is not None and rg > 0:
        return "Hidden Gem"
    if (rg is not None and rg > 0.30) or (eg is not None and eg > 0.30):
        return "Ultra Grower"
    if rg is not None and rg > 0.15:
        return "Fast Grower"
    if rg is not None and rg > 0.05 and mc is not None and mc > 50e9:
        return "Stalwart"
    if rg is not None and rg >= 0:
        return "Slow Grower"
    if fcf is not None and fcf > 0:
        return "Turnaround?"
    return "Tread Carefully"


def append_run(results, run_ts=None):
    """Append one JSONL entry per ticker to the prediction ledger.

    Format: one complete JSON object per line (JSONL). Each call opens the file
    in append mode — no read, no rewrite, no dedup. If the process is killed
    mid-write the last line may be partial; all prior entries remain intact.

    Args:
        results: list of result dicts from analyze_stock() — portfolio + suggestions
        run_ts:  ISO 8601 UTC string e.g. "2026-07-11T08:23:41Z"; defaults to now

    Returns:
        run_ts: the timestamp actually used (pass to discord_sender for consistency)
    """
    if run_ts is None:
        run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    date_str = run_ts[:10]

    with open(LEDGER_FILE, "a", encoding="utf-8") as f:
        for r in results:
            verdict = r.get("verdict") or {}
            reasons = r.get("micha_reasons") or {}
            entry = {
                "run_ts":         run_ts,
                "date":           date_str,
                "ticker":         r["ticker"],
                "method":         "blind",
                "micha_score":    r["micha_score"],
                "micha_criteria": r.get("micha_criteria", {}),
                "micha_reason_7": reasons.get("7", ""),
                "micha_reason_8": reasons.get("8", ""),
                "profile_hash":   r.get("profile_hash"),
                "peter_score":    r.get("peter_score"),
                "peter_scores":   r.get("peter_scores", {}),
                "lynch_category": _lynch_category(r),
                "held":           r.get("_held", False),
                "action":         verdict.get("action"),
            }
            f.write(json.dumps(entry, ensure_ascii=False, default=_json_default) + "\n")

    return run_ts
