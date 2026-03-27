---
name: johan-ig-trader
description: Johan's personal IG trading bot for CFDs, forex, and equity derivatives. Supports momentum and mean reversion strategies with LLM sentiment analysis on IG. Includes stop-loss/take-profit, cooldown, and daily loss limits. Use when user wants to trade on IG Markets, set up automated CFD trading, or needs to run the IG trading bot on this machine. Requires IG API credentials.
---

# Johan's IG Trader

Autonomous trading bot for IG Markets (CFDs, forex, and equity derivatives) with **news sentiment integration** for smarter trading decisions.

## Quick Start

### 1. Configure

Create `.env` file in the skill directory:
```
IG_API_KEY=<your-api-key>
IG_ACCOUNT_ID=<your-account-id>
IG_PASSWORD=<your-password>
IG_BASE_URL=https://demo-api.ig.com/gateway/deal  # Use demo for testing

# Optional: Ollama for sentiment
USE_LLM=true
OLLAMA_MODEL=deepseek-v3.2:cloud
OLLAMA_BASE_URL=http://127.0.0.1:11434

# Trading parameters
EPICS=IX.D.DAX.IFG.IP,IX.D.SPTRD.IFE.IP,CS.D.EURUSD.MINI.IP
STRATEGY=momentum
TRADE_SIZE_PCT=1
MAX_POSITIONS=3
STOP_LOSS_PCT=2
TAKE_PROFIT_PCT=3
COOLDOWN_HOURS=6
MAX_DAILY_LOSS_PCT=2
ALLOW_SHORT=false  # Enable short selling for SELL signals

# News/Sentiment configuration
SENTIMENT_STALE_HOURS=6      # Max age of sentiment data before it's considered stale
SENTIMENT_THRESHOLD=0.3        # Minimum sentiment strength to consider
```

### 2. Setup

```bash
bash {baseDir}/scripts/setup.sh
```

### 3. Run

**Basic run:**
```bash
python3 {baseDir}/scripts/trader.py
```

**Via cron:**
```
*/5 * * * * cd {baseDir} && python3 scripts/trader.py >> trader.log 2>&1
```

---

## News Trading Features

The bot integrates with a news sentiment scraper to make smarter trading decisions based on market news.

### How It Works

1. **Decision Engine** (`decision_engine.py`) - Combines technical indicators with news sentiment
2. **Sentiment Integration** (`sentiment_integration.py`) - Reads sentiment data from news scraper
3. **News Scraper** (`ig_news_scraper.py`) - Fetches and analyzes financial news

### Market Support

The bot supports sentiment analysis for these markets:

| Epic | Market |
|------|--------|
| `IX.D.DAX.IFG.IP` | DAX (Germany 40) |
| `IX.D.SPTRD.IFE.IP` | S&P 500 |
| `IX.D.NASDAQ.IFE.IP` | NASDAQ 100 |
| `CS.D.EURUSD.MINI.IP` | EUR/USD Mini |
| `CS.D.GOLD.CFD.IP` | Gold |
| `CF.D.LCO.USD.IP` | Oil (Brent) |

---

## Running the News Scraper

### Prerequisites

The news scraper requires Python dependencies:
```bash
pip3 install requests beautifulsoup4 textblob
```

For enhanced sentiment analysis, download NLTK data:
```bash
python3 -c "import nltk; nltk.download('vader_lexicon')"
```

### Manual Run

Run the news scraper before trading to fetch fresh sentiment:

```bash
cd {baseDir}/scripts
python3 ig_news_scraper.py
```

This creates:
- `data/news_sentiment.json` - Latest sentiment signals
- `data/news_sentiment_report.json` - Detailed sentiment report
- `data/sentiment_history.jsonl` - Historical sentiment data

### Automated Scheduling

**Option 1: Combined cron job (recommended)**
```bash
# Fetch news then trade
*/10 * * * * cd {baseDir}/scripts && python3 ig_news_scraper.py >> ../news.log 2>&1 && python3 trader.py >> ../trader.log 2>&1
```

**Option 2: Separate jobs**
```bash
# Fetch news every 30 minutes
*/30 * * * * cd {baseDir}/scripts && python3 ig_news_scraper.py >> ../news.log 2>&1

# Trade every 5 minutes (uses cached sentiment)
*/5 * * * * cd {baseDir}/scripts && python3 trader.py >> ../trader.log 2>&1
```

### Configuration Options

Add to `.env`:

```bash
# Sentiment staleness threshold (hours)
# If sentiment data is older than this, it's ignored
SENTIMENT_STALE_HOURS=6

# Minimum sentiment strength to consider trading
# Range: 0.0 to 1.0 (lower = more sensitive)
SENTIMENT_THRESHOLD=0.3
```

---

## Decision Engine

The Decision Engine combines **60% technical analysis** with **40% news sentiment** to generate trading signals.

### Technical Factors (60% weight)

- **EMA Crossover** (35%) - Fast vs slow EMA comparison
- **RSI Levels** (25%) - Overbought/oversold detection
- **Bollinger Bands** (20%) - Price position relative to bands
- **Trend Direction** (20%) - Up/down/sideways classification

### Sentiment Factors (40% weight)

- News sentiment score (-1 to +1)
- Confidence level
- Key trading signals (bullish/bearish keywords)

### Signal Output

```
SIGNAL: STRONG_BUY | BUY | NEUTRAL | SELL | STRONG_SELL

Additional fields:
- strength: Combined score (-1 to +1)
- confidence: Overall confidence (0-1)
- should_trade: Boolean - only trade when True
- reason: Human-readable explanation
- technical_score: Technical component
- sentiment_score: Sentiment component
```

### Example Trade Decision

When technical analysis shows a BUY signal but news sentiment is strongly bearish:
- `should_trade = False` - Trade is blocked
- Reason: "Technical BUY conflicts with BEARISH sentiment"

When technical and sentiment align (e.g., BUY + BULLISH):
- `should_trade = True` - Trade proceeds
- Reason: "Technical BUY aligned with BULLISH sentiment"

---

## Strategies

### momentum (default)
- Uses proper Exponential Moving Average (EMA) calculation
- Buys when EMA(9) crosses above EMA(20)
- Sells when EMA(9) crosses below EMA(20)
- Enhanced with sentiment filtering via Decision Engine

### mean_reversion
- Calculates RSI (14-period)
- Finds support/resistance levels
- Buys when RSI < 30 near support (oversold)
- Sells when RSI > 70 near resistance (overbought)

---

## Features

### News-Enhanced Trading
- Fetches financial news from multiple sources
- Analyzes sentiment using TextBlob/VADER
- Blocks trades when news contradicts technical signals
- Boosts confidence when technical and news align

### Stop-Loss & Take-Profit
- Automatically attached to new positions
- Configurable via `STOP_LOSS_PCT` and `TAKE_PROFIT_PCT`

### Session Token Refresh
- Automatically refreshes IG session tokens before expiry (~10 minutes)

### Cooldown Enforcement
- Prevents re-trading the same instrument within `COOLDOWN_HOURS`
- Tracks in `cooldown.json`

### Daily Loss Limit
- Stops trading when `MAX_DAILY_LOSS_PCT` of balance is lost
- Tracks in `daily_loss.json`

### Trade Size Validation
- Validates position sizes against IG minimums
- Adjusts automatically or skips if below minimum

### Short Selling Support
- Enable with `ALLOW_SHORT=true`
- Opens short positions on SELL signals when no long position exists

---

## IG Epic Examples

- `IX.D.DAX.IFG.IP` — Germany 40 (DAX)
- `IX.D.SPTRD.IFE.IP` — S&P 500
- `CS.D.EURUSD.MINI.IP` — EUR/USD Mini
- `IX.D.NASDAQ.IFE.IP` — NASDAQ 100

See `references/epics.md` for full list.

---

## Files

### Core Scripts
- `scripts/trader.py` — Main trading bot with decision engine integration
- `scripts/decision_engine.py` — Combines technical + sentiment signals
- `scripts/sentiment_integration.py` — Reads sentiment data
- `scripts/ig_news_scraper.py` — Fetches and analyzes financial news
- `scripts/setup.sh` — Environment setup

### Data Files
- `data/news_sentiment.json` — Latest sentiment signals
- `data/news_sentiment_report.json` — Detailed sentiment report
- `data/sentiment_history.jsonl` — Historical sentiment data
- `trades.jsonl` — Trade history with news context
- `cooldown.json` — Cooldown tracking
- `daily_loss.json` — Daily loss tracking

### Logs
- `trader.log` — Trading bot runtime logs
- `news.log` — News scraper logs

### Reference
- `references/ig-api.md` — IG REST API documentation
- `references/epics.md` — Common epic codes

---

## Security Notes

- Use DEMO account first to test
- IG credentials are session-based and expire (~10 min)
- Session tokens automatically refresh
- Monitor positions regularly
- News sentiment is advisory only - final trading decision combines multiple factors

---

## Sentiment Workflow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  News Scraper   │────▶│ Sentiment Files  │────▶│ Decision Engine │
│  (ig_news_)     │     │ (data/*.json)    │     │ (decision_)     │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                        │
                               ┌──────────────────────┘
                               ▼
                        ┌─────────────────┐
                        │  Trader Bot     │
                        │  (trader.py)    │
                        └─────────────────┘
```

1. **News Scraper** runs periodically (cron) to fetch fresh news
2. **Sentiment files** store analyzed sentiment data
3. **Decision Engine** combines sentiment with technical analysis
4. **Trader Bot** uses the combined signal to make trades

---

## References

- `references/ig-api.md` - IG REST API documentation
- `references/epics.md` - Common epic codes
