# 📊 The Larsson Binance Trader
## Complete Documentation | English Edition

---

**Version:** 2026.03.30  
**Language:** English  
**License:** MIT

---

## 📑 Table of Contents

1. [Overview & Architecture](#1-overview--architecture)
2. [Core Features](#2-core-features)
3. [Installation & Setup](#3-installation--setup)
4. [Configuration Guide](#4-configuration-guide)
5. [Trading Strategies](#5-trading-strategies)
6. [Telegram Commands](#6-telegram-commands)
7. [Automation & Cron Jobs](#7-automation--cron-jobs)
8. [Troubleshooting Guide](#8-troubleshooting-guide)
9. [Security & Risk Management](#9-security--risk-management)
10. [API Reference](#10-api-reference)

---

## 1. Overview & Architecture

### 🎯 What is The Larsson Binance Trader?

The Larsson Binance Trader is an **AI-powered cryptocurrency trading bot** that combines:
- **Technical Analysis** - EMA, RSI, Bollinger Bands
- **Sentiment Analysis** - News from CoinDesk using local LLM (llama3.2:3b)
- **Auto-Discovery** - Automatically finds and ranks trading pairs
- **Dynamic PAIRS** - Auto-updates based on performance scores

### 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    TRADING BOT SYSTEM                       │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  News Scraper │  │    Decision   │  │   Discovery   │      │
│  │   (Python)    │──│    Engine     │──│    Engine     │      │
│  │  AgentBrowser │  │   Technical   │  │   Binance     │      │
│  └──────────────┘  │   + Sentiment │  │   Scanner     │      │
│         │          └──────────────┘  └──────────────┘      │
│         │                   │                   │              │
│         ▼                   ▼                   ▼            │
│  ┌────────────────────────────────────────────────────┐   │
│  │              Trading Bot (Python)                   │   │
│  │         Binance API • Risk Management            │   │
│  │         Dynamic PAIRS Selection                  │   │
│  └────────────────────────────────────────────────────┘   │
│                            │                               │
│                            ▼                               │
│  ┌────────────────────────────────────────────────────┐   │
│  │           Telegram Bot (Real-time)                │   │
│  │    /status • /positions • /balance • /pairs    │   │
│  │    /sentiment • /discovery • /uptime           │   │
│  └────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Core Features

### ✨ Key Capabilities

| Feature | Description | Status |
|---------|-------------|--------|
| **🧠 AI Sentiment Analysis** | Analyzes CoinDesk news using local LLM (llama3.2:3b) - Zero API costs | ✅ Active |
| **📊 Technical Analysis** | EMA, RSI, Bollinger Bands, Volume analysis | ✅ Active |
| **🔍 Auto-Discovery** | Automatically discovers and ranks new trading pairs hourly | ✅ Active |
| **📱 Telegram Integration** | Real-time notifications and status commands | ✅ Active |
| **⚡ Local LLM Execution** | Runs entirely on your machine - No external API costs | ✅ Active |
| **🛡️ Risk Management** | Stop-loss, take-profit, daily loss limits | ✅ Active |
| **🔄 Dynamic PAIRS** | Automatically updates PAIRS list based on performance | ✅ Active |

### 🎯 Trading Strategies

| Strategy | Description | Use Case |
|----------|-------------|----------|
| **Momentum** | Follows market trends using EMA crossover | Trending markets |
| **Mean Reversion** | Trades overbought/oversold levels | Ranging markets |
| **DCA** | Dollar Cost Averaging at regular intervals | Long-term accumulation |

---

## 3. Installation & Setup

### 📋 Prerequisites

**Required Software:**
- Python 3.8+
- pip (Python package manager)
- Git (for cloning)
- Ollama (for local LLM)

### 🚀 Quick Install

```bash
# 1. Install Python dependencies
pip install httpx python-dotenv

# 2. Install Ollama (Linux/Mac)
curl -fsSL https://ollama.com/install.sh | sh

# 3. Pull LLM model
ollama pull llama3.2:3b

# 4. Clone repository
cd trading-bots/johan-binance-trader

# 5. Setup configuration
cp .env.example .env

# 6. Edit .env with your API keys
nano .env
```

### ▶️ Start the Bot

```bash
# Terminal 1: Start trading bot (runs every 60 seconds)
./scripts/trader_continuous.sh

# Terminal 2: Start Telegram bot
python3 scripts/telegram_bot.py
```

---

## 4. Configuration Guide

### 🔧 Environment Variables (.env)

```bash
# ═══════════════════════════════════════════════════
# Binance API Credentials
# ═══════════════════════════════════════════════════
BINANCE_API_KEY=your_api_key_here
BINANCE_SECRET_KEY=your_secret_key_here

# ═══════════════════════════════════════════════════
# Trading Parameters
# ═══════════════════════════════════════════════════
PAIRS=BTCUSDT,ETHUSDT,SOLUSDT          # Auto-updated hourly!
STRATEGY=momentum
TRADE_SIZE_PCT=15
MAX_POSITIONS=2
STOP_LOSS_PCT=2
TAKE_PROFIT_PCT=3

# ═══════════════════════════════════════════════════
# LLM Configuration (Ollama)
# ═══════════════════════════════════════════════════
OLLAMA_MODEL=llama3.2:3b
OLLAMA_BASE_URL=http://127.0.0.1:11434
USE_LLM=true

# ═══════════════════════════════════════════════════
# Decision Engine
# ═══════════════════════════════════════════════════
USE_DECISION_ENGINE=true
DECISION_SENTIMENT_WEIGHT=0.4

# ═══════════════════════════════════════════════════
# Discovery & Dynamic Pairs
# ═══════════════════════════════════════════════════
USE_AUTO_DISCOVERY=true
DISCOVERY_MIN_SCORE=0.05              # Lower threshold = more pairs
DISCOVERY_AUTO_ADD=false              # Manual approval recommended

# ═══════════════════════════════════════════════════
# Telegram Bot
# ═══════════════════════════════════════════════════
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

---

## 5. Trading Strategies

### 🧠 Decision Process Flow

```
Strategy Signal (e.g., Momentum EMA Crossover)
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
    │  LLM Sentiment│ ← llama3.2:3b validates (optional)
    │  (if enabled) │
    └──────────────┘
           ↓
    ┌──────────────┐
    │    Trade?    │ ← Yes/No based on combined score > threshold
    └──────────────┘
```

### 📊 Technical Indicators Weight

| Indicator | Weight | Description |
|-----------|--------|-------------|
| **EMA Crossover** | 30% | Fast vs Slow EMA comparison |
| **RSI** | 25% | Overbought/Oversold detection |
| **Bollinger Bands** | 15% | Price position within bands |
| **Volume Trend** | 10% | Increasing/Decreasing volume |
| **Price Change** | 10% | 24-hour change percentage |

---

## 6. Telegram Commands

### 🤖 Available Commands

| Command | Description | Example Output |
|---------|-------------|----------------|
| `/status` | Full bot status | Balance, positions, uptime |
| `/positions` | Active positions | Synced with Binance, PnL |
| `/balance` | USDT balance | Live from Binance API |
| `/pairs` | Current PAIRS list | From .env file |
| `/sync` | Sync with Binance | Verify positions match |
| `/uptime` | Bot runtime | How long running |
| `/sentiment` | Market sentiment | News analysis summary |
| `/discovery` | Trading opportunities | Top scoring pairs |
| `/help` | List all commands | Command reference |

### 💡 Usage Examples

**Check current status:**
```
/status
```
**Output:**
```
📊 TRADING BOT STATUS
⏱️ Uptime: 10:45:23
💰 Balance: $1,234.56 USDT
📈 Positions: BTCUSDT, ETHUSDT
🔍 Scanning: 8 pairs
```

**View active positions:**
```
/positions
```
**Output:**
```
📈 Active Positions:
• BTCUSDT: 0.015 @ $67,890 (+2.3%)
• ETHUSDT: 0.45 @ $3,450 (+1.8%)
✅ Synced with Binance
```

---

## 7. Automation & Cron Jobs

### ⏰ Scheduled Tasks

**Hourly Automation:**

| Task | Schedule | Description |
|------|----------|-------------|
| **Discovery Scan** | Every hour | Analyzes market, sends report to Telegram |
| **Sentiment Analysis** | Every hour | News analysis sent to Telegram |
| **Bot Monitor** | Every hour | Restarts trading bot if down |
| **PAIRS Update** | Every hour | Auto-updates based on scores |

### 📝 Crontab Configuration

```bash
# Edit crontab
crontab -e

# Add these lines:

# ═══════════════════════════════════════════════════
# Trading Bot Monitor - restarts if down
# ═══════════════════════════════════════════════════
0 * * * * /home/johan/.openclaw/workspace/trading-bots/johan-binance-trader/scripts/check_and_restart_bot.sh

# ═══════════════════════════════════════════════════
# Discovery - runs silently, sends to Telegram
# ═══════════════════════════════════════════════════
0 * * * * cd /home/johan/.openclaw/workspace/crypto-news-scraper && bash ./discovery_and_update.sh >/dev/null 2>&1

# ═══════════════════════════════════════════════════
# Sentiment Analysis - runs silently
# ═══════════════════════════════════════════════════
0 * * * * cd /home/johan/.openclaw/workspace/crypto-news-scraper && bash ./run_crypto_silent.sh >/dev/null 2>&1
```

### 🔄 Dynamic PAIRS System

**How it works:**

1. **Every hour:** Discovery scans top 50 pairs by volume
2. **Calculates score:** Technical + Sentiment for each
3. **Sorts:** By combined_score (highest first)
4. **Updates PAIRS:** Top 8 (score > 0.05)
5. **Auto-sync:** Trading bot reads new PAIRS

**Benefits:**
- ✅ Always trading strongest pairs
- ✅ Removes weak performers automatically
- ✅ No manual intervention needed
- ✅ Adapts to market conditions

---

## 8. Troubleshooting Guide

### 🔧 Common Issues & Solutions

| Issue | Check Command | Solution |
|-------|--------------|----------|
| **Bot not responding** | `ps aux \| grep telegram_bot` | `pkill -f telegram_bot.py && python3 scripts/telegram_bot.py` |
| **Uptime: Not running** | `pgrep -f trader_continuous` | `./scripts/trader_continuous.sh` |
| **Duplicate notifications** | `ps aux \| grep telegram` | `pkill -9 -f telegram_bot.py` |
| **Weak PAIRS performance** | `grep PAIRS .env` | Discovery auto-replaces weak pairs |
| **API errors** | Check `.env` file | Verify keys on Binance website |
| **High memory usage** | `top` or `htop` | Restart bots: `pkill -f trader && pkill -f telegram` |

### 🆘 Emergency Commands

```bash
# Restart everything
pkill -f trader
pkill -f telegram
sleep 2
./scripts/trader_continuous.sh &
python3 scripts/telegram_bot.py &

# Check all processes
ps aux | grep -E "trader|telegram"

# View recent logs
tail -50 trader.log
tail -50 telegram_bot.log
```

---

## 9. Security & Risk Management

### 🔒 Security Features

| Feature | Description | Status |
|---------|-------------|--------|
| **API Key Storage** | In `.env` file, git-ignored | ✅ Secure |
| **Automatic Stop-Loss** | On every position | ✅ Active |
| **Daily Loss Limit** | Default: 2% of portfolio | ✅ Active |
| **Max Positions** | Default: 2 concurrent | ✅ Active |
| **Cooldown Period** | Default: 12h after stop-loss | ✅ Active |
| **Local LLM** | No data leaves your machine | ✅ Private |
| **Telegram Security** | Secure bot token, encrypted | ✅ Secure |

### ⚠️ Risk Settings (.env)

```bash
# Risk Configuration
STOP_LOSS_PCT=2        # Stop loss at -2%
TAKE_PROFIT_PCT=3      # Take profit at +3%
MAX_POSITIONS=2        # Max 2 concurrent positions
COOLDOWN_HOURS=12      # Wait 12h after stop-loss
MAX_TRADES_PER_PAIR_PER_DAY=3  # Limit daily trades
MAX_TOTAL_ENTRIES_PER_DAY=5      # Limit total entries
```

---

## 10. API Reference

### 📁 Key Files

#### Core Scripts

| File | Purpose | Lines |
|------|---------|-------|
| `trader.py` | Main trading logic and execution | ~650 |
| `telegram_bot.py` | Telegram interface and commands | ~480 |
| `decision_engine.py` | Technical + sentiment analysis | ~450 |
| `discovery_engine.py` | Market scanning and ranking | ~530 |
| `sentiment_integration.py` | News analysis module | ~200 |
| `get_status.py` | Status report generation | ~280 |

#### Utility Scripts

| File | Purpose |
|------|---------|
| `check_and_restart_bot.sh` | Monitors and auto-restarts trading bot |
| `check_telegram_bot.sh` | Monitors Telegram bot status |
| `notify_telegram.py` | Sends trade notifications |
| `portfolio.py` | Portfolio tracking and analysis |
| `profitloss_report.py` | P&L reporting |

### 📊 Data Files

| File | Purpose | Format |
|------|---------|--------|
| `trader.log` | Trading activity log | Text |
| `trades.jsonl` | Transaction history | JSON Lines |
| `discovery_report.json` | Latest discovery results | JSON |
| `crypto_sentiment_report.json` | Sentiment analysis | JSON |
| `trading_signal.json` | Current trading signal | JSON |

---

## 📞 Support & Resources

### 🔗 Links

- **GitHub Repository:** https://github.com/thelarsson/the-larsson-binance-trader
- **Telegram Bot:** @TheLarssonBot

### 📝 Quick Reference

```bash
# Check status
cd trading-bots/johan-binance-trader
ps aux | grep -E "trader|telegram"

# View logs
tail -f trader.log
tail -f telegram_bot.log

# Restart bots
pkill -f trader
pkill -f telegram
./scripts/trader_continuous.sh &
python3 scripts/telegram_bot.py &
```

---

**The Larsson Binance Trader**  
*AI-Powered Cryptocurrency Trading*  
**Version 2026.03.30** | **Documentation v1.0** | **MIT License**

---

*Built with ❤️ by AI Assistant for The Larsson Trading*
