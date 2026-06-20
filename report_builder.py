"""
report_builder.py
Builds "The Wire" — a classic broadsheet newspaper HTML report from daily analysis results.

Usage (from run.py):
    from report_builder import build_report
    build_report(portfolio_results, suggestions, newspaper_text)
"""

from datetime import datetime
import html
import json


def _json_default(obj):
    try:
        return obj.item()  # converts numpy int64/float64/bool_ to Python native
    except AttributeError:
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _esc(text):
    if text is None:
        return ""
    return html.escape(str(text))


def _action_class(action):
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


def _cycle_class(stage):
    return {"EARLY": "early", "MID": "mid", "LATE": "late"}.get(
        (stage or "").upper(), "none"
    )


def _bar(score, out_of):
    if score is None or out_of == 0:
        return 0
    return round((score / out_of) * 100)


def _price_line(price_levels):
    if not price_levels:
        return ""
    price = price_levels.get("price_now")
    change = price_levels.get("price_change")
    pct = price_levels.get("price_change_pct")
    if price is None:
        return ""
    price_str = f"${price:,.2f}"
    if change is None or pct is None:
        return f'<span class="price-now">{_esc(price_str)}</span>'
    arrow = "▲" if change >= 0 else "▼"
    cls = "up" if change >= 0 else "down"
    sign = "+" if change >= 0 else ""
    return (
        f'<span class="price-now">{_esc(price_str)}</span>'
        f'<span class="price-change {cls}">'
        f'{arrow} {sign}{change:.2f} ({sign}{pct:.2f}%)'
        f'</span>'
    )


def _sparkline_points(r):
    pl = r.get("price_levels") or {}
    pts = [
        pl.get("week_52_low"),
        pl.get("prior_3m_low"),
        pl.get("sma150"),
        pl.get("sma50"),
        pl.get("recent_3m_low"),
        pl.get("price_now"),
    ]
    return [p for p in pts if p is not None]


def _fmt_briefing(text):
    if not text:
        return ""
    lines = [
        ln.strip().lstrip("*#").strip()
        for ln in text.splitlines()
        if ln.strip().lstrip("*#").strip()
    ]
    if not lines:
        return ""

    # Pick a pull-quote: first sentence of the middle-ish paragraph
    para_lines = [l for l in lines if len(l) >= 60 and not (len(l) < 60 and l.isupper())]
    pull_text = ""
    if para_lines:
        mid_para = para_lines[max(0, len(para_lines) // 2 - 1)]
        dot = mid_para.find(". ")
        pull_text = mid_para[: dot + 1] if dot > 30 else mid_para[:180]

    blocks = []
    first_p = True
    pull_done = False
    mid_idx = max(1, len(lines) // 2 - 1)

    for i, line in enumerate(lines):
        if len(line) < 60 and line.isupper():
            blocks.append(f'<h3 class="brief-sub">{_esc(line)}</h3>')
        else:
            cls = ' class="drop-cap"' if first_p else ""
            blocks.append(f'<p{cls}>{_esc(line)}</p>')
            first_p = False
        if not pull_done and pull_text and i >= mid_idx:
            blocks.append(f'<blockquote class="pull-quote">{_esc(pull_text)}</blockquote>')
            pull_done = True

    return "\n".join(blocks)


# ── Clearbit domain map ────────────────────────────────────────────────────────

TICKER_DOMAIN = {
    "AAPL": "apple.com",    "NVDA": "nvidia.com",     "MSFT": "microsoft.com",
    "GOOGL": "google.com",  "GOOG": "google.com",     "TSM": "tsmc.com",
    "AMZN": "amazon.com",   "ASML": "asml.com",       "META": "meta.com",
    "JPM": "jpmorganchase.com", "JNJ": "jnj.com",     "XOM": "exxonmobil.com",
    "HD": "homedepot.com",  "HON": "honeywell.com",   "UNP": "up.com",
    "V": "visa.com",        "MA": "mastercard.com",   "LLY": "lilly.com",
    "AVGO": "broadcom.com", "COST": "costco.com",     "NFLX": "netflix.com",
    "AMD": "amd.com",       "INTC": "intel.com",      "QCOM": "qualcomm.com",
    "CRM": "salesforce.com","ADBE": "adobe.com",      "ORCL": "oracle.com",
    "IBM": "ibm.com",       "WMT": "walmart.com",     "PG": "pg.com",
    "KO": "coca-cola.com",  "PEP": "pepsico.com",     "MCD": "mcdonalds.com",
    "DIS": "disney.com",    "BA": "boeing.com",       "GS": "goldmansachs.com",
    "MS": "morganstanley.com","BAC": "bankofamerica.com","WFC": "wellsfargo.com",
    "C": "citi.com",        "UNH": "unitedhealthgroup.com","CVX": "chevron.com",
    "PFE": "pfizer.com",    "MRK": "merck.com",       "ABBV": "abbvie.com",
    "TMO": "thermofisher.com","CAT": "caterpillar.com","DE": "deere.com",
    "LMT": "lockheedmartin.com","GE": "ge.com",       "TSLA": "tesla.com",
}


def _logo_html(ticker, size=32, cls="card-logo"):
    domain = TICKER_DOMAIN.get((ticker or "").upper(), "")
    initials = (ticker or "??")[:2].upper()
    fallback_cls = cls.replace("card-logo", "card-logo-fallback").replace("panel-logo", "panel-logo-fallback")
    if domain:
        return (
            f'<img class="{cls}" width="{size}" height="{size}" '
            f'src="https://logo.clearbit.com/{domain}" alt="{_esc(ticker)}" loading="lazy" '
            f'onerror="handleLogoError(this)">'
            f'<span class="{fallback_cls}" style="display:none">{initials}</span>'
        )
    return f'<span class="{fallback_cls}">{initials}</span>'


# ── HTML fragment builders ─────────────────────────────────────────────────────

def _heat_cell(r):
    verdict = r.get("verdict") or {}
    action = verdict.get("action", "")
    cls = _action_class(action)
    micha = r.get("micha_score") or 0
    ticker = r.get("ticker", "")
    action_word = action.split()[0] if action else "—"
    fill_pct = _bar(micha, 12)
    return (
        f'<div class="heat-cell heat-cell--{cls}" onclick="openPanel(\'{_esc(ticker)}\')" '
        f'role="button" tabindex="0" aria-label="{_esc(ticker)}: {_esc(action_word)}">'
        f'<div class="heat-cell__fill" style="width:{fill_pct}%"></div>'
        f'<div class="heat-cell__content">'
        f'<span class="heat-ticker">{_esc(ticker)}</span>'
        f'<span class="heat-score">{micha}/12</span>'
        f'<span class="heat-action">{_esc(action_word)}</span>'
        f'</div>'
        f'</div>'
    )


def _stock_card(r):
    ticker = r.get("ticker", "")
    name = r.get("name", "")
    verdict = r.get("verdict") or {}
    action = verdict.get("action", "")
    cls = _action_class(action)
    action_word = action.split()[0] if action else "—"
    stage = r.get("cycle_stage") or "NONE"
    micha = r.get("micha_score") or 0
    peter_raw = r.get("peter_score")
    peter = peter_raw if peter_raw is not None else 0
    peter_display = f"{peter:.1f}" if peter_raw is not None else "—"
    short_t = verdict.get("short_term") or ""
    snippet = (short_t[:110] + "…") if len(short_t) > 110 else short_t
    sector = r.get("sector", "")
    return (
        f'<article class="card card--{cls}" onclick="openPanel(\'{_esc(ticker)}\')" '
        f'role="button" tabindex="0">'
        f'<div class="card-header">'
        f'{_logo_html(ticker)}'
        f'<div class="card-id">'
        f'<span class="card-ticker">{_esc(ticker)}</span>'
        f'<span class="card-name">{_esc(name)}</span>'
        f'</div>'
        f'<span class="action-tag action-tag--{cls}">{_esc(action_word)}</span>'
        f'</div>'
        f'<div class="card-price">{_price_line(r.get("price_levels"))}</div>'
        f'<canvas id="spark-{_esc(ticker)}" class="sparkline" width="300" height="52"></canvas>'
        f'<div class="card-bars">'
        f'<div class="score-row"><span class="score-label">TECH</span>'
        f'<div class="score-track"><div class="score-fill score-fill--tech" style="width:{_bar(micha,12)}%"></div></div>'
        f'<span class="score-val">{micha}/12</span></div>'
        f'<div class="score-row"><span class="score-label">FUND</span>'
        f'<div class="score-track"><div class="score-fill score-fill--fund" style="width:{_bar(peter,10)}%"></div></div>'
        f'<span class="score-val">{peter_display}/10</span></div>'
        f'</div>'
        f'<div class="card-meta">'
        f'<span class="cycle-badge cycle-badge--{_cycle_class(stage)}">{_esc(stage)}</span>'
        f'<span class="card-sector">{_esc(sector)}</span>'
        f'</div>'
        f'<p class="card-oneliner">{_esc(snippet)}</p>'
        f'<span class="card-cta">Read full report &#8594;</span>'
        f'</article>'
    )


def _suggestion_card(r):
    ticker = r.get("ticker", "")
    name = r.get("name", "")
    verdict = r.get("verdict") or {}
    action = verdict.get("action", "")
    cls = _action_class(action)
    action_word = action.split()[0] if action else "—"
    stage = r.get("cycle_stage") or "NONE"
    micha = r.get("micha_score") or 0
    peter_raw = r.get("peter_score")
    peter = peter_raw if peter_raw is not None else 0
    peter_display = f"{peter:.1f}" if peter_raw is not None else "—"
    short_t = verdict.get("short_term") or ""
    snippet = (short_t[:90] + "…") if len(short_t) > 90 else short_t
    sector = r.get("sector", "")
    return (
        f'<article class="sug-card card--{cls}" onclick="openPanel(\'{_esc(ticker)}\')" '
        f'role="button" tabindex="0">'
        f'<div class="card-header">'
        f'{_logo_html(ticker)}'
        f'<div class="card-id">'
        f'<span class="card-ticker">{_esc(ticker)}</span>'
        f'<span class="card-name">{_esc(name)}</span>'
        f'</div>'
        f'<span class="action-tag action-tag--{cls}">{_esc(action_word)}</span>'
        f'</div>'
        f'<div class="card-price">{_price_line(r.get("price_levels"))}</div>'
        f'<div class="card-bars">'
        f'<div class="score-row"><span class="score-label">TECH</span>'
        f'<div class="score-track"><div class="score-fill score-fill--tech" style="width:{_bar(micha,12)}%"></div></div>'
        f'<span class="score-val">{micha}/12</span></div>'
        f'<div class="score-row"><span class="score-label">FUND</span>'
        f'<div class="score-track"><div class="score-fill score-fill--fund" style="width:{_bar(peter,10)}%"></div></div>'
        f'<span class="score-val">{peter_display}/10</span></div>'
        f'</div>'
        f'<div class="card-meta">'
        f'<span class="cycle-badge cycle-badge--{_cycle_class(stage)}">{_esc(stage)}</span>'
        f'<span class="card-sector">{_esc(sector)}</span>'
        f'</div>'
        f'<p class="card-oneliner">{_esc(snippet)}</p>'
        f'</article>'
    )


# ── CSS ────────────────────────────────────────────────────────────────────────

def _css():
    return '''
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root, [data-theme="light"] {
  --paper:    #f5f0e8;
  --ink:      #0c0c0c;
  --ink-dim:  #4a4a4a;
  --rule:     #0c0c0c;
  --go:       #1a6b2a;
  --stop:     #b51f1f;
  --hold:     #7a5c00;
  --neutral:  #5a5a5a;
  --card-bg:  #faf6ed;
  --pass-bg:  #d4f0d4;
  --fail-bg:  #f7e0e0;
}
[data-theme="dark"] {
  --paper:    #0c0c0c;
  --ink:      #e8eef5;
  --ink-dim:  #8da0b5;
  --rule:     #444;
  --go:       #34d399;
  --stop:     #f26d6d;
  --hold:     #f2b134;
  --neutral:  #6b7d92;
  --card-bg:  #111827;
  --pass-bg:  #0d2a1a;
  --fail-bg:  #2a0d0d;
}

body {
  background: var(--paper);
  color: var(--ink);
  font-family: "Source Serif 4", Georgia, serif;
  font-size: 16px;
  line-height: 1.65;
  transition: background 0.25s, color 0.25s;
}

.wrap {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 2rem 4rem;
}

/* ── Masthead ──────────────────────────────────────────────────────────────── */
.masthead { padding: 1.75rem 0 0; margin-bottom: 2.25rem; }

.masthead-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  padding-bottom: 0.6rem;
}
.eyebrow {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.68rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-dim);
  margin-bottom: 0.15rem;
}
.logotype {
  font-family: "Playfair Display", Georgia, serif;
  font-weight: 900;
  font-size: clamp(3rem, 9vw, 7.5rem);
  letter-spacing: -0.02em;
  line-height: 1;
  text-transform: uppercase;
  color: var(--ink);
}
.masthead-byline {
  font-family: "Source Serif 4", Georgia, serif;
  font-style: italic;
  font-size: 0.95rem;
  color: var(--ink-dim);
  margin-top: 0.15rem;
}
.theme-toggle {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.72rem;
  letter-spacing: 0.06em;
  background: transparent;
  border: 1.5px solid var(--ink);
  color: var(--ink);
  cursor: pointer;
  padding: 0.4rem 0.9rem;
  transition: background 0.15s, color 0.15s;
  white-space: nowrap;
  align-self: center;
}
.theme-toggle:hover { background: var(--ink); color: var(--paper); }

.masthead-rule {
  border: none;
  border-top: 5px solid var(--rule);
  margin: 0;
}
.edition-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem 1.25rem;
  border-top: 1px solid var(--rule);
  padding: 0.4rem 0;
  font-family: "JetBrains Mono", monospace;
  font-size: 0.68rem;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: var(--ink-dim);
}
.edition-divider { color: var(--rule); }
.edition-signal strong { color: var(--go); }

/* ── Section rule ──────────────────────────────────────────────────────────── */
.section { margin-bottom: 3rem; }

.section-rule {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1.5rem;
}
.section-rule::before, .section-rule::after {
  content: "";
  flex: 1;
  border-top: 2px solid var(--rule);
}
.section-rule-inner {
  display: flex;
  align-items: baseline;
  gap: 0.75rem;
  white-space: nowrap;
}
.section-rule-label {
  font-family: "Playfair Display", Georgia, serif;
  font-weight: 900;
  font-size: 0.82rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}
.section-rule-count {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.65rem;
  color: var(--ink-dim);
}

/* ── Heat map ──────────────────────────────────────────────────────────────── */
.heatmap-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0;
  border: 3px solid var(--rule);
}
.heat-cell {
  position: relative;
  overflow: hidden;
  height: 95px;
  cursor: pointer;
  border: 1px solid var(--rule);
  transition: filter 0.15s;
}
.heat-cell:hover { filter: brightness(0.92); }
.heat-cell__fill {
  position: absolute;
  bottom: 0; left: 0; right: 0;
  height: 5px;
}
.heat-cell--go    .heat-cell__fill { background: var(--go); }
.heat-cell--hold  .heat-cell__fill { background: var(--hold); }
.heat-cell--stop  .heat-cell__fill { background: var(--stop); }
.heat-cell--neutral .heat-cell__fill { background: var(--neutral); }

.heat-cell__content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  height: 100%;
  padding: 0.65rem 0.85rem;
}
.heat-ticker {
  font-family: "Playfair Display", Georgia, serif;
  font-weight: 900;
  font-size: 1.5rem;
  line-height: 1;
}
.heat-score {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.7rem;
  color: var(--ink-dim);
  margin-top: 0.2rem;
}
.heat-action {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.6rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  margin-top: 0.3rem;
}
.heat-cell--go    .heat-action { color: var(--go); }
.heat-cell--hold  .heat-action { color: var(--hold); }
.heat-cell--stop  .heat-action { color: var(--stop); }
.heat-cell--neutral .heat-action { color: var(--neutral); }

/* ── Briefing ──────────────────────────────────────────────────────────────── */
.briefing-layout {
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: 3rem;
  align-items: start;
}
.feature-kicker {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.68rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--ink-dim);
  margin-bottom: 0.35rem;
}
.feature-hed {
  font-family: "Playfair Display", Georgia, serif;
  font-weight: 900;
  font-size: clamp(1.6rem, 3vw, 2.5rem);
  line-height: 1.15;
  margin-bottom: 0.85rem;
  border-bottom: 3px solid var(--rule);
  padding-bottom: 0.65rem;
}
.feature-article > p {
  margin-bottom: 1rem;
  text-align: justify;
  hyphens: auto;
}
.feature-article > p.drop-cap::first-letter {
  font-family: "Playfair Display", Georgia, serif;
  font-weight: 900;
  font-size: 4.5em;
  line-height: 0.75;
  float: left;
  margin: 0.04em 0.08em 0 0;
}
.feature-article h3.brief-sub {
  font-family: "Playfair Display", Georgia, serif;
  font-weight: 900;
  font-size: 0.95rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  margin: 1.5rem 0 0.5rem;
  border-bottom: 1px solid var(--rule);
  padding-bottom: 0.3rem;
}
.pull-quote {
  border-left: 4px solid var(--rule);
  margin: 1.5rem 0;
  padding: 0.6rem 1.2rem;
  font-family: "Source Serif 4", Georgia, serif;
  font-style: italic;
  font-size: 1.15rem;
  line-height: 1.5;
  color: var(--ink-dim);
  quotes: none;
}
.briefing-sidebar { position: sticky; top: 1rem; }
.sidebar-block {
  border: 1.5px solid var(--rule);
  background: var(--card-bg);
  padding: 1rem;
  margin-bottom: 1.25rem;
}
.sidebar-label {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.65rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ink-dim);
  margin-bottom: 0.75rem;
  display: block;
}

/* ── Dispatch grids ────────────────────────────────────────────────────────── */
.dispatch-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1.5rem;
}
.suggest-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.25rem;
}

/* ── Cards ─────────────────────────────────────────────────────────────────── */
.card, .sug-card {
  position: relative;
  background: var(--card-bg);
  border: 1.5px solid var(--rule);
  border-top: 4px solid var(--neutral);
  padding: 1rem 1.1rem;
  cursor: pointer;
  transition: box-shadow 0.15s, transform 0.15s;
  text-align: left;
}
.card:hover, .sug-card:hover {
  box-shadow: 4px 4px 0 var(--rule);
  transform: translate(-2px, -2px);
}
.card--go    { border-top-color: var(--go);   }
.card--hold  { border-top-color: var(--hold); }
.card--stop  { border-top-color: var(--stop); }
.card--neutral { border-top-color: var(--neutral); }

.card-header {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.55rem;
}
.card-logo {
  width: 32px; height: 32px;
  border-radius: 50%;
  object-fit: contain;
  border: 1px solid var(--rule);
  background: var(--paper);
  flex-shrink: 0;
}
.card-logo-fallback {
  width: 32px; height: 32px;
  border-radius: 50%;
  border: 1.5px solid var(--rule);
  background: var(--ink);
  color: var(--paper);
  font-family: "JetBrains Mono", monospace;
  font-size: 0.68rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.card-id { flex: 1; min-width: 0; }
.card-ticker {
  font-family: "Playfair Display", Georgia, serif;
  font-weight: 900;
  font-size: 1.3rem;
  line-height: 1;
  display: block;
}
.card-name {
  font-size: 0.75rem;
  color: var(--ink-dim);
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ── Action tags ───────────────────────────────────────────────────────────── */
.action-tag {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 0.15rem 0.45rem;
  border: 1.5px solid;
  white-space: nowrap;
  flex-shrink: 0;
}
.action-tag--go      { border-color: var(--go);   color: var(--go);   }
.action-tag--hold    { border-color: var(--hold);  color: var(--hold); }
.action-tag--stop    { border-color: var(--stop);  color: var(--stop); }
.action-tag--neutral { border-color: var(--neutral); color: var(--neutral); }

/* ── Price ─────────────────────────────────────────────────────────────────── */
.card-price {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.78rem;
  margin-bottom: 0.5rem;
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.price-now { font-weight: 700; font-size: 0.9rem; }
.price-change { font-size: 0.72rem; }
.price-change.up   { color: var(--go);   }
.price-change.down { color: var(--stop); }

/* ── Sparkline ─────────────────────────────────────────────────────────────── */
.sparkline {
  display: block;
  width: 100% !important;
  height: 52px !important;
  margin-bottom: 0.6rem;
}

/* ── Score bars ────────────────────────────────────────────────────────────── */
.card-bars { margin-bottom: 0.55rem; }
.score-row {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  margin-bottom: 0.25rem;
}
.score-label {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.6rem;
  color: var(--ink-dim);
  width: 2.8rem;
  flex-shrink: 0;
  letter-spacing: 0.04em;
}
.score-track {
  flex: 1;
  height: 5px;
  background: rgba(0,0,0,0.1);
  position: relative;
}
[data-theme="dark"] .score-track { background: rgba(255,255,255,0.1); }
.score-fill {
  position: absolute;
  left: 0; top: 0; bottom: 0;
}
.score-fill--tech { background: var(--go);   }
.score-fill--fund { background: var(--hold); }
.score-val {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.6rem;
  color: var(--ink-dim);
  width: 3rem;
  text-align: right;
  flex-shrink: 0;
}

/* ── Card meta ─────────────────────────────────────────────────────────────── */
.card-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  flex-wrap: wrap;
}
.cycle-badge {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.58rem;
  letter-spacing: 0.1em;
  padding: 0.1rem 0.4rem;
  border: 1px solid;
  text-transform: uppercase;
}
.cycle-badge--early   { border-color: var(--go);      color: var(--go);      }
.cycle-badge--mid     { border-color: var(--hold);     color: var(--hold);    }
.cycle-badge--late    { border-color: var(--stop);     color: var(--stop);    }
.cycle-badge--none    { border-color: var(--neutral);  color: var(--neutral); }
.card-sector {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.6rem;
  color: var(--ink-dim);
}
.card-oneliner {
  font-size: 0.83rem;
  color: var(--ink-dim);
  line-height: 1.45;
  font-style: italic;
  margin-bottom: 0.4rem;
}
.card-cta {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.65rem;
  color: var(--ink);
  opacity: 0;
  display: block;
  transition: opacity 0.15s;
  letter-spacing: 0.04em;
}
.card:hover .card-cta, .sug-card:hover .card-cta { opacity: 0.6; }

/* ── Footer ────────────────────────────────────────────────────────────────── */
.footer {
  margin-top: 3rem;
  border-top: 5px solid var(--rule);
  padding-top: 3px;
}
.footer::before {
  content: "";
  display: block;
  border-top: 1px solid var(--rule);
  margin-bottom: 1.1rem;
}
.footer-inner {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0.5rem;
}
.footer-disclaimer {
  font-family: "Source Serif 4", Georgia, serif;
  font-style: italic;
  font-size: 0.82rem;
  color: var(--ink-dim);
}
.footer-sig {
  font-family: "Playfair Display", Georgia, serif;
  font-weight: 900;
  font-size: 0.88rem;
  letter-spacing: 0.05em;
}

/* ── Panel overlay ─────────────────────────────────────────────────────────── */
.panel-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  z-index: 100;
}
.panel-overlay--visible { display: block; }

/* ── Detail panel ──────────────────────────────────────────────────────────── */
.detail-panel {
  position: fixed;
  right: 0; top: 0;
  height: 100vh;
  width: 500px;
  max-width: 100vw;
  overflow-y: auto;
  background: var(--paper);
  border-left: 4px solid var(--rule);
  transform: translateX(105%);
  transition: transform 0.3s cubic-bezier(0.4,0,0.2,1);
  z-index: 200;
}
.detail-panel--open { transform: translateX(0); }
.panel-content { padding-bottom: 3rem; }

.panel-close {
  position: absolute;
  top: 0.9rem; right: 0.9rem;
  width: 2rem; height: 2rem;
  background: transparent;
  border: 1.5px solid var(--ink);
  color: var(--ink);
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s, color 0.15s;
}
.panel-close:hover { background: var(--ink); color: var(--paper); }

/* ── Panel header ──────────────────────────────────────────────────────────── */
.panel-header {
  position: sticky;
  top: 0;
  padding: 1.1rem 1.25rem 0.8rem;
  background: var(--paper);
  border-bottom: 2px solid var(--rule);
  z-index: 5;
}
.panel-header-top {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  margin-bottom: 0.45rem;
  padding-right: 2.5rem;
}
.panel-logo {
  width: 40px; height: 40px;
  border-radius: 50%;
  object-fit: contain;
  border: 1.5px solid var(--rule);
  background: var(--paper);
  flex-shrink: 0;
}
.panel-logo-fallback {
  width: 40px; height: 40px;
  border-radius: 50%;
  border: 1.5px solid var(--rule);
  background: var(--ink);
  color: var(--paper);
  font-family: "JetBrains Mono", monospace;
  font-size: 0.78rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.panel-title-wrap { flex: 1; min-width: 0; }
.panel-ticker {
  font-family: "Playfair Display", Georgia, serif;
  font-weight: 900;
  font-size: 1.65rem;
  line-height: 1;
  display: block;
}
.panel-name {
  font-size: 0.78rem;
  color: var(--ink-dim);
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.panel-price {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.83rem;
  margin-bottom: 0.35rem;
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.panel-meta-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.panel-sector {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.62rem;
  color: var(--ink-dim);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/* ── Panel body ────────────────────────────────────────────────────────────── */
.panel-body { padding: 1.25rem; }
.panel-section {
  margin-bottom: 2rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid var(--rule);
}
.panel-section:last-child { border-bottom: none; }
.panel-section-title {
  font-family: "Playfair Display", Georgia, serif;
  font-weight: 900;
  font-size: 1.05rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-bottom: 0.75rem;
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  border-bottom: 2px solid var(--rule);
  padding-bottom: 0.35rem;
}
.panel-tally {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.72rem;
  color: var(--ink-dim);
  font-weight: 400;
  letter-spacing: 0;
}

/* ── Panel: The Story ──────────────────────────────────────────────────────── */
.panel-story p {
  font-size: 0.9rem;
  line-height: 1.65;
  margin-bottom: 0.75rem;
  text-align: justify;
  hyphens: auto;
}
.panel-story p.panel-drop-cap::first-letter {
  font-family: "Playfair Display", Georgia, serif;
  font-weight: 900;
  font-size: 3.5em;
  line-height: 0.75;
  float: left;
  margin: 0.04em 0.08em 0 0;
}
.panel-pull {
  border-left: 4px solid var(--rule);
  margin: 1rem 0;
  padding: 0.5rem 1rem;
  font-style: italic;
  font-size: 0.93rem;
  line-height: 1.5;
  color: var(--ink-dim);
  quotes: none;
}

/* ── Panel: Micha Method ───────────────────────────────────────────────────── */
.crit-list { display: flex; flex-direction: column; }
.crit-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.28rem 0.4rem;
}
.crit-row:nth-child(odd) { background: rgba(0,0,0,0.03); }
[data-theme="dark"] .crit-row:nth-child(odd) { background: rgba(255,255,255,0.03); }
.crit-name {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.7rem;
  color: var(--ink);
}
.crit-badge {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  padding: 0.1rem 0.4rem;
  border: 1px solid;
  flex-shrink: 0;
}
.crit-pass { border-color: var(--go);   color: var(--go);   background: var(--pass-bg); }
.crit-fail { border-color: var(--stop); color: var(--stop); background: var(--fail-bg); }
.crit-reason {
  font-size: 0.76rem;
  font-style: italic;
  color: var(--ink-dim);
  padding: 0.2rem 0.5rem 0.4rem 1.2rem;
  border-left: 2px solid var(--rule);
  margin: 0.1rem 0 0.4rem 0.75rem;
  line-height: 1.45;
}

/* ── Panel: Peter Lynch ────────────────────────────────────────────────────── */
.peter-bars { margin-bottom: 1rem; }
.peter-bar-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.3rem;
}
.peter-bar-label {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.62rem;
  color: var(--ink-dim);
  width: 10.5rem;
  flex-shrink: 0;
}
.peter-bar-track {
  flex: 1;
  height: 6px;
  background: rgba(0,0,0,0.1);
  position: relative;
}
[data-theme="dark"] .peter-bar-track { background: rgba(255,255,255,0.1); }
.peter-bar-fill {
  position: absolute;
  left: 0; top: 0; bottom: 0;
  background: var(--hold);
}
.peter-bar-val {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.62rem;
  color: var(--ink-dim);
  width: 2.5rem;
  text-align: right;
  flex-shrink: 0;
}
.key-metrics-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.6rem;
  margin-top: 0.75rem;
}
.key-metric {
  border: 1.5px solid var(--rule);
  padding: 0.5rem 0.75rem;
  background: var(--card-bg);
}
.key-metric-label {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.58rem;
  color: var(--ink-dim);
  display: block;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  margin-bottom: 0.2rem;
}
.key-metric-val {
  font-family: "JetBrains Mono", monospace;
  font-size: 1rem;
  font-weight: 700;
  color: var(--ink);
  display: block;
}

/* ── Panel: The Verdict ────────────────────────────────────────────────────── */
.verdict-action {
  font-family: "Playfair Display", Georgia, serif;
  font-weight: 900;
  font-size: 1.9rem;
  letter-spacing: 0.02em;
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 2px solid;
}
.verdict-action--go      { color: var(--go);   border-color: var(--go);   }
.verdict-action--hold    { color: var(--hold);  border-color: var(--hold); }
.verdict-action--stop    { color: var(--stop);  border-color: var(--stop); }
.verdict-action--neutral { color: var(--neutral); border-color: var(--neutral); }

.verdict-body p {
  font-size: 0.87rem;
  line-height: 1.6;
  margin-bottom: 0.65rem;
}
.verdict-body strong {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.68rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.buy-zone-box {
  border: 2px solid var(--go);
  padding: 0.75rem 1rem;
  margin-top: 0.75rem;
}
.bz-range {
  font-family: "JetBrains Mono", monospace;
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--go);
  margin-bottom: 0.15rem;
}
.bz-floor {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.75rem;
  color: var(--ink-dim);
}
.no-zone {
  font-family: "JetBrains Mono", monospace;
  font-size: 0.75rem;
  color: var(--stop);
  border: 1.5px solid var(--stop);
  padding: 0.65rem 0.85rem;
  margin-top: 0.75rem;
  line-height: 1.45;
}

/* ── Responsive ────────────────────────────────────────────────────────────── */
@media (max-width: 1000px) {
  .briefing-layout { grid-template-columns: 1fr; }
  .briefing-sidebar { position: static; display: flex; gap: 1rem; flex-wrap: wrap; }
  .sidebar-block { flex: 1; min-width: 220px; }
}
@media (max-width: 820px) {
  .dispatch-grid { grid-template-columns: 1fr; }
  .suggest-grid  { grid-template-columns: repeat(2, 1fr); }
  .heatmap-grid  { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 560px) {
  .wrap { padding: 0 1rem 2rem; }
  .suggest-grid  { grid-template-columns: 1fr; }
  .heatmap-grid  { grid-template-columns: repeat(2, 1fr); }
  .logotype { font-size: 2.8rem; }
  .detail-panel { width: 100vw; }
}
'''


# ── JavaScript ─────────────────────────────────────────────────────────────────
# Plain string (not f-string) so JS braces {} are not interpreted by Python.

_JS_BODY = '''
const STOCK_MAP = {};
STOCKS.forEach(function(s) { STOCK_MAP[s.ticker] = s; });

function handleLogoError(img) {
  img.style.display = 'none';
  if (img.nextElementSibling) img.nextElementSibling.style.display = 'flex';
}

// ── Theme ─────────────────────────────────────────────────────────────────────
function toggleTheme() {
  var html = document.documentElement;
  var next = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  try { localStorage.setItem('wire-theme', next); } catch(e) {}
  setTimeout(function() { renderRadarChart(); renderDistChart(); }, 30);
}

(function() {
  try {
    var saved = localStorage.getItem('wire-theme');
    if (saved) document.documentElement.setAttribute('data-theme', saved);
  } catch(e) {}
})();

// ── Panel ─────────────────────────────────────────────────────────────────────
function openPanel(ticker) {
  var s = STOCK_MAP[ticker];
  if (!s) return;
  document.getElementById('panelContent').innerHTML = buildPanelHTML(s);
  document.getElementById('detailPanel').classList.add('detail-panel--open');
  document.getElementById('overlay').classList.add('panel-overlay--visible');
  document.body.style.overflow = 'hidden';
}

function closePanel() {
  document.getElementById('detailPanel').classList.remove('detail-panel--open');
  document.getElementById('overlay').classList.remove('panel-overlay--visible');
  document.body.style.overflow = '';
}

document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') closePanel();
});

// ── Panel HTML builder ────────────────────────────────────────────────────────
function jEsc(t) {
  if (t == null) return '';
  return String(t)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function fmtDollar(n) {
  if (n == null) return '—';
  return '$' + Number(n).toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2});
}

var CRITERIA_LABELS = {
  '1_price_above_sma150':   'Price above SMA 150',
  '2_sma150_slope_positive':'SMA 150 slope positive',
  '3_price_above_sma50':    'Price above SMA 50',
  '4_sma50_above_sma150':   'SMA 50 above SMA 150',
  '5_golden_cross_recent':  'Golden cross',
  '6_atr_shock_recent':     'ATR volatility shock',
  '7_breakout_quality':     'Breakout quality (AI)',
  '8_retest_quality':       'Retest quality (AI)',
  '9_volume_expansion':     'Volume expansion',
  '10_volume_dryup_before': 'Volume dry-up prior',
  '11_higher_highs_lows':   'Higher highs & higher lows',
  '12_rs_vs_sp500':         'Relative strength vs S&P 500'
};

var CRITERIA_ORDER = [
  '1_price_above_sma150','2_sma150_slope_positive','3_price_above_sma50',
  '4_sma50_above_sma150','5_golden_cross_recent','6_atr_shock_recent',
  '7_breakout_quality','8_retest_quality','9_volume_expansion',
  '10_volume_dryup_before','11_higher_highs_lows','12_rs_vs_sp500'
];

var PETER_LABELS = {
  'revenue_growth':        'Revenue Growth',
  'eps_growth':            'EPS Growth',
  'net_income_trend':      'Net Income Trend',
  'balance_sheet':         'Balance Sheet',
  'cash_flow':             'Cash Flow Quality',
  'moat':                  'Moat & Competitive Edge',
  'valuation':             'Valuation',
  'management':            'Management Quality',
  'industry':              'Industry Strength',
  'long_term_compounding': 'Long-Term Compounding'
};

var PETER_ORDER = [
  'revenue_growth','eps_growth','net_income_trend','balance_sheet',
  'cash_flow','moat','valuation','management','industry','long_term_compounding'
];

function actionClass(action) {
  if (!action) return 'neutral';
  var a = action.toUpperCase();
  if (a.indexOf('BUY') >= 0 || a.indexOf('ACCUMULATE') >= 0) return 'go';
  if (a.indexOf('WAIT') >= 0) return 'hold';
  if (a.indexOf('AVOID') >= 0) return 'stop';
  return 'neutral';
}

function cycleClass(stage) {
  var m = {EARLY:'early', MID:'mid', LATE:'late'};
  return m[(stage||'').toUpperCase()] || 'none';
}

function buildPanelHTML(s) {
  var v   = s.verdict || {};
  var pl  = s.price_levels || {};
  var bz  = s.buy_zone;
  var cls = actionClass(v.action || '');
  var initials = (s.ticker||'').slice(0,2).toUpperCase();

  // Price change line
  var priceHtml = '<span class="price-now">' + jEsc(fmtDollar(pl.price_now)) + '</span>';
  if (pl.price_change != null && pl.price_change_pct != null) {
    var chg  = pl.price_change;
    var pct  = pl.price_change_pct;
    var arr  = chg >= 0 ? '▲' : '▼';
    var dir  = chg >= 0 ? 'up' : 'down';
    var sign = chg >= 0 ? '+' : '';
    priceHtml += ' <span class="price-change ' + dir + '">' + arr + ' ' +
      sign + Number(chg).toFixed(2) + ' (' + sign + Number(pct).toFixed(2) + '%)</span>';
  }

  // Logo
  var logoHtml;
  if (s.domain) {
    logoHtml = '<img class="panel-logo" width="40" height="40" src="https://logo.clearbit.com/' +
      jEsc(s.domain) + '" alt="' + jEsc(s.ticker) + '" loading="lazy" ' +
      'onerror="handleLogoError(this)">' +
      '<span class="panel-logo-fallback" style="display:none">' + initials + '</span>';
  } else {
    logoHtml = '<span class="panel-logo-fallback">' + initials + '</span>';
  }

  // Section 1: The Story
  var storyParts = [];
  if (s.cycle_stage_reasoning) storyParts.push({t: s.cycle_stage_reasoning, dc: true});
  if (v.micha_meaning)         storyParts.push({t: v.micha_meaning});
  if (s.micha_reasons && s.micha_reasons['7']) storyParts.push({t: s.micha_reasons['7']});
  if (s.micha_reasons && s.micha_reasons['8']) storyParts.push({t: s.micha_reasons['8']});
  if (v.peter_meaning)         storyParts.push({t: v.peter_meaning});
  if (s.peter_summary)         storyParts.push({t: s.peter_summary});
  if (s.buy_zone_narrative)    storyParts.push({t: s.buy_zone_narrative});

  var pullQuote   = v.short_term || '';
  var pullMidIdx  = Math.max(0, Math.floor(storyParts.length / 2) - 1);
  var pullInserted = false;
  var storyHtml   = '';

  for (var i = 0; i < storyParts.length; i++) {
    var p   = storyParts[i];
    var dcCls = p.dc ? ' class="panel-drop-cap"' : '';
    storyHtml += '<p' + dcCls + '>' + jEsc(p.t) + '</p>';
    if (!pullInserted && pullQuote && i >= pullMidIdx) {
      storyHtml += '<blockquote class="panel-pull">' + jEsc(pullQuote) + '</blockquote>';
      pullInserted = true;
    }
  }

  // Section 2: Micha Method
  var crit    = s.micha_criteria || {};
  var reasons = s.micha_reasons  || {};
  var passCount = 0;
  CRITERIA_ORDER.forEach(function(k) { if (crit[k]) passCount++; });

  var michaHtml = '';
  CRITERIA_ORDER.forEach(function(key) {
    var val   = crit[key];
    var label = CRITERIA_LABELS[key] || key;
    var bCls  = val ? 'crit-pass' : 'crit-fail';
    var bTxt  = val ? 'PASS' : 'FAIL';
    michaHtml += '<div class="crit-row"><span class="crit-name">' + jEsc(label) +
      '</span><span class="crit-badge ' + bCls + '">' + bTxt + '</span></div>';
    if (key === '7_breakout_quality' && reasons['7']) {
      michaHtml += '<p class="crit-reason">' + jEsc(reasons['7']) + '</p>';
    }
    if (key === '8_retest_quality' && reasons['8']) {
      michaHtml += '<p class="crit-reason">' + jEsc(reasons['8']) + '</p>';
    }
  });

  // Section 3: Peter Lynch
  var ps = s.peter_scores || {};
  var peterBarsHtml = '';
  PETER_ORDER.forEach(function(key) {
    var score = ps[key];
    if (score == null) return;
    var label = PETER_LABELS[key] || key;
    var pct2  = Math.round((score / 10) * 100);
    peterBarsHtml += '<div class="peter-bar-row">' +
      '<span class="peter-bar-label">' + jEsc(label) + '</span>' +
      '<div class="peter-bar-track"><div class="peter-bar-fill" style="width:' + pct2 + '%"></div></div>' +
      '<span class="peter-bar-val">' + Number(score).toFixed(1) + '</span>' +
      '</div>';
  });

  var keyMetrics = [
    {label:'Valuation',   key:'valuation'},
    {label:'EPS Growth',  key:'eps_growth'},
    {label:'Net Income',  key:'net_income_trend'},
    {label:'Management',  key:'management'}
  ];
  var kmHtml = '<div class="key-metrics-grid">';
  keyMetrics.forEach(function(m) {
    var val = ps[m.key] != null ? Number(ps[m.key]).toFixed(1) + '/10' : '—';
    kmHtml += '<div class="key-metric">' +
      '<span class="key-metric-label">' + jEsc(m.label) + '</span>' +
      '<span class="key-metric-val">' + jEsc(val) + '</span>' +
      '</div>';
  });
  kmHtml += '</div>';

  // Section 4: The Verdict
  var actionText = v.action || '—';
  var buyZoneHtml;
  if (bz && bz.low != null && bz.high != null) {
    buyZoneHtml = '<div class="buy-zone-box">' +
      '<p class="bz-range">' + jEsc(fmtDollar(bz.low)) + ' – ' + jEsc(fmtDollar(bz.high)) + '</p>' +
      '<p class="bz-floor">Floor support: ' + jEsc(fmtDollar(bz.floor)) + '</p>' +
      '</div>';
  } else {
    buyZoneHtml = '<p class="no-zone">No technical buy zone — downtrend conditions.</p>';
  }

  var verdictBodyHtml = '';
  if (v.short_term)            verdictBodyHtml += '<p><strong>Short term</strong> &nbsp; ' + jEsc(v.short_term) + '</p>';
  if (v.long_term)             verdictBodyHtml += '<p><strong>Long term</strong> &nbsp; '  + jEsc(v.long_term)  + '</p>';
  if (v.accumulation_strategy) verdictBodyHtml += '<p><strong>Strategy</strong> &nbsp; '   + jEsc(v.accumulation_strategy) + '</p>';
  verdictBodyHtml += buyZoneHtml;

  return (
    '<div class="panel-header panel-header--' + cls + '">' +
      '<div class="panel-header-top">' +
        '<div class="panel-logo-wrap">' + logoHtml + '</div>' +
        '<div class="panel-title-wrap">' +
          '<span class="panel-ticker">' + jEsc(s.ticker) + '</span>' +
          '<span class="panel-name">'   + jEsc(s.name)   + '</span>' +
        '</div>' +
        '<span class="action-tag action-tag--' + cls + '">' + jEsc(actionText) + '</span>' +
      '</div>' +
      '<div class="panel-price">' + priceHtml + '</div>' +
      '<div class="panel-meta-row">' +
        '<span class="panel-sector">' + jEsc(s.sector) + '</span>' +
        '<span class="cycle-badge cycle-badge--' + cycleClass(s.cycle_stage) + '">' +
          jEsc(s.cycle_stage || 'NONE') + '</span>' +
      '</div>' +
    '</div>' +
    '<div class="panel-body">' +
      '<section class="panel-section">' +
        '<h3 class="panel-section-title">The Story</h3>' +
        '<div class="panel-story">' + storyHtml + '</div>' +
      '</section>' +
      '<section class="panel-section">' +
        '<h3 class="panel-section-title">Micha Method <span class="panel-tally">' + passCount + '/12</span></h3>' +
        '<div class="crit-list">' + michaHtml + '</div>' +
      '</section>' +
      '<section class="panel-section">' +
        '<h3 class="panel-section-title">Peter Lynch <span class="panel-tally">' +
          Number(s.peter_score || 0).toFixed(1) + '/10</span></h3>' +
        '<div class="peter-bars">' + peterBarsHtml + '</div>' +
        kmHtml +
      '</section>' +
      '<section class="panel-section">' +
        '<h3 class="panel-section-title">The Verdict</h3>' +
        '<div class="verdict-action verdict-action--' + cls + '">' + jEsc(actionText) + '</div>' +
        '<div class="verdict-body">' + verdictBodyHtml + '</div>' +
      '</section>' +
    '</div>'
  );
}

// ── Sparklines ────────────────────────────────────────────────────────────────
var sparkCharts = {};

function getCSSVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function renderSparklines() {
  STOCKS.forEach(function(s) {
    var canvas = document.getElementById('spark-' + s.ticker);
    if (!canvas) return;
    var pts = s.sparkline;
    if (!pts || pts.length < 2) return;
    if (sparkCharts[s.ticker]) {
      try { sparkCharts[s.ticker].destroy(); } catch(e) {}
    }
    var rising = pts[pts.length - 1] >= pts[0];
    var color  = rising ? getCSSVar('--go') : getCSSVar('--stop');
    sparkCharts[s.ticker] = new Chart(canvas, {
      type: 'line',
      data: {
        labels: pts.map(function(_, i) { return i; }),
        datasets: [{
          data: pts,
          borderColor: color,
          borderWidth: 1.5,
          tension: 0.35,
          fill: false,
          pointRadius: 0,
          pointHoverRadius: 0
        }]
      },
      options: {
        animation: false,
        responsive: false,
        plugins: {
          legend: { display: false },
          tooltip: { enabled: false }
        },
        scales: {
          x: { display: false },
          y: { display: false }
        }
      }
    });
  });
}

// ── Radar chart ───────────────────────────────────────────────────────────────
var radarChart = null;

function renderRadarChart() {
  var canvas = document.getElementById('radarChart');
  if (!canvas || typeof Chart === 'undefined') return;
  if (radarChart) { try { radarChart.destroy(); } catch(e) {} radarChart = null; }

  var portfolio = STOCKS.slice(0, PORTFOLIO_COUNT);
  if (!portfolio.length) return;

  var michaGroups = {
    'Trend':    ['1_price_above_sma150','2_sma150_slope_positive','3_price_above_sma50','4_sma50_above_sma150'],
    'Breakout': ['7_breakout_quality','8_retest_quality'],
    'Volume':   ['9_volume_expansion','10_volume_dryup_before'],
    'Momentum': ['5_golden_cross_recent','6_atr_shock_recent'],
    'Strength': ['11_higher_highs_lows','12_rs_vs_sp500']
  };
  var peterGroups = {
    'Trend':    ['revenue_growth','eps_growth'],
    'Breakout': ['valuation'],
    'Volume':   ['net_income_trend','cash_flow'],
    'Momentum': ['management','balance_sheet'],
    'Strength': ['moat','industry','long_term_compounding']
  };
  var labels = Object.keys(michaGroups);

  function avgMicha(group) {
    var total = 0;
    portfolio.forEach(function(s) {
      var crit = s.micha_criteria || {};
      var hits = group.reduce(function(sum, k) { return sum + (crit[k] ? 1 : 0); }, 0);
      total += (hits / group.length) * 10;
    });
    return total / portfolio.length;
  }
  function avgPeter(group) {
    var total = 0;
    portfolio.forEach(function(s) {
      var ps   = s.peter_scores || {};
      var vals = group.map(function(k) { return ps[k] || 0; });
      var avg  = vals.reduce(function(a,b) { return a+b; }, 0) / vals.length;
      total += avg;
    });
    return total / portfolio.length;
  }

  var michaData = labels.map(function(l) { return avgMicha(michaGroups[l]); });
  var peterData = labels.map(function(l) { return avgPeter(peterGroups[l]); });

  var ink  = getCSSVar('--ink');
  var go   = getCSSVar('--go');
  var hold = getCSSVar('--hold');

  radarChart = new Chart(canvas, {
    type: 'radar',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Technical (Micha)',
          data: michaData,
          borderColor: go,
          backgroundColor: go + '30',
          borderWidth: 1.5,
          pointRadius: 3,
          pointBackgroundColor: go
        },
        {
          label: 'Fundamental (Peter)',
          data: peterData,
          borderColor: hold,
          backgroundColor: hold + '30',
          borderWidth: 1.5,
          pointRadius: 3,
          pointBackgroundColor: hold
        }
      ]
    },
    options: {
      animation: false,
      responsive: false,
      scales: {
        r: {
          min: 0, max: 10,
          ticks: { display: false, stepSize: 2 },
          grid: { color: ink + '25' },
          angleLines: { color: ink + '25' },
          pointLabels: {
            color: ink,
            font: { family: "'JetBrains Mono'", size: 10 }
          }
        }
      },
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            color: ink,
            font: { family: "'Source Serif 4'", size: 11 },
            boxWidth: 12,
            padding: 10
          }
        }
      }
    }
  });
}

// ── Score distribution chart ──────────────────────────────────────────────────
var distChart = null;

function renderDistChart() {
  var canvas = document.getElementById('distChart');
  if (!canvas || typeof Chart === 'undefined') return;
  if (distChart) { try { distChart.destroy(); } catch(e) {} distChart = null; }

  var portfolio = STOCKS.slice(0, PORTFOLIO_COUNT);
  if (!portfolio.length) return;

  var sorted = portfolio.slice().sort(function(a, b) {
    var sa = (a.micha_score/12 + (a.peter_score||0)/10) / 2;
    var sb = (b.micha_score/12 + (b.peter_score||0)/10) / 2;
    return sb - sa;
  });

  var ink  = getCSSVar('--ink');
  var go   = getCSSVar('--go');
  var stop = getCSSVar('--stop');
  var hold = getCSSVar('--hold');

  function barColor(s) {
    var c = actionClass((s.verdict && s.verdict.action) || '');
    return c === 'go' ? go + 'cc' : c === 'stop' ? stop + 'cc' : hold + 'cc';
  }

  distChart = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: sorted.map(function(s) { return s.ticker; }),
      datasets: [{
        data: sorted.map(function(s) {
          return Math.round(((s.micha_score/12 + (s.peter_score||0)/10) / 2) * 100);
        }),
        backgroundColor: sorted.map(barColor),
        borderWidth: 0
      }]
    },
    options: {
      indexAxis: 'y',
      animation: false,
      responsive: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: function(ctx) { return ' ' + ctx.raw + '%'; }
          }
        }
      },
      scales: {
        x: {
          min: 0, max: 100,
          ticks: {
            color: ink,
            font: { size: 10 },
            maxTicksLimit: 5,
            callback: function(v) { return v + '%'; }
          },
          grid: { color: ink + '20' }
        },
        y: {
          ticks: {
            color: ink,
            font: { family: "'JetBrains Mono'", size: 10 }
          },
          grid: { display: false }
        }
      }
    }
  });
}

// ── Init ──────────────────────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', function() {
  renderSparklines();
  renderRadarChart();
  renderDistChart();
});
'''


def _js(stocks_json, portfolio_count):
    return (
        'const STOCKS = ' + stocks_json + ';\n'
        'const PORTFOLIO_COUNT = ' + str(portfolio_count) + ';\n'
        + _JS_BODY
    )


# ── Main ───────────────────────────────────────────────────────────────────────

def build_report(portfolio_results, suggestions, newspaper_text,
                 out_path="daily_report.html"):
    """Build the full HTML report and write it to out_path."""
    now = datetime.now()
    date_long = now.strftime("%A, %B %d, %Y").upper()

    go_count = sum(
        1 for r in portfolio_results
        if _action_class((r.get("verdict") or {}).get("action", "")) == "go"
    )
    n_portfolio = len(portfolio_results)
    n_suggest = len(suggestions)
    signal_str = f"{go_count}/{n_portfolio}"

    # Build JS data payload
    all_stocks = portfolio_results + suggestions
    stocks_payload = []
    for r in all_stocks:
        pl = r.get("price_levels") or {}
        ticker = r.get("ticker", "")
        stocks_payload.append({
            "ticker":              ticker,
            "name":                r.get("name", ""),
            "sector":              r.get("sector", ""),
            "micha_score":         r.get("micha_score") or 0,
            "micha_criteria":      r.get("micha_criteria") or {},
            "micha_reasons":       r.get("micha_reasons") or {},
            "peter_score":         r.get("peter_score") or 0,
            "peter_scores":        r.get("peter_scores") or {},
            "peter_summary":       r.get("peter_summary") or "",
            "verdict":             r.get("verdict") or {},
            "cycle_stage":         r.get("cycle_stage") or "",
            "cycle_stage_reasoning": r.get("cycle_stage_reasoning") or "",
            "buy_zone":            r.get("buy_zone"),
            "buy_zone_narrative":  r.get("buy_zone_narrative") or "",
            "price_levels":        pl,
            "sparkline":           _sparkline_points(r),
            "domain":              TICKER_DOMAIN.get(ticker.upper(), ""),
        })
    stocks_json = json.dumps(stocks_payload, ensure_ascii=False, default=_json_default)

    # HTML sections
    heatmap_cells = "\n".join(_heat_cell(r) for r in portfolio_results)
    briefing_html = _fmt_briefing(newspaper_text)
    portfolio_cards = "\n".join(_stock_card(r) for r in portfolio_results)
    suggestion_cards = "\n".join(_suggestion_card(r) for r in suggestions)
    s_suffix = "s" if n_portfolio != 1 else ""

    html_doc = f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>The Wire &#8212; {_esc(date_long)}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@900&family=Source+Serif+4:ital,wght@0,400;0,600;1,400&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
  <style>{_css()}</style>
</head>
<body>
<div class="wrap">

  <header class="masthead">
    <div class="masthead-top">
      <div class="masthead-brand">
        <p class="eyebrow">Market Dispatch &middot; Automated Daily Edition</p>
        <h1 class="logotype">The Wire</h1>
        <p class="masthead-byline">by Tal Haran</p>
      </div>
      <button class="theme-toggle" onclick="toggleTheme()" aria-label="Toggle day/night">
        &#9728; Morning &nbsp;/&nbsp; &#9790; Night
      </button>
    </div>
    <hr class="masthead-rule">
    <div class="edition-row">
      <span class="dateline">{_esc(date_long)}</span>
      <span class="edition-divider">&middot;</span>
      <span class="edition-signal">Portfolio Signal &nbsp;&middot;&nbsp; <strong>{signal_str}</strong> accumulate</span>
      <span class="edition-divider">&middot;</span>
      <span class="edition-vol">Vol. 1</span>
    </div>
  </header>

  <section class="section">
    <div class="section-rule">
      <div class="section-rule-inner">
        <span class="section-rule-label">Portfolio Heat Map</span>
      </div>
    </div>
    <div class="heatmap-grid">
{heatmap_cells}
    </div>
  </section>

  <section class="section">
    <div class="section-rule">
      <div class="section-rule-inner">
        <span class="section-rule-label">Today&#8217;s Briefing</span>
      </div>
    </div>
    <div class="briefing-layout">
      <div class="briefing-body">
        <p class="feature-kicker">Daily Market Intelligence</p>
        <h2 class="feature-hed">The Morning Dispatch</h2>
        <div class="feature-article">
{briefing_html}
        </div>
      </div>
      <aside class="briefing-sidebar">
        <div class="sidebar-block">
          <span class="sidebar-label">Portfolio Composition</span>
          <canvas id="radarChart" width="260" height="260"></canvas>
        </div>
        <div class="sidebar-block">
          <span class="sidebar-label">Portfolio Ranking</span>
          <canvas id="distChart" width="260" height="180"></canvas>
        </div>
      </aside>
    </div>
  </section>

  <section class="section">
    <div class="section-rule">
      <div class="section-rule-inner">
        <span class="section-rule-label">Portfolio Dispatches</span>
        <span class="section-rule-count">{n_portfolio} position{s_suffix}</span>
      </div>
    </div>
    <div class="dispatch-grid">
{portfolio_cards}
    </div>
  </section>

  <section class="section">
    <div class="section-rule">
      <div class="section-rule-inner">
        <span class="section-rule-label">Diversifier Dispatches</span>
        <span class="section-rule-count">{n_suggest} suggestion{"s" if n_suggest != 1 else ""}</span>
      </div>
    </div>
    <div class="suggest-grid">
{suggestion_cards}
    </div>
  </section>

  <footer class="footer">
    <div class="footer-inner">
      <span class="footer-disclaimer">Generated automatically from market data &mdash; analysis only, not financial advice.</span>
      <span class="footer-sig">The Wire &nbsp;&middot;&nbsp; by Tal Haran</span>
    </div>
  </footer>

</div>

<div class="panel-overlay" id="overlay" onclick="closePanel()"></div>
<aside class="detail-panel" id="detailPanel" role="dialog" aria-modal="true" aria-label="Stock detail">
  <button class="panel-close" onclick="closePanel()" aria-label="Close">&times;</button>
  <div id="panelContent" class="panel-content"></div>
</aside>

<script>{_js(stocks_json, n_portfolio)}</script>
</body>
</html>"""

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html_doc)

    return out_path


# ── Quick local test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    _demo_result = {
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "sector": "Technology",
        "micha_score": 9,
        "micha_criteria": {
            "1_price_above_sma150": True,  "2_sma150_slope_positive": True,
            "3_price_above_sma50": True,   "4_sma50_above_sma150": True,
            "5_golden_cross_recent": False, "6_atr_shock_recent": True,
            "7_breakout_quality": True,    "8_retest_quality": True,
            "9_volume_expansion": True,    "10_volume_dryup_before": False,
            "11_higher_highs_lows": True,  "12_rs_vs_sp500": False,
        },
        "micha_reasons": {
            "7": "Price broke above the 52-week high on strong volume with a clean base.",
            "8": "The retest of the breakout level held perfectly at the SMA50.",
        },
        "peter_score": 7.8,
        "peter_scores": {
            "revenue_growth": 8.0, "eps_growth": 7.5, "net_income_trend": 8.0,
            "balance_sheet": 9.0, "cash_flow": 9.0, "moat": 9.5,
            "valuation": 5.5, "management": 8.0, "industry": 7.0, "long_term_compounding": 8.0,
        },
        "peter_summary": "Apple continues to demonstrate exceptional fundamentals. "
                         "Revenue growth has re-accelerated driven by services. "
                         "The balance sheet remains fortress-strong with significant buyback capacity.",
        "verdict": {
            "action": "ACCUMULATE",
            "micha_meaning": "Nine of twelve technical criteria pass, confirming a strong uptrend structure.",
            "peter_meaning": "A Peter Lynch score of 7.8 reflects a high-quality business trading at a premium.",
            "short_term": "The 1-6 month setup favors accumulation on pullbacks toward the SMA50 near $185.",
            "long_term": "Apple's services flywheel and installed base provide durable compounding over 3-5 years.",
            "accumulation_strategy": "Build a starter position at current levels and add aggressively on any pullback to the $182-$188 buy zone.",
        },
        "cycle_stage": "EARLY",
        "cycle_stage_reasoning": "Apple has broken out of a multi-month base on expanding volume, "
                                  "signaling the early phase of a new upswing cycle.",
        "buy_zone": {"low": 182.50, "high": 188.00, "floor": 176.30},
        "buy_zone_narrative": "The buy zone aligns with the 50-day SMA providing dynamic support.",
        "price_levels": {
            "price_now": 191.45, "price_change": 2.31, "price_change_pct": 1.22,
            "price_date": "2026-06-20", "sma50": 185.20, "sma150": 172.40,
            "price_vs_sma50_pct": 3.37, "price_vs_sma150_pct": 11.05,
            "recent_3m_low": 178.50, "recent_3m_high": 193.20,
            "prior_3m_low": 161.00, "week_52_low": 158.25,
            "golden_cross_days_ago": 42,
        },
    }

    _demo_suggest = {
        "ticker": "NVDA",
        "name": "NVIDIA Corporation",
        "sector": "Semiconductors",
        "micha_score": 11,
        "micha_criteria": {
            "1_price_above_sma150": True,  "2_sma150_slope_positive": True,
            "3_price_above_sma50": True,   "4_sma50_above_sma150": True,
            "5_golden_cross_recent": True,  "6_atr_shock_recent": True,
            "7_breakout_quality": True,    "8_retest_quality": True,
            "9_volume_expansion": True,    "10_volume_dryup_before": True,
            "11_higher_highs_lows": True,  "12_rs_vs_sp500": False,
        },
        "micha_reasons": {
            "7": "Explosive breakout on AI-driven earnings beat with record volume.",
            "8": "Clean flag consolidation before resuming the uptrend.",
        },
        "peter_score": 8.5,
        "peter_scores": {
            "revenue_growth": 9.5, "eps_growth": 9.0, "net_income_trend": 9.5,
            "balance_sheet": 8.5, "cash_flow": 8.5, "moat": 9.5,
            "valuation": 5.0, "management": 9.0, "industry": 9.5, "long_term_compounding": 9.0,
        },
        "peter_summary": "NVIDIA's AI infrastructure dominance is unmatched. "
                         "Data center revenue is compounding at triple digits. "
                         "The moat widens with each software ecosystem expansion.",
        "verdict": {
            "action": "BUY NOW",
            "micha_meaning": "Eleven of twelve criteria pass — near-perfect technical structure.",
            "peter_meaning": "Exceptional fundamentals; valuation is the only concern at current prices.",
            "short_term": "Momentum favors immediate entry with a target toward $1,400 in 3-6 months.",
            "long_term": "NVIDIA is the picks-and-shovels play for the AI infrastructure buildout through 2030.",
            "accumulation_strategy": "Full position entry on any pullback to the $1,050-$1,100 zone.",
        },
        "cycle_stage": "MID",
        "cycle_stage_reasoning": "NVIDIA is in the mid-cycle acceleration phase with fundamentals matching price action.",
        "buy_zone": {"low": 1050.00, "high": 1100.00, "floor": 980.00},
        "buy_zone_narrative": "The buy zone sits just above the SMA50 and prior breakout level.",
        "price_levels": {
            "price_now": 1148.25, "price_change": -12.50, "price_change_pct": -1.08,
            "price_date": "2026-06-20", "sma50": 1040.00, "sma150": 880.00,
            "price_vs_sma50_pct": 10.4, "price_vs_sma150_pct": 30.5,
            "recent_3m_low": 980.00, "recent_3m_high": 1165.00,
            "prior_3m_low": 750.00, "week_52_low": 495.00,
            "golden_cross_days_ago": 110,
        },
    }

    _newspaper = """MARKET OVERVIEW

Global markets continued their cautious advance as technology stocks led gains amid expectations of easing monetary conditions. Investors weighed a mixed batch of earnings against persistent inflation data that suggests the Federal Reserve may hold rates higher for longer than anticipated.

Apple and NVIDIA remain the headline performers in today's portfolio scan, with both showing strong technical setups alongside impressive fundamental profiles. The broader technology sector is benefiting from renewed appetite for AI infrastructure plays.

PORTFOLIO ANALYSIS

The portfolio maintains a bullish posture with five of eight positions in accumulate or buy territory. The technical breadth remains healthy, with most holdings trading above their key moving averages. Diversification into semiconductors through NVIDIA provides exposure to the secular AI tailwind.

Risk management remains paramount. Investors should scale into positions gradually, respecting the buy zones identified below key technical support levels. The overall risk-reward profile remains favorable given current market dynamics."""

    build_report([_demo_result], [_demo_suggest], _newspaper, "test_report.html")
    print("Written test_report.html — open in a browser to review.")
