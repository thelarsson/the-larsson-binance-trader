## ⚠️ Legal Disclaimer

The use of this software is entirely at your own risk. The developer shall not be held liable for any direct, indirect, incidental, or consequential losses arising from the use of this trading bot.

This bot does not provide financial advice, and no guarantees are made regarding profitability, performance, or accuracy of its strategies or signals.

By using this software, you agree that you are fully responsible for your trading decisions and any outcomes resulting from them.



The Larsson Binance Trader

Autonomous spot trading bot for Binance with LLM sentiment analysis, auto-discovery of trading opportunities, and Telegram integration.
Features

    Multiple Strategies: momentum, mean_reversion, DCA
    Auto-Discovery: Automatically finds high-potential trading pairs based on technical + sentiment scores
    News Sentiment: Integrates crypto news analysis for smarter trading decisions
    Risk Management: Stop-loss, take-profit, daily loss limits, position sizing
    Telegram Bot: Real-time notifications and commands
    Position Sync: Always uses Binance as source of truth (handles manual trades)
    Dust Filtering: Ignores positions under $1 USD (staking rewards, etc.)

Architecture

┌─────────────────┐     ┌──────────────────┐     ┌─────────────┐
│   Telegram Bot  │────▶│  Trading Bot     │────▶│   Binance   │
│   (commands)    │     │  (decision)      │     │   (trades)  │
└─────────────────┘     └──────────────────┘     └─────────────┘
                              │
                              ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────┐
│  News Scraper   │────▶│  Discovery Engine│────▶│  Sentiment  │
│  (hourly)       │     │  (opportunities) │     │  Analysis   │
└─────────────────┘     └──────────────────┘     └─────────────┘

Key Principle: Binance is the source of truth for positions. The bot checks your actual Binance account every cycle.
Quick Start
1. Configure

Create .env file:

# Binance API (REQUIRED)
BINANCE_API_KEY=<your-api-key>
BINANCE_SECRET_KEY=<your-secret-key>

# LLM Configuration (optional - for sentiment analysis)
OPENAI_API_KEY=<optional-openai-key>
OLLAMA_MODEL=<optional-ollama-model>
OLLAMA_BASE_URL=http://127.0.0.1:11434

# Trading Pairs
PAIRS=BTCUSDT,ETHUSDT,SOLUSDT

# Strategy: momentum | mean_reversion | dca
STRATEGY=momentum

# Risk Management
TRADE_SIZE_PCT=1              # % of balance per trade
MAX_POSITIONS=2               # Max concurrent positions
STOP_LOSS_PCT=2               # Stop loss %
TAKE_PROFIT_PCT=3             # Take profit %
COOLDOWN_HOURS=12             # Hours between trades on same pair
MAX_DAILY_LOSS_PCT=2          # Daily loss limit
USDT_RESERVE_PCT=40           # % of balance to keep in reserve

# Auto-Discovery
USE_AUTO_DISCOVERY=true       # Enable discovery
DISCOVERY_AUTO_ADD=true       # Auto-add high-scoring pairs
DISCOVERY_MIN_SCORE=0.3       # Minimum score to add (0-1)

# Telegram Bot (optional)
TELEGRAM_BOT_TOKEN=<your-bot-token>
TELEGRAM_CHAT_ID=<your-chat-id>

2. Setup

bash {baseDir}/scripts/setup.sh

3. Run

Option A: Continuous mode (recommended)

bash {baseDir}/scripts/trader_continuous.sh

Option B: Single cycle (for testing)

python3 {baseDir}/scripts/trader.py

Option C: Cron

*/5 * * * * cd {baseDir} && python3 scripts/trader.py >> trader.log 2>&1

Telegram Bot Commands

Send these commands to your Telegram bot:
Command 	Description
/status 	Full bot status, balance, positions
/positions 	Show active positions (synced with Binance)
/balance 	USDT balance (live from Binance)
/uptime 	Bot uptime
/sentiment 	News sentiment report
/discovery 	Trading opportunities from discovery
/sync 	Sync/verify positions with Binance
/help 	Commands list
Strategies
Momentum (default)

    Entry: Price above slow EMA + fast EMA crossing above slow EMA + bullish higher timeframe
    Exit: Price below EMA or stop-loss/take-profit triggered
    Best for: Trending markets

Mean Reversion

    Entry: RSI < 30 (oversold) near lower Bollinger Band
    Exit: RSI > 70 or upper Bollinger Band
    Best for: Ranging markets

DCA

    Entry: Fixed interval buying regardless of price
    Exit: Configured take-profit levels
    Best for: Long-term accumulation

How Position Tracking Works

    Source of Truth: Binance API is always checked first
    Dust Filter: Positions under $1 USD are ignored (staking rewards, etc.)
    Sync: If you sell manually on Binance, bot treats local position as "closed"
    Logging: trades.jsonl tracks history but is NOT used for trading decisions

Example: If you have 0.001 BTC worth $68 → counted as position. If you have 0.00001 BTC worth $0.50 → ignored.
Auto-Discovery

The bot can automatically find and trade high-potential pairs:

    Scans top coins by volume
    Analyzes technical indicators (EMA, RSI, volume)
    Checks news sentiment for each coin
    Scores opportunities (0-1 scale)
    Auto-adds pairs with score ≥ DISCOVERY_MIN_SCORE

Discovery updates hourly via cron job.
Configuration Reference
Variable 	Default 	Description
STRATEGY 	momentum 	Trading strategy
MAX_POSITIONS 	2 	Max open positions
TRADE_SIZE_PCT 	1 	Position size as % of balance
STOP_LOSS_PCT 	2 	Stop loss percentage
TAKE_PROFIT_PCT 	3 	Take profit percentage
COOLDOWN_HOURS 	12 	Min hours between trades
MAX_DAILY_LOSS_PCT 	2 	Daily loss limit
USDT_RESERVE_PCT 	40 	% of balance to reserve
DISCOVERY_MIN_SCORE 	0.3 	Min score to auto-add pairs
USE_LLM 	true 	Enable LLM sentiment
USE_DECISION_ENGINE 	true 	Enable sentiment + technical combo
DECISION_SENTIMENT_WEIGHT 	0.4 	Weight of news sentiment (0-1)
Files

    scripts/trader.py — Main trading bot
    scripts/trader_continuous.sh — Continuous runner
    scripts/telegram_bot.py — Telegram bot
    scripts/auto_discovery.py — Discovery integration
    trades.jsonl — Trade history (not used for decisions)
    trader.log — Runtime logs
    .env — Configuration

Security Notes

    NEVER enable withdrawal permissions on API keys
    IP-restrict keys on Binance to your server IP
    Keep .env file secure (never commit to git)
    Start with small amounts, test thoroughly
    The bot only places orders - you maintain full control

Troubleshooting
Bot shows "Not running" for /uptime

The Telegram bot looks for the trader process. If using trader_continuous.sh, it should find it automatically.
Positions not matching Binance

The bot checks Binance every cycle. If you trade manually, the bot will detect the change next cycle and log "Treating as closed."
No discovery opportunities above threshold

Discovery scores change with market conditions. Lower DISCOVERY_MIN_SCORE to see more opportunities, or wait for better setups.
Staking rewards showing as positions

Fixed - the bot now filters out all positions under $1 USD (including LD-prefixed staking rewards).
References

    See references/binance-api.md for API documentation
    See references/indicators.md for technical analysis details
    Discovery data: /home/johan/.openclaw/workspace/crypto-news-scraper/
