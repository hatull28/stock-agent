# Stock Agent

An AI-powered daily stock analysis agent that combines technical and fundamental scoring to rank portfolio holdings and surface diversification candidates. Results are delivered as a styled HTML report and a Discord embed.

## How it works

Each run analyses every stock in the configured portfolio through two lenses:

**Micha Method (technical, 0–12 points)**
Twelve binary criteria covering price/SMA relationships, golden cross, ATR shock, volume patterns, higher highs/lows, and relative strength. Criteria 1–6 and 9–12 are evaluated in code; criteria 7–8 (breakout quality and retest) are judged by an LLM.

**Peter Lynch score (fundamental, 0–10 points)**
An LLM scores ten fundamental criteria (PEG ratio, revenue/earnings growth, margins, debt, FCF yield, ROE, etc.) on a 1–10 scale each, using live data from yfinance.

**Combined verdict**
A final LLM call synthesises both scores and outputs one of: `BUY NOW`, `WAIT FOR PULLBACK`, `ACCUMULATE`, or `AVOID`, plus short- and long-term outlooks and an accumulation strategy.

The agent also asks the LLM to propose diversification candidates from underrepresented sectors, scores those the same way, then ranks everything by `(micha_scaled + peter) / 2`.

## File structure

```
stock-agent/
├── run.py               # Entry point — runs the full daily pipeline
├── config.py            # PORTFOLIO, WATCHLIST, BENCHMARK constants
├── data.py              # yfinance OHLCV price-history fetcher
├── fundamentals.py      # yfinance fundamental metrics (PE, PEG, margins, …)
├── analysis.py          # Micha Method scoring engine (12 criteria)
├── ai_layer.py          # LLM calls via OpenRouter → Deepseek Chat
├── report_builder.py    # Builds daily_report.html (night-mode terminal theme)
├── discord_sender.py    # Posts rich embed to Discord webhook
├── run_agent.bat        # Windows shortcut: activates venv then runs run.py
├── requirements.txt
├── .env                 # API keys (not committed)
└── diagnostics/
    └── verify_c10.py    # Historical backtest of criterion 10 (volume dryup)
```

## Setup

**Requirements:** Python 3.14+

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
OPENROUTER_API_KEY=your_openrouter_key_here
DISCORD_WEBHOOK_URL=your_discord_webhook_url_here
```

- **OPENROUTER_API_KEY** — get one at openrouter.ai; the agent routes to `deepseek/deepseek-chat`
- **DISCORD_WEBHOOK_URL** — create a webhook in Discord under channel settings → Integrations

## Running

```bash
python run.py
```

Or on Windows, double-click `run_agent.bat` (activates the venv automatically).

## Output

| File | Description |
|---|---|
| `daily_report.html` | Full visual report — open in any browser |
| Discord embed | Summary card sent to your configured channel |

Both are regenerated on every run and are not committed to git.

## Diagnostics

`diagnostics/verify_c10.py` backtests criterion 10 (volume dryup) across the last 252 trading days for every ticker, reporting fire rate, ratio ranges, and data-quality warnings. Run it from the project root:

```bash
python diagnostics/verify_c10.py
```
