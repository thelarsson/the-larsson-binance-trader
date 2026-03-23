---
name: johan-binance-trader
description: Johan's personal Binance spot trading bot with LLM-powered market analysis. Supports momentum trading, mean reversion, and DCA strategies on any Binance spot pair. Use when user wants to trade on Binance, set up automated crypto trading, or needs to run the trading bot on this machine. Requires Binance API credentials.
---

# Johan's Binance Spot Trader

Autonomous spot trading bot for Binance with LLM sentiment analysis.

## Quick Start

### 1. Configure

Create `.env` file in the skill directory:
```
BINANCE_API_KEY=<your-api-key>
BINANCE_SECRET_KEY=<your-secret-key>
OPENAI_API_KEY=<optional-openai-key>
OLLAMA_MODEL=<optional-ollama-model>
OLLAMA_BASE_URL=http://127.0.0.1:11434
PAIRS=BTCUSDT,ETHUSDT,SOLUSDT
STRATEGY=momentum
TRADE_SIZE_PCT=1
MAX_POSITIONS=2
STOP_LOSS_PCT=2
TAKE_PROFIT_PCT=3
COOLDOWN_HOURS=12
MAX_DAILY_LOSS_PCT=2
MAX_TRADES_PER_PAIR_PER_DAY=2
USDT_RESERVE_PCT=40
```

### 2. Setup

```bash
bash {baseDir}/scripts/setup.sh
```

### 3. Run

```bash
python3 {baseDir}/scripts/trader.py
```

Or via cron:
```
*/5 * * * * cd {baseDir} && python3 scripts/trader.py >> trader.log 2>&1
```

## Strategies

- **momentum** (default): Buys on EMA cross + volume spike
- **mean_reversion**: Buys oversold (RSI < 30), sells overbought (RSI > 70)
- **dca**: Fixed interval buying regardless of price

## Files

- `scripts/trader.py` — Main trading bot
- `scripts/portfolio.py` — Portfolio viewer
- `scripts/setup.sh` — Environment setup
- `trades.jsonl` — Trade history (preserved across transfers)
- `trader.log` — Runtime logs

## Security Notes

- NEVER enable withdrawal permissions on API keys
- IP-restrict keys on Binance
- Start with small amounts, test first

## References

- See `references/binance-api.md` for API documentation
- See `references/indicators.md` for technical analysis details
