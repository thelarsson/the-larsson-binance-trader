# The Larsson Binance Trader - Complete Documentation

## Overview

An AI-powered cryptocurrency trading bot that combines technical analysis, sentiment analysis from news sources, and automatic market discovery to identify optimal trading opportunities on Binance.

## Table of Contents

1. [Architecture](#architecture)
2. [Features](#features)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Trading Strategies](#trading-strategies)
6. [Commands](#commands)
7. [Automation](#automation)
8. [Troubleshooting](#troubleshooting)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    TRADING BOT SYSTEM                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  News Scraper │  │    Decision   │  │   Discovery   │      │
│  │   (Python)    │──│    Engine     │──│    Engine     │      │
│  │  AgentBrowser │  │   Technical   │  │   Binance     │      │
│  └──────────────┘  │   + Sentiment │  │   Scanner     │      │
│         │          └──────────────┘  └──────────────┘      │
│         │                   │                   │              │
│         ▼                   ▼                   ▼              │
│  ┌────────────────────────────────────────────────────┐   │
│  │              Trading Bot (Python)                   │   │
│  │         Binance API • Risk Management            │   │
│  │         Dynamic PAIRS Selection                  │   │
│  └────────────────────────────────────────────────────┘   │
│                            │                               │
│                            ▼                               │
│  ┌────────────────────────────────────────────────────┐   │
│  │           Telegram Bot (Real-time)                │   │
│  │    /status • /positions • /balance              │   │
│  │    /sentiment • /discovery • /uptime              │   │
│  └────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Features

### Core Capabilities
- **AI Sentiment Analysis**: Analyzes CoinDesk news using local LLM (llama3.2:3b)
- **Technical Analysis**: EMA, RSI, Bollinger Bands, volume analysis
- **Auto-Discovery**: Automatically discovers and ranks new trading pairs
- **Telegram Integration**: Real-time notifications and status commands
- **Local LLM Execution**: Runs entirely on your machine (zero API costs)
- **Risk Management**: Stop-loss, take-profit, daily loss limits
- **Dynamic Pair Selection**: Automatically updates PAIRS list based on performance

### Trading Strategies
- **Momentum**: Follows market trends using EMA crossover
- **Mean Reversion**: Trades overbought/oversold levels
- **DCA (Dollar Cost Averaging)**: Regular interval purchasing

## Installation

### Prerequisites
```bash
# Python 3.8+
pip install httpx python-dotenv

# Ollama (for local LLM)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2:3b
```

### Setup
```bash
cd trading-bots/johan-binance-trader
cp .env.example .env
# Edit .env with your API keys
```

### Start the Bot
```bash
# Start trading bot (runs every 60 seconds)
./scripts/trader_continuous.sh

# Start Telegram bot (in separate terminal)
python3 scripts/telegram_bot.py
```

## Configuration

### Environment Variables (.env)

```bash
# Binance API
BINANCE_API_KEY=your_api_key
BINANCE_SECRET_KEY=your_secret

# Trading Parameters
PAIRS=BTCUSDT,ETHUSDT,SOLUSDT          # Dynamically updated hourly!
STRATEGY=momentum
TRADE_SIZE_PCT=15
MAX_POSITIONS=2
STOP_LOSS_PCT=2
TAKE_PROFIT_PCT=3

# LLM (Ollama)
OLLAMA_MODEL=llama3.2:3b
OLLAMA_BASE_URL=http://127.0.0.1:11434
USE_LLM=true

# Decision Engine
USE_DECISION_ENGINE=true
DECISION_SENTIMENT_WEIGHT=0.4

# Discovery & Dynamic Pairs
USE_AUTO_DISCOVERY=true
DISCOVERY_MIN_SCORE=0.05              # Lower threshold for more pairs
DISCOVERY_AUTO_ADD=false              # Manual approval recommended

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

## Trading Strategies

### Decision Process

```
Strategy Signal (e.g., Momentum)
           ↓
    ┌──────────────┐
    │  Risk Check  │ ← Cooldown? Max positions? Daily loss?
    └──────────────┘
           ↓
    ┌──────────────┐
    │   Decision   │ ← Technical (60%) + Sentiment (40%)
    │    Engine    │
    └──────────────┘
           ↓
    ┌──────────────┐
    │  LLM Sentiment│ ← llama3.2:3b analyzes market data
    │  (if enabled) │
    └──────────────┘
           ↓
    ┌──────────────┐
    │    Trade?    │ ← Yes/No based on combined score
    └──────────────┘
```

### Technical Indicators

| Indicator | Weight | Description |
|-----------|--------|-------------|
| EMA Crossover | 30% | Fast vs Slow EMA comparison |
| RSI | 25% | Overbought/Oversold detection |
| Bollinger Bands | 15% | Price position within bands |
| Volume Trend | 10% | Increasing/Decreasing volume |
| Price Change | 10% | 24-hour change percentage |

## Commands

### Telegram Bot Commands

| Command | Description |
|---------|-------------|
| `/status` | Full bot status with positions, balance, uptime |
| `/positions` | Active positions with PnL (synced with Binance) |
| `/balance` | USDT balance (live from Binance) |
| `/pairs` | Show current PAIRS list |
| `/sync` | Sync/verify positions with Binance |
| `/uptime` | Bot runtime |
| `/sentiment` | Market sentiment from news analysis |
| `/discovery` | Trading opportunities |
| `/help` | List all available commands |

### Command Examples

**Check current status:**
```
/status
```

**View active positions:**
```
/positions
```

**See top trading pairs:**
```
/discovery
```

## Automation

### Cron Jobs

```bash
# Add to crontab:

# Discovery runs every hour (sends report to Telegram)
0 * * * * cd /path/to/crypto-news-scraper && bash ./discovery_and_update.sh

# Trading bot monitor (restarts if down)
0 * * * * /path/to/scripts/check_and_restart_bot.sh

# Telegram bot monitor (every 5 minutes)
*/5 * * * * /path/to/scripts/check_telegram_bot.sh
```

### Dynamic PAIRS System

**How it works:**
1. Every hour: Discovery scans top 50 pairs by volume
2. Calculates technical score for each
3. Sorts by combined_score (technical + sentiment)
4. Updates .env PAIRS with top 8 (score > 0.05)
5. Trading bot reads new PAIRS automatically

**Benefits:**
- Always trading strongest available pairs
- Removes weak performers automatically
- No manual intervention needed
- Adapts to market conditions

## Troubleshooting

### Bot not responding in Telegram
```bash
# Check if process running
ps aux | grep telegram_bot

# Restart
pkill -f telegram_bot.py
python3 scripts/telegram_bot.py
```

### "Uptime: Not running"
```bash
# Check process
pgrep -f trader_continuous
```

### Duplicate notifications in Telegram
```bash
# Stop all instances
pkill -9 -f telegram_bot.py
```

### Weak PAIRS performance
Dynamic system will automatically replace them:
```bash
# View current PAIRS
grep PAIRS .env

# View discovery report
cat ../crypto-news-scraper/discovery_report.json
```

## File Structure

```
trading-bots/johan-binance-trader/
├── scripts/
│   ├── trader.py                 # Main trading bot
│   ├── telegram_bot.py           # Telegram bot
│   ├── decision_engine.py        # Technical + sentiment analysis
│   ├── discovery_engine.py       # Market scanner
│   ├── get_status.py             # Status generation
│   ├── check_and_restart_bot.sh  # Bot monitor
│   └── ...
├── .env                          # Configuration
├── CHANGELOG.md                  # Version history
├── trader.log                    # Trading logs
└── trades.jsonl                  # Transaction history
```

## Performance

- **Trading Bot**: Runs every 60 seconds
- **Sentiment Analysis**: Updates hourly
- **Discovery**: Scans 50+ pairs hourly
- **PAIRS Update**: Automatic every hour
- **Latency**: ~2s for sentiment (local LLM)

## Security

- API keys stored in `.env` (git-ignored)
- Automatic stop-loss on all positions
- Daily loss limit (default: 2%)
- Max positions limit (default: 2)
- Cooldown after stop-loss (default: 12h)

## License

MIT License

## Support

For issues or questions, check the GitHub repository or use the Telegram bot commands.

---

**Version**: 2026.03.29  
**Last Updated**: March 30, 2026
