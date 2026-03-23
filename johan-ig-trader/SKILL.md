---
name: johan-ig-trader
description: Johan's personal IG trading bot for CFDs, forex, and equity derivatives. Supports momentum and mean reversion strategies with LLM sentiment analysis on IG. Use when user wants to trade on IG Markets, set up automated CFD trading, or needs to run the IG trading bot on this machine. Requires IG API credentials.
---

# Johan's IG Trader

Autonomous trading bot for IG Markets (CFDs, forex, and equity derivatives).

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

- **momentum** (default): Buys on EMA cross + volume confirmation
- **mean_reversion**: Buys when RSI < 30 near support, sells when RSI > 70

## IG Epic Examples

- `IX.D.DAX.IFG.IP` — Germany 40 (DAX)
- `IX.D.SPTRD.IFE.IP` — S&P 500
- `CS.D.EURUSD.MINI.IP` — EUR/USD Mini
- `IX.D.NASDAQ.IFE.IP` — NASDAQ 100

## Files

- `scripts/trader.py` — Main trading bot
- `scripts/setup.sh` — Environment setup
- `trader.log` — Runtime logs

## Security Notes

- Use DEMO account first to test
- IG credentials are session-based and expire
- Monitor positions regularly

## References

- See `references/ig-api.md` for IG REST API documentation
- See `references/epics.md` for common epic codes
