# Changelog

All notable changes to the Binance Trading Bot.

## [2026-03-29] - Dynamic PAIRS and Telegram Integration

### Added
- **Dynamic PAIRS System**: Automatically updates PAIRS list hourly based on discovery engine scores
- **Auto-Discovery Reports**: Discovery reports now sent to Telegram trading bot automatically
- **Sentiment Reports**: Crypto sentiment analysis reports sent to Telegram hourly
- **New Commands**:
  - `/pairs` - Show current PAIRS list from .env
  - `/sync` - Sync positions with Binance API
- **Monitoring Scripts**:
  - `check_and_restart_bot.sh` - Monitors and auto-restarts trading bot if down
  - `check_telegram_bot.sh` - Monitors Telegram bot status

### Changed
- **Telegram Bot**: 
  - Added automatic position syncing with Binance API
  - Fixed `/uptime` command to correctly detect trading bot process
  - Added chat message handling for non-command interactions
- **Cron Jobs**: Added hourly checks for both trading and Telegram bots
- **Process Detection**: Improved uptime detection using `pgrep` with better fallbacks

### Fixed
- **Permission Issues**: Fixed script execution permissions for monitoring
- **Process Uptime**: Now correctly finds `trader_continuous.sh` process instead of failing

## [2026-03-27] - Initial Trading Bot Setup

### Added
- Basic trading bot with momentum strategy
- Telegram integration with commands: `/status`, `/positions`, `/balance`, `/uptime`
- Decision engine combining technical (60%) and sentiment (40%) analysis
- Discovery engine for automatic currency detection
- Sentiment analysis using local LLM (llama3.2:3b)

## Configuration

### Current PAIRS
Dynamic - updates hourly based on top-scoring pairs from discovery engine.

### Cron Jobs
| Job | Schedule | Description |
|-----|----------|-------------|
| Trading Bot Monitor | Every hour | Restarts trading bot if down |
| Telegram Bot Monitor | Every 5 minutes | Checks Telegram bot status |

## How to Update

```bash
cd ~/.openclaw/workspace/trading-bots/johan-binance-trader
git pull origin master

# Restart services
pkill -f trader_continuous
pkill -f telegram_bot
./scripts/trader_continuous.sh &
python3 scripts/telegram_bot.py &
```
