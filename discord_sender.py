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


def send_briefing(portfolio_results, suggestions, report_url=None):
    """Send the daily briefing as a rich Discord embed."""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

    # build the portfolio section text
    portfolio_lines = []
    for r in portfolio_results:
        action = r["verdict"]["action"] if r["verdict"] else "?"
        emoji = action_emoji(action)
        micha_bar = score_bar(r["micha_score"], 12)
        peter_bar = score_bar(r["peter_score"] or 0, 10)
        portfolio_lines.append(
            f"{emoji} **{r['ticker']}**  "
            f"T:`{micha_bar}` {r['micha_score']}/12  "
            f"F:`{peter_bar}` {r['peter_score']}/10"
        )
    portfolio_text = "\n".join(portfolio_lines)

    # build the suggestions section
    suggestion_lines = []
    for r in suggestions:
        action = r["verdict"]["action"] if r["verdict"] else "?"
        emoji = action_emoji(action)
        suggestion_lines.append(
            f"{emoji} **{r['ticker']}** ({r['sector']})  "
            f"T: {r['micha_score']}/12  F: {r['peter_score']}/10"
        )
    suggestion_text = "\n".join(suggestion_lines)

    # assemble the embed
    embed = {
        "title": "📊 Daily Stock Briefing",
        "description": "Technical (T) = Micha /12 · Fundamental (F) = Peter Lynch /10",
        "color": mood_color(portfolio_results),
        "fields": [
            {"name": "💼 Portfolio", "value": portfolio_text, "inline": False},
            {"name": "✨ Diversifier Ideas (new sectors)",
             "value": suggestion_text, "inline": False},
        ],
        "footer": {"text": "Analysis, not financial advice"},
    }

    if report_url:
        embed["fields"].append(
            {"name": "📄 Full Report", "value": f"[Open detailed report]({report_url})",
             "inline": False})

    payload = {"embeds": [embed]}
    response = requests.post(webhook_url, json=payload)
    return response.status_code == 204