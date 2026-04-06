#!/bin/bash
# Monitor both Binance trading bot and Telegram bot
# Restarts them if they are down

BOT_DIR="/home/johan/.openclaw/workspace/trading-bots/johan-binance-trader"
LOG_FILE="$BOT_DIR/logs/monitor.log"

# Function to log with timestamp
log_msg() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Create logs directory if needed
mkdir -p "$BOT_DIR/logs"

log_msg "=== Monitor check started ==="

# Check if trading bot (trader_continuous.sh) is running
if ! pgrep -f "trader_continuous.sh" > /dev/null; then
    log_msg "⚠️ Trading bot DOWN - Restarting..."
    cd "$BOT_DIR"
    nohup ./scripts/trader_continuous.sh > /dev/null 2>&1 &
    sleep 2
    if pgrep -f "trader_continuous.sh" > /dev/null; then
        log_msg "✅ Trading bot restarted successfully"
    else
        log_msg "❌ Failed to restart trading bot"
    fi
else
    log_msg "✅ Trading bot running"
fi

# Check if Telegram bot is running
if ! pgrep -f "telegram_bot.py" > /dev/null; then
    log_msg "⚠️ Telegram bot DOWN - Restarting..."
    cd "$BOT_DIR"
    nohup python3 scripts/telegram_bot.py > /dev/null 2>&1 &
    sleep 2
    if pgrep -f "telegram_bot.py" > /dev/null; then
        log_msg "✅ Telegram bot restarted successfully"
    else
        log_msg "❌ Failed to restart Telegram bot"
    fi
else
    log_msg "✅ Telegram bot running"
fi

log_msg "=== Monitor check complete ==="
