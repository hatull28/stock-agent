"""
report_builder.py
Builds a visual HTML "newspaper" from the daily analysis results.

Design: "The Wire" - a financial dispatch styled like a night-mode market
terminal crossed with an editorial broadsheet. Data is set as monospace "tape",
the AI briefing is the lead feature article, and action verdicts are the only
place green/amber/red appear, so the signals carry real meaning.

Usage (from run.py):
    from report_builder import build_report
    build_report(portfolio_results, suggestions, newspaper_text)
"""

from datetime import datetime
import html


# ---- small helpers -------------------------------------------------------

def _action_class(action):
    """Map an action string to a CSS class / signal color group."""
    if not action:
        return "neutral"
    a = action.upper()
    if "BUY" in a or "ACCUMULATE" in a:
        return "go"
    if "WAIT" in a:
        return "hold"
    if "AVOID" in a:
        return "stop"
    return "neutral"


def _bar(score, out_of):
    """Return a width percentage (0-100) for a score bar."""
    if score is None:
        return 0
    return round((score / out_of) * 100)


def _esc(text):
    """Escape any text that came from the AI so it can't break the HTML."""
    if text is None:
        return ""
    return html.escape(str(text))


def _format_briefing(text):
    """Turn the AI's markdown-ish briefing into simple HTML paragraphs.
    We keep this deliberately light: split on blank lines, strip stray
    markdown markers, and wrap each block in a paragraph."""
    if not text:
        return "<p>No briefing generated today.</p>"

    # normalize line endings and split into blocks
    blocks = [b.strip() for b in text.replace("\r", "").split("\n") if b.strip()]
    out = []
    for b in blocks:
        # strip common markdown leftovers so they don't show as literal symbols
        clean = b.lstrip("#").lstrip("*").strip()
        clean = clean.replace("**", "")
        # headings (short lines that look like section titles)
        if clean.isupper() and len(clean) < 40:
            out.append(f'<h3 class="lead-sub">{_esc(clean)}</h3>')
        else:
            out.append(f"<p>{_esc(clean)}</p>")
    return "\n".join(out)


# ---- stock entry rendering ----------------------------------------------

def _stock_entry(r, featured_reasons=True):
    """Render one stock as a 'dispatch' entry."""
    verdict = r.get("verdict") or {}
    action = verdict.get("action", "—")
    cls = _action_class(action)

    micha = r.get("micha_score", 0)
    peter = r.get("peter_score") or 0

    reasons_html = ""
    if featured_reasons:
        reasons = r.get("micha_reasons") or {}
        short_term = verdict.get("short_term", "")
        long_term = verdict.get("long_term", "")
        strategy = verdict.get("accumulation_strategy", "")
        bits = []
        if verdict.get("micha_meaning"):
            bits.append(("Technical", verdict["micha_meaning"]))
        if verdict.get("peter_meaning"):
            bits.append(("Fundamental", verdict["peter_meaning"]))
        if short_term:
            bits.append(("Short term", short_term))
        if long_term:
            bits.append(("Long term", long_term))
        if strategy:
            bits.append(("Strategy", strategy))
        if reasons.get("7"):
            bits.append(("Breakout", reasons["7"]))
        if reasons.get("8"):
            bits.append(("Retest", reasons["8"]))
        if bits:
            rows = "\n".join(
                f'<div class="reason"><span class="reason-key">{_esc(k)}</span>'
                f'<span class="reason-val">{_esc(v)}</span></div>'
                for k, v in bits
            )
            reasons_html = f'<div class="reasons">{rows}</div>'

    sector = r.get("sector", "")
    sector_html = f'<span class="sector">{_esc(sector)}</span>' if sector else ""

    return f"""
    <article class="entry {cls}">
      <header class="entry-head">
        <div class="entry-id">
          <span class="ticker">{_esc(r.get('ticker',''))}</span>
          {sector_html}
        </div>
        <span class="tag tag-{cls}">{_esc(action)}</span>
      </header>
      <div class="entry-name">{_esc(r.get('name',''))}</div>
      <div class="meters">
        <div class="meter">
          <div class="meter-label">TECH <span class="meter-num">{micha}/12</span></div>
          <div class="meter-track"><div class="meter-fill" style="width:{_bar(micha,12)}%"></div></div>
        </div>
        <div class="meter">
          <div class="meter-label">FUND <span class="meter-num">{peter}/10</span></div>
          <div class="meter-track"><div class="meter-fill alt" style="width:{_bar(peter,10)}%"></div></div>
        </div>
      </div>
      {reasons_html}
    </article>
    """


# ---- main entry point ----------------------------------------------------

def build_report(portfolio_results, suggestions, newspaper_text,
                 out_path="daily_report.html"):
    """Build the full HTML report and write it to out_path."""

    now = datetime.now()
    date_long = now.strftime("%A, %B ") + str(now.day) + now.strftime(", %Y")
    time_str = now.strftime("%H:%M")

    # count the day's mood for the masthead readout
    go = sum(1 for r in portfolio_results
             if _action_class((r.get("verdict") or {}).get("action")) == "go")
    total = len(portfolio_results)

    portfolio_entries = "\n".join(_stock_entry(r) for r in portfolio_results)
    suggestion_entries = "\n".join(_stock_entry(r) for r in suggestions)
    briefing_html = _format_briefing(newspaper_text)

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Wire — Daily Stock Briefing</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=Spectral:ital,wght@0,400;0,600;1,400&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #0f1620;
    --panel: #161f2b;
    --panel-2: #1b2633;
    --ink: #e8eef5;
    --ink-dim: #8da0b5;
    --line: #263444;
    --amber: #f2b134;
    --go: #34d399;
    --hold: #f2b134;
    --stop: #f26d6d;
    --neutral: #6b7d92;
  }}
  * {{ box-sizing: border-box; }}
  html {{ scroll-behavior: smooth; }}
  body {{
    margin: 0;
    background: var(--bg);
    color: var(--ink);
    font-family: 'Spectral', Georgia, serif;
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
  }}
  .wrap {{ max-width: 1100px; margin: 0 auto; padding: 0 24px 80px; }}

  /* ---- masthead ---- */
  .masthead {{
    border-bottom: 2px solid var(--amber);
    padding: 40px 0 18px;
    margin-bottom: 8px;
  }}
  .eyebrow {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.32em;
    text-transform: uppercase;
    color: var(--amber);
    margin: 0 0 10px;
  }}
  .title {{
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700;
    font-size: clamp(42px, 8vw, 86px);
    letter-spacing: -0.03em;
    line-height: 0.92;
    margin: 0;
  }}
  .title .the {{ color: var(--ink-dim); font-weight: 400; }}
  .meta-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 18px;
    justify-content: space-between;
    align-items: baseline;
    margin-top: 16px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: var(--ink-dim);
    letter-spacing: 0.05em;
  }}
  .readout b {{ color: var(--ink); }}

  /* ---- section labels ---- */
  .section-label {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    letter-spacing: 0.28em;
    text-transform: uppercase;
    color: var(--ink-dim);
    margin: 54px 0 18px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--line);
    display: flex;
    justify-content: space-between;
  }}
  .section-label .count {{ color: var(--amber); }}

  /* ---- lead briefing ---- */
  .lead {{
    background: linear-gradient(180deg, var(--panel) 0%, var(--panel-2) 100%);
    border: 1px solid var(--line);
    border-left: 3px solid var(--amber);
    padding: 30px 34px;
    margin-top: 18px;
    border-radius: 2px;
  }}
  .lead p {{ margin: 0 0 14px; font-size: 17px; color: #d6e0eb; }}
  .lead p:first-of-type::first-letter {{
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700;
    font-size: 3.1em;
    float: left;
    line-height: 0.8;
    padding: 6px 12px 0 0;
    color: var(--amber);
  }}
  .lead-sub {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    letter-spacing: 0.2em;
    color: var(--amber);
    margin: 22px 0 10px;
  }}

  /* ---- entries grid ---- */
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(330px, 1fr));
    gap: 16px;
  }}
  .entry {{
    background: var(--panel);
    border: 1px solid var(--line);
    border-top: 2px solid var(--neutral);
    border-radius: 2px;
    padding: 18px 20px 20px;
    transition: transform .15s ease, border-color .15s ease;
  }}
  .entry:hover {{ transform: translateY(-2px); }}
  .entry.go {{ border-top-color: var(--go); }}
  .entry.hold {{ border-top-color: var(--hold); }}
  .entry.stop {{ border-top-color: var(--stop); }}
  .entry-head {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }}
  .entry-id {{ display: flex; flex-direction: column; gap: 3px; }}
  .ticker {{
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700;
    font-size: 26px;
    letter-spacing: -0.02em;
  }}
  .sector {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--ink-dim);
  }}
  .entry-name {{
    font-size: 13px;
    color: var(--ink-dim);
    margin: 2px 0 14px;
    font-style: italic;
  }}
  .tag {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
    padding: 5px 9px;
    border-radius: 2px;
    white-space: nowrap;
    text-align: right;
  }}
  .tag-go {{ background: rgba(52,211,153,.14); color: var(--go); border: 1px solid rgba(52,211,153,.3); }}
  .tag-hold {{ background: rgba(242,177,52,.14); color: var(--hold); border: 1px solid rgba(242,177,52,.3); }}
  .tag-stop {{ background: rgba(242,109,109,.14); color: var(--stop); border: 1px solid rgba(242,109,109,.3); }}
  .tag-neutral {{ background: rgba(107,125,146,.14); color: var(--neutral); border: 1px solid rgba(107,125,146,.3); }}

  /* ---- meters ---- */
  .meters {{ display: flex; flex-direction: column; gap: 10px; margin-bottom: 4px; }}
  .meter-label {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.12em;
    color: var(--ink-dim);
    display: flex;
    justify-content: space-between;
    margin-bottom: 4px;
  }}
  .meter-num {{ color: var(--ink); }}
  .meter-track {{
    height: 6px;
    background: var(--panel-2);
    border-radius: 3px;
    overflow: hidden;
  }}
  .meter-fill {{
    height: 100%;
    background: linear-gradient(90deg, #2b6cb0, #4299e1);
    border-radius: 3px;
  }}
  .meter-fill.alt {{ background: linear-gradient(90deg, #b7791f, var(--amber)); }}

  /* ---- reasons ---- */
  .reasons {{
    margin-top: 14px;
    padding-top: 14px;
    border-top: 1px dashed var(--line);
    display: flex;
    flex-direction: column;
    gap: 8px;
  }}
  .reason {{ display: grid; grid-template-columns: 78px 1fr; gap: 10px; }}
  .reason-key {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 9.5px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--amber);
    padding-top: 2px;
  }}
  .reason-val {{ font-size: 13px; color: #c4d1de; line-height: 1.5; }}

  /* ---- footer ---- */
  .foot {{
    margin-top: 64px;
    padding-top: 20px;
    border-top: 1px solid var(--line);
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: var(--ink-dim);
    letter-spacing: 0.06em;
    text-align: center;
  }}
  .foot .warn {{ color: var(--ink); }}

  @media (max-width: 560px) {{
    .grid {{ grid-template-columns: 1fr; }}
    .lead {{ padding: 22px 20px; }}
  }}
  @media (prefers-reduced-motion: reduce) {{
    .entry {{ transition: none; }}
  }}
</style>
</head>
<body>
  <div class="wrap">
    <header class="masthead">
      <p class="eyebrow">Market Dispatch · Automated Daily Edition</p>
      <h1 class="title"><span class="the">The</span> Wire</h1>
      <div class="meta-row">
        <span class="dateline">{_esc(date_long)} · {time_str}</span>
        <span class="readout">PORTFOLIO SIGNAL · <b>{go}/{total}</b> accumulate</span>
      </div>
    </header>

    <div class="section-label"><span>The Briefing</span><span class="count">lead</span></div>
    <div class="lead">
      {briefing_html}
    </div>

    <div class="section-label"><span>Portfolio Holdings</span><span class="count">{len(portfolio_results)} positions</span></div>
    <div class="grid">
      {portfolio_entries}
    </div>

    <div class="section-label"><span>Diversifier Dispatches</span><span class="count">new sectors</span></div>
    <div class="grid">
      {suggestion_entries}
    </div>

    <footer class="foot">
      <p class="warn">Generated automatically from market data · Analysis, not financial advice.</p>
      <p>The Wire · built with the Micha Method &amp; Peter Lynch scoring</p>
    </footer>
  </div>
</body>
</html>"""

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_doc)

    return out_path
