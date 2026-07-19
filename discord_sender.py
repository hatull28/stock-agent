import hashlib
import os
import requests
from dotenv import load_dotenv

load_dotenv()


def action_emoji(action):
    """Pick an emoji for each action type."""
    if not action:
        return "⚪"
    a = action.upper()
    if "BUY" in a or "ACCUMULATE" in a:
        return "🟢"
    if "WAIT" in a:
        return "🟡"
    if "AVOID" in a:
        return "🔴"
    return "⚪"


def score_bar(score, out_of):
    """Make a little visual bar like ███░░ for a score."""
    filled = round((score / out_of) * 5)
    return "█" * filled + "░" * (5 - filled)


def mood_color(portfolio_results):
    """Overall card color based on how many stocks are 'go'."""
    greens = sum(1 for r in portfolio_results
                 if r["verdict"] and ("BUY" in r["verdict"]["action"].upper()
                 or "ACCUMULATE" in r["verdict"]["action"].upper()))
    ratio = greens / max(len(portfolio_results), 1)
    if ratio >= 0.5:
        return 0x2ecc71   # green
    if ratio >= 0.25:
        return 0xf1c40f   # amber
    return 0xe74c3c       # red


_ACTION_SHORT = {
    "BUY NOW":          "BUY",
    "WAIT FOR PULLBACK": "WAIT",
    "ACCUMULATE":       "ACCU",
    "AVOID":            "AVOID",
}


def compute_run_digest(results):
    """SHA-256 fingerprint of sorted ticker:profile_hash pairs, first 12 hex chars.

    This is the canonical digest function — the exact bytes that end up in the
    Discord embed footer. Import and call this (do not reimplement) in any tool
    that verifies the ledger against the witness.
    """
    digest_src = "|".join(
        f"{r['ticker']}:{r.get('profile_hash', '')}"
        for r in sorted(results, key=lambda x: x["ticker"])
    )
    return hashlib.sha256(digest_src.encode()).hexdigest()[:12]


def send_briefing(portfolio_results, suggestions, report_url=None, run_ts=None):
    """Send the daily briefing as a rich Discord embed.

    run_ts: ISO 8601 UTC string from the ledger (e.g. "2026-07-11T08:23:41Z").
    If None, falls back to the current UTC time. Used in the footer as an
    external timestamp that Discord independently records.
    """
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

    def _price_str(r):
        pl = r.get("price_levels") or {}
        price  = pl.get("price_now")
        change = pl.get("price_change")
        pct    = pl.get("price_change_pct")
        if price is None or change is None:
            return ""
        arrow = "▲" if change >= 0 else "▼"
        sign  = "+" if change >= 0 else ""
        return f"  `${price:,.2f} {sign}{change:.2f} ({sign}{pct:.2f}%) {arrow}`"

    # build the portfolio section text
    portfolio_lines = []
    for r in portfolio_results:
        action = r["verdict"]["action"] if r["verdict"] else "?"
        emoji = action_emoji(action)
        micha_bar = score_bar(r["micha_score"], 12)
        peter_bar = score_bar(r["peter_score"] or 0, 10)
        badge = _ACTION_SHORT.get(action, action[:4])
        portfolio_lines.append(
            f"{emoji} **{r['ticker']}**  "
            f"T:`{micha_bar}` {r['micha_score']}/12  "
            f"F:`{peter_bar}` {r['peter_score']}/10"
            f"{_price_str(r)}  [{badge}]"
        )
    portfolio_text = "\n".join(portfolio_lines)

    # build the suggestions section
    suggestion_lines = []
    for r in suggestions:
        action = r["verdict"]["action"] if r["verdict"] else "?"
        emoji = action_emoji(action)
        badge = _ACTION_SHORT.get(action, action[:4])
        suggestion_lines.append(
            f"{emoji} **{r['ticker']}** ({r['sector']})  "
            f"T: {r['micha_score']}/12  F: {r['peter_score']}/10"
            f"{_price_str(r)}  [{badge}]"
        )
    suggestion_text = "\n".join(suggestion_lines)

    # run digest — fingerprints portfolio + suggestions (the set this function receives).
    # watchlist is not passed here and therefore not covered by the digest.
    run_digest = compute_run_digest(portfolio_results + suggestions)

    from datetime import datetime, timezone
    _ts = run_ts or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")

    # assemble the embed
    embed = {
        "title": "📊 Daily Stock Briefing",
        "description": "Technical (T) = Micha /12 · Fundamental (F) = Peter Lynch /10",
        "color": mood_color(portfolio_results),
        "fields": [
            {"name": "💼 Portfolio", "value": portfolio_text, "inline": False},
            {"name": "✨ Diversifier Ideas (new sectors)",
             "value": suggestion_text, "inline": False},
            {"name": "📄 Full Report",
             "value": "[Open The Wire →](https://hatull28.github.io/stock-agent/daily_report.html)",
             "inline": False},
        ],
        "footer": {"text": f"Analysis, not financial advice · {_ts} · digest:{run_digest}"},
    }

    if report_url:
        embed["fields"].append(
            {"name": "📄 Full Report", "value": f"[Open detailed report]({report_url})",
             "inline": False})

    payload = {"embeds": [embed]}
    response = requests.post(webhook_url, json=payload)
    return response.status_code == 204