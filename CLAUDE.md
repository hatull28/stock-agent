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
| `config.py` | Loads portfolio, watchlist, benchmark from `portfolio.json` |
| `portfolio.json` | Editable config: portfolio tickers, watchlist, benchmark |
| `data.py` | yfinance price history fetcher |
| `fundamentals.py` | yfinance fundamental data fetcher |
| `analysis.py` | Micha Method scoring (all 12 criteria) |
| `blind_profiler.py` | Anonymizer for C7/C8 prompts — indexed OHLC, no ticker/dates |
| `ai_layer.py` | All AI calls via OpenRouter → DeepSeek |
| `ledger.py` | Append-only prediction ledger writer (research_data.json) |
| `report_builder.py` | HTML broadsheet "The Wire" generator |
| `discord_sender.py` | Discord webhook embed sender |
| `history_manager.py` | Score history save/load (score_history.json, 30-entry rolling cap) |
| `run_agent.bat` | Windows launcher: venv + run + git push |
| `diagnostics/verify_c10.py` | Historical diagnostic for criterion 10 |
| `diagnostics/leak_check.py` | Adversarial audit — proves blind profiler prevents ticker ID |
| `diagnostics/stability_check.py` | Score-flip diagnostic — profiles hash + criterion pass rates |

---

## Portfolio & watchlist

Configured via `portfolio.json` — edit this file to add/remove tickers, no code change needed.

```json
{
  "portfolio": ["AAPL", "NVDA", "MSFT", "GOOGL", "TSM", "AMZN", "ASML", "META", "JPM"],
  "watchlist": ["DELL", "INTC", "FSLR", "NKE", "TSLA", "NVO"],
  "benchmark": "^GSPC"
}
```

The agent generates exactly **3 diversifier suggestions** (top 3 by combined score)
from non-tech sectors (Healthcare, Financials, Energy, Consumer Discretionary,
Industrials) to balance the tech-heavy portfolio.

**Watchlist** tickers are now fully wired through the pipeline — analyzed with the same
Micha + Lynch scoring as the portfolio, shown in a "Watchlist Dispatches" section of the
report, and written to the prediction ledger with `"held": false`. Portfolio tickers get
`"held": true` in the ledger. This enables clean pre-purchase vs held analysis in research_data.json.

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
- C7/C8 prompts are **anonymized** via `blind_profiler.py` — no ticker symbol, no calendar
  dates, no absolute prices. OHLC is indexed to Day 1 Close = 100.00; volume is a ratio
  of the 40-day mean. Adversarial leak check (diagnostics/leak_check.py) confirmed 0/40
  identification rate vs 40/40 for the control. Score variance (C7/C8) at temperature 0.2
  is expected and benign — confirmed by stability_check.py.

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
- **Config staleness nag box** — appears immediately below masthead; lists holdings +
  watchlist tickers and when `portfolio.json` was last saved. Switches to amber warning
  if mtime > 30 days (dark-mode aware).
- Signals strip (colored action pills) below masthead, above the briefing
- Daily Unsplash photo in the masthead hero (fetched fresh each run)
- Full-width Morning Dispatch (AI briefing as lead article with drop-cap + pull-quote)
- Duck illustration (`assets/duck.png`) in Morning Dispatch sidebar
- Heatmap grid (4-column, each cell = ticker + Micha score + action, colored by verdict)
- Stock cards with Clearbit logos (JS fallback to initials), sparklines (Canvas), score bars, cycle badge, sector ETF badge, buy zone badge
- Slide-out detail panel per stock (click any card)
- Detail panel: Micha checklist, Peter Lynch "handwritten notepad" view, Lynch category tab (floating, right of panel — Stalwart / Fast Grower / etc.), key financials table, verdict section
- Lynch sticker shown inside panel on mobile (tab is hidden on screens ≤600px)
- Mobile-responsive: panel goes full-screen, signals strip wraps, dispatch goes single-column
- **Section order:** Portfolio Dispatches → Diversifier Dispatches → **Watchlist Dispatches** → Portfolio Breakdown charts
- Watchlist Dispatches: full `_stock_card()` cards (same as portfolio — sparklines, history, detail panel)
- Charts (radar + distribution) at bottom of page; radar/dist use only portfolio tickers (`PORTFOLIO_COUNT`)
- GitHub Pages auto-publishes after each run via `run.py` git push

---

## Data integrity — what's real vs AI-generated

This is a quick reference for every number/label visible in the report.

| Field | Source | Notes |
|-------|--------|-------|
| Micha score & criteria | Code (deterministic) | `analysis.py` — all 12 criteria |
| Criteria 7 & 8 (breakout/retest) | AI | DeepSeek; anonymized blind profile; only AI-scored criteria |
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
| Morning Dispatch article | AI | Prompted with real criteria pass/fail summary + watchlist data |
| Blind profile hash | Code | SHA-256 of indexed OHLC rows; stored in ledger for tamper evidence |
| Run digest (Discord footer) | Code | SHA-256 of sorted ticker:profile_hash pairs, first 12 chars |

**Integrity guardrails now in place:**
- `combined_verdict()` validates `action` against the 4 allowed strings; maps closest match if AI returns something else
- Micha floor rule: Micha ≤ 2 forces AVOID; Micha ≤ 4 downgrades BUY NOW to ACCUMULATE
- Contradiction retry: if `short_term` prose is semantically opposite to `action`, one targeted retry fires to fix only `short_term`
- ATR shock (criterion 6) is directional — only upward moves count
- Buy zone badge shows "Pullback $X–$Y" when price is >12% above the zone ceiling
- `write_newspaper()` receives a criteria pass/fail summary string for each stock so technical narrative is grounded
- C7/C8 prompts anonymized — ticker identity cannot leak into AI judgment (proved by leak_check.py)
- Prediction ledger (`research_data.json`) is append-only JSONL committed to git; Discord footer carries run timestamp + digest as external witness

---

## AI layer (ai_layer.py)

Uses OpenRouter with model `deepseek/deepseek-chat`. Key functions:
- `judge_breakout_and_retest()` — criteria 7 & 8, anonymized blind profile, max_tokens=2000
- `peter_lynch_score()` — 10 Lynch criteria, returns scores + summary
- `combined_verdict()` — final action, temperature=0 for consistency
- `analyze_cycle_and_zones()` — cycle stage + buy zone narrative
- `propose_diversifiers()` — suggests non-tech stocks, excludes holdings
- `write_newspaper(portfolio_results, suggestions, watchlist_results=None)` — AI writes the lead article prose

---

## Prediction ledger (research_data.json)

Append-only JSONL file committed to git after every run. One line per ticker per run.

Key fields per entry:
- `run_ts` — ISO 8601 UTC timestamp (same value used in Discord footer)
- `ticker`, `date`, `method` ("blind")
- `micha_score`, `micha_criteria` (all 12 pass/fail)
- `micha_reason_7`, `micha_reason_8` — AI rationale strings for C7/C8
- `profile_hash` — SHA-256 of the blind OHLC profile (tamper evidence)
- `peter_score`, `peter_scores` — Lynch aggregate + per-criterion breakdown
- `lynch_category` — deterministic label (Hidden Gem / Fast Grower / Stalwart / etc.)
- `held` — `true` if ticker is in PORTFOLIO at run time, `false` if watchlist or suggestion
- `source` — `"portfolio"` / `"watchlist"` / `"suggestion"`; absent on pre-source-field entries (legacy)
- `action` — final combined verdict

`held` and `source` answer different forward-test questions. `held` is the simple pre-purchase
vs held split. `source` separates watchlist (stocks you chose to watch) from suggestions (stocks
the AI proposed) — these are different bets and the forward test should tell them apart.

A ticker moving from watchlist → portfolio produces a clean era split: `held=false, source="watchlist"`
entries are pre-purchase predictions uncontaminated by anchoring; `held=true, source="portfolio"`
entries begin when capital is committed.

**Digest coverage:** The Discord digest fingerprints all entries for a run. `verify_witness.py`
detects the era automatically: if any entry has `source`, all entries are in the digest (new era);
if no entry has `source`, only portfolio + suggestions were covered (legacy era, with a warning).

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
- GitHub Pages auto-publish (`run.py` git push at end of every run)
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
- **Blind profiler** (`blind_profiler.py`) — C7/C8 prompts anonymized; adversarial leak check
  proved 0/40 identification rate; stability_check.py confirmed score variance is C7/C8 only
- **Prediction ledger** (`research_data.json`) — append-only JSONL, committed to git;
  `"held"` field tags portfolio vs watchlist/suggestion entries
- **Discord run digest** — SHA-256 fingerprint of ticker:profile_hash pairs in embed footer;
  run_ts shared between ledger and Discord for cross-referencing
- **Watchlist pipeline** — WATCHLIST fully analyzed each run (Micha + Lynch + verdict);
  "Watchlist Dispatches" section in report with full stock cards; included in AI briefing
- **Config staleness nag** — box below masthead showing portfolio.json mtime; amber warning
  if >30 days stale
- **portfolio.json config** — portfolio and watchlist editable without touching code
- **Unsplash daily masthead image** — fresh photo fetched each run via `unsplash_layer.py`
- **Score history + sparklines** — daily Micha scores saved to `score_history.json` (30-entry
  rolling cap per ticker, method: "blind"); 7-day SVG polyline sparklines and ↑↓→ trend arrows
  render on every stock card (`_score_sparkline_svg()` / `_trend_arrow()` in report_builder.py)
- **`source` field on ledger entries** — `"portfolio"` / `"watchlist"` / `"suggestion"` on every
  entry; enables forward-test queries that separate watched stocks from AI-proposed stocks
- **Full digest coverage** — Discord digest now fingerprints all 18 entries per run (portfolio +
  suggestions + watchlist); `verify_witness.py` auto-detects era via `source` field presence

---

## What's still to build 🔲

- **Backtesting** — test the method against 1000 days of historical data
- **VPS migration** — always-on hosting, eliminates Task Scheduler dependency
- **Portfolio Sandbox** *(parked — open design questions unresolved)*
  An interactive page, separate from the daily broadsheet, for testing how candidate
  additions change the portfolio's shape. Toggle watchlist names on/off and see the effect
  live. Open questions before building: (a) What does it measure? Sector weights are easy
  and shallow; return correlation across holdings is honest and real work. (b) Where does
  it live — a second generated HTML page, a section of the daily report, or opened on
  demand? (c) What does "playable" mean concretely — client-side JS with pre-computed
  data baked in at generation time? Do not build until these are answered.
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
- `score_history.json` is in .gitignore (personal data, not for GitHub)
- `research_data.json` is NOT in .gitignore — it is committed to git as the prediction ledger
- `daily_report.html` is NOT in .gitignore — it gets pushed to GitHub Pages
- DeepSeek free tier can be slow; paid tier is faster and more reliable
- AI criteria (7 & 8) can vary slightly run-to-run — this is normal and expected (temperature 0.2);
  confirmed by stability_check.py that all deterministic criteria are 0/N or N/N
- `run.py` unconditionally commits and pushes at the end of every run, even if nothing changed
- `propose_diversifiers()` in ai_layer.py has dead/unreachable code after `return filtered` — safe to ignore
- Peter Lynch sub-scores are 1–10 (not 0–10), so the aggregate is never actually 0; described as "0–10" throughout but minimum is ~1
- Lynch category can still shift between runs if yfinance TTM data crosses a threshold boundary — this is a data source issue, not a code bug
- `week_52_low` is `None` for stocks with fewer than 245 trading days — display as "N/A"
- `week_52_low` threshold is 245 rows (not 252) — the `requests` backend returns 251 trading days for a 1y period
- Contradiction retry in `combined_verdict()` is keyword-based — catches obvious mismatches but not subtle semantic inversions
- The 4 neutral-pinned Peter sub-scores are still averaged into the overall score — caveat is visible in UI but score is not restructured
- `ledger.py` uses `json.dumps(..., default=_json_default)` to handle numpy int64/float64 types from analysis.py — do not remove the default handler
- `_held` flag is set on result dicts in `run.py` **before** `append_run()` is called — portfolio gets `True`, watchlist + suggestions get `False`
- Watchlist tickers that are also in PORTFOLIO are silently skipped in Part D of `run_daily_analysis()` (guard: `if ticker in PORTFOLIO: continue`)
- **SSL on Python 3.14 + Windows**: OpenSSL 3.5.7 (June 2026) can't verify Yahoo Finance's cert chain (server doesn't send intermediates). Fix: `truststore` package injected at the top of `run.py`, plus explicit `requests.Session` passed to every `yf.Ticker()` call in `data.py` and `fundamentals.py` — this bypasses `curl_cffi` (yfinance's preferred backend, which also fails). If you reinstall packages and SSL breaks again, run `pip install truststore`.
- **Windows console encoding**: Python 3.14 defaults to `cp1252` on Windows, which can't encode Unicode chars like `≤`. Fixed by `sys.stdout.reconfigure(encoding="utf-8")` at the top of `run.py`. Don't remove this line.
