# The Wire — Stock Agent · Claude Code Context

## What this project is

An automated daily stock analysis agent built in Python. It analyzes a portfolio
using the **Micha Method** (12-criteria technical scoring) combined with **Peter Lynch
fundamental scoring**, generates a broadsheet newspaper called **"The Wire"**, and
delivers it to Discord via webhook. GitHub Pages hosts the report publicly.

**Owner:** Tal Haran · Tel Aviv, Israel
**Report URL:** https://hatull28.github.io/stock-agent/daily_report.html
**GitHub:** https://github.com/hatull28/stock-agent

---

## How to run

```powershell
# Activate the virtual environment first (every session)
venv\Scripts\activate

# Run the full daily analysis
python run.py

# Or double-click run_agent.bat (runs analysis + git push automatically)
```

---

## Project file map

| File | Role |
|------|------|
| `run.py` | Main orchestrator — runs everything in order |
| `config.py` | Portfolio tickers, watchlist, benchmark |
| `data.py` | yfinance price history fetcher |
| `fundamentals.py` | yfinance fundamental data fetcher |
| `analysis.py` | Micha Method scoring (all 12 criteria) |
| `ai_layer.py` | All AI calls via OpenRouter → DeepSeek |
| `report_builder.py` | HTML broadsheet "The Wire" generator |
| `discord_sender.py` | Discord webhook embed sender |
| `history_manager.py` | Score history save/load (in progress) |
| `run_agent.bat` | Windows launcher: venv + run + git push |
| `diagnostics/verify_c10.py` | Historical diagnostic for criterion 10 |

---

## Portfolio & watchlist

```python
PORTFOLIO = ["AAPL", "NVDA", "MSFT", "GOOGL", "TSM", "AMZN", "ASML", "META"]
WATCHLIST = ["DELL", "INTC", "FSLR", "NKE", "TSLA"]
BENCHMARK = "^GSPC"
```

The agent generates exactly **3 diversifier suggestions** (top 3 by combined score)
from non-tech sectors (Healthcare, Financials, Energy, Consumer Discretionary,
Industrials) to balance the tech-heavy portfolio. WATCHLIST is defined but
currently unused by the pipeline.

---

## The Micha Method (12 criteria)

**Code-computed (deterministic):**
1. Price above SMA150
2. SMA150 slope positive
3. Price above SMA50
4. SMA50 above SMA150
5. Golden cross confirmed (full 25-day window scan, not two-point comparison)
6. ATR shock recent — **upward moves only** (a big down-day does NOT pass)
9. Volume expansion (uses days 21-70 background window, not 50-day rolling avg)
10. Volume dry-up before breakout (same background window)
11. Higher highs & higher lows
12. RS vs S&P500

**AI-judged (DeepSeek via OpenRouter):**
7. Breakout quality
8. Retest quality

**Key decisions:**
- AI temperature = 0.2 for most calls, 0.0 for the combined verdict
- Volume criteria fixed from circular baseline bug (days 21-70 background)
- Golden cross uses full window scan with wobble immunity + persistence check
- ATR shock fixed to directional-only (was counting gap-downs as a pass)

---

## Peter Lynch scoring

10 criteria scored 1–10 by AI from real fundamental data.
Real numbers flow through: pe_ratio, forward_pe, peg_ratio, revenue_growth,
earnings_growth, profit_margin, debt_to_equity, free_cash_flow,
return_on_equity, market_cap.

**4 of 10 criteria have no real data available:**
Moat & Competitive Edge, Management Quality, Industry Strength, Net Income Trend.
These are **pinned to 5 (neutral)** in the prompt — the AI is instructed not to
score them freely, and the summary prose is constrained not to claim moat/management/
industry strength. The panel shows a visible caveat: "moat/mgmt/industry estimated."

**Detail panel has two views:**
- 📊 Expert: real Key Financials table (P/E, PEG, margins, etc.)
- ✍️ Lynch's Take: handwritten Caveat font, aged notepad aesthetic,
  green/amber/red signals per metric with peer comparisons

---

## "The Wire" report design

- Classic broadsheet newspaper aesthetic
- FT-style cream morning edition + dark night terminal edition (toggle)
- Byline "by Tal Haran" in masthead
- Signals strip (colored action pills) below masthead, above the briefing
- Full-width Morning Dispatch (AI briefing as lead article with drop-cap + pull-quote)
- Duck illustration (`assets/duck.png`) in Morning Dispatch sidebar
- Heatmap grid (4-column, each cell = ticker + Micha score + action, colored by verdict)
- Stock cards with Clearbit logos (JS fallback to initials), sparklines (Canvas), score bars, cycle badge, sector ETF badge, buy zone badge
- Slide-out detail panel per stock (click any card)
- Detail panel: Micha checklist, Peter Lynch "handwritten notepad" view, Lynch category tab (floating, right of panel — Stalwart / Fast Grower / etc.), key financials table, verdict section
- Lynch sticker shown inside panel on mobile (tab is hidden on screens ≤600px)
- Mobile-responsive: panel goes full-screen, signals strip wraps, dispatch goes single-column
- Charts (radar + distribution) moved to bottom of page
- GitHub Pages auto-publishes after each run via run_agent.bat

---

## Data integrity — what's real vs AI-generated

This is a quick reference for every number/label visible in the report.

| Field | Source | Notes |
|-------|--------|-------|
| Micha score & criteria | Code (deterministic) | `analysis.py` — all 12 criteria |
| Criteria 7 & 8 (breakout/retest) | AI | DeepSeek; only criteria that are AI-scored |
| Peter Lynch sub-scores | AI (6 real, 4 pinned) | Moat/Mgmt/Industry/NI Trend pinned to 5 |
| Peter Lynch summary prose | AI | Constrained: no unsupported claims |
| Combined action (BUY NOW / WAIT / etc.) | AI | Validated post-call; Micha floor enforced |
| Short/long term prose | AI | Contradiction-checked vs action |
| Accumulation strategy prose | AI | Constrained: no specific dollar prices |
| Buy zone ($X–$Y range) | Code | SMA50 ± 4%, deterministic |
| Cycle stage (EARLY/MID/LATE/NONE) | Code | Deterministic thresholds |
| Sparkline chart | Real data | Last 60 closing prices from yfinance |
| Market index numbers (Dispatch) | Real data | yfinance ^GSPC/^IXIC/^DJI, injected into prompt |
| Peer comparisons (Lynch panel) | Code | JS computes from STOCKS array at render time |
| Lynch category (Stalwart, etc.) | Code | Deterministic thresholds on revenue_growth/earnings_growth/PEG |
| Sector ETF badge (vs XLK, etc.) | Real data | 6-month returns, yfinance |
| 52-week low | Real data | `None` if stock has <252 trading days (IPO/new stock) |
| Morning Dispatch article | AI | Prompted with real criteria pass/fail summary |

**Integrity guardrails now in place:**
- `combined_verdict()` validates `action` against the 4 allowed strings; maps closest match if AI returns something else
- Micha floor rule: Micha ≤ 2 forces AVOID; Micha ≤ 4 downgrades BUY NOW to ACCUMULATE
- Contradiction retry: if `short_term` prose is semantically opposite to `action`, one targeted retry fires to fix only `short_term`
- ATR shock (criterion 6) is directional — only upward moves count
- Buy zone badge shows "Pullback $X–$Y" when price is >12% above the zone ceiling
- `write_newspaper()` receives a criteria pass/fail summary string for each stock so technical narrative is grounded

---

## AI layer (ai_layer.py)

Uses OpenRouter with model `deepseek/deepseek-chat`. Key functions:
- `judge_breakout_and_retest()` — criteria 7 & 8, max_tokens=2000
- `peter_lynch_score()` — 10 Lynch criteria, returns scores + summary
- `combined_verdict()` — final action, temperature=0 for consistency
- `analyze_cycle_and_zones()` — cycle stage + buy zone narrative
- `propose_diversifiers()` — suggests non-tech stocks, excludes holdings
- `write_newspaper()` — AI writes the lead article prose

---

## Environment variables (.env — never commit this)

```
OPENROUTER_API_KEY=sk-or-...
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

---

## What's been built ✅

- Full 12-criteria Micha Method (10 code + 2 AI)
- Peter Lynch fundamental scoring (10 criteria)
- Combined verdict per stock
- Cycle stage (EARLY/MID/LATE/NONE) + buy zone (code-computed, not AI)
- Sector-aware diversifier suggestions (excludes current holdings)
- Sector ETF badge (vs XLK, SOXX, etc.) on each stock card
- Current price + daily change display (▲▼ arrows)
- "The Wire" broadsheet HTML report with theme toggle
- Discord embed delivery with report link
- GitHub Pages auto-publish (run_agent.bat does git push)
- Git version control (clean history)
- Claude Code workflow established (plan mode, review before approve)
- AI temperature tuned (0.2 general, 0.0 verdict)
- Volume criteria fixed (circular baseline bug)
- Golden cross fixed (full window scan)
- Duck illustration in Morning Dispatch sidebar
- Heatmap grid (4-col, color-coded by verdict)
- Clearbit company logos with JS initials fallback
- Lynch category floating tab (Stalwart / Fast Grower / etc.)
- Mobile-responsive layout (full-screen panel, Lynch sticker, single-column dispatch)
- Data integrity audit (11 bugs found and fixed — see Data Integrity section above)
  - ATR shock directional (criterion 6)
  - Sparkline replaced with real 60-day close history
  - Micha score panel/card mismatch fixed (single source of truth)
  - Buy zone badge distance check (shows "Pullback" label when extended)
  - `verdict.action` validated post-call; hard Micha floor enforced
  - Contradiction detection + retry for action vs short_term
  - 4 Peter sub-scores pinned to neutral-5 with UI caveat
  - Peter summary prose constrained (no unsupported claims)
  - `accumulation_strategy` constrained (no invented price targets)
  - `week_52_low` returns None for stocks with <252 trading days
  - `write_newspaper()` receives real criteria pass/fail summary

---

## What's still to build 🔲

- **Score history** — save daily scores to score_history.json, show
  7-day sparklines on stock cards, trend arrows (↑↓→)
- **Unsplash daily image** — fresh photo in the newspaper masthead
- **Portfolio config without editing code** — plain text file for
  adding/removing tickers
- **Backtesting** — test the method against 1000 days of historical data
- **VPS migration** — always-on hosting, eliminates Task Scheduler dependency
- **CLAUDE.md** — this file ✅

---

## Owner preferences & working style

- Prefers visual, designed outputs over dense data tables
- Explain the "why" behind code, not just the "what"
- Use learning mode for new concepts, build mode for execution
- Always show the plan in Claude Code before editing anything
- Commit working code before each new change
- Test on real data before trusting any result
- One feature per commit — clean, isolated history
- This is not financial advice — always include that disclaimer

---

## Common gotchas

- Always activate venv first: `venv\Scripts\activate`
- Python 3.14 on Windows — some libraries may have compatibility quirks
- yfinance sometimes returns NaN for the last row — handled with .dropna()
- score_history.json is in .gitignore (personal data, not for GitHub)
- daily_report.html is NOT in .gitignore — it gets pushed to GitHub Pages
- DeepSeek free tier can be slow; paid tier is faster and more reliable
- AI criteria (7 & 8) can vary slightly run-to-run — this is normal
- run_agent.bat includes git push — don't run it just to test locally
- `run.py` unconditionally commits and pushes at the end of every run, even if nothing changed
- `propose_diversifiers()` in ai_layer.py has dead/unreachable code after `return filtered` (lines ~366-387) — safe to ignore, doesn't affect output
- Peter Lynch sub-scores are 1–10 (not 0–10), so the aggregate is never actually 0; described as "0–10" throughout but minimum is ~1
- `WATCHLIST` in config.py is defined but never imported or used anywhere in the pipeline
- Lynch category can still shift between runs if yfinance TTM data crosses a threshold boundary — this is a data source issue, not a code bug; log `revenue_growth` values if you need to debug it
- `week_52_low` is `None` for stocks with fewer than 252 trading days — display as "N/A" rather than treating it as a price level
- Contradiction retry in `combined_verdict()` is keyword-based — it catches obvious mismatches but won't catch subtle semantic inversions
- The 4 neutral-pinned Peter sub-scores are still averaged into the overall score — the caveat is visible in the UI but the score itself is not restructured
- **SSL on Python 3.14 + Windows**: OpenSSL 3.5.7 (June 2026) can't verify Yahoo Finance's cert chain (server doesn't send intermediates). Fix: `truststore` package injected at the top of `run.py`, plus explicit `requests.Session` passed to every `yf.Ticker()` call in `data.py` and `fundamentals.py` — this bypasses `curl_cffi` (yfinance's preferred backend, which also fails). If you reinstall packages and SSL breaks again, run `pip install truststore`.
- **Windows console encoding**: Python 3.14 defaults to `cp1252` on Windows, which can't encode Unicode chars like `≤`. Fixed by `sys.stdout.reconfigure(encoding="utf-8")` at the top of `run.py`. Don't remove this line.
- `week_52_low` threshold is 245 rows (not 252) — the `requests` backend returns 251 trading days for a 1y period, so 252 would incorrectly return `None` for established stocks
