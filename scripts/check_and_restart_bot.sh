#!/bin/bash
# Check if trading bot is running, start if not, notify via Telegram

BOT_DIR="/home/johan/.openclaw/workspace/trading-bots/johan-binance-trader"
LOG_FILE="$BOT_DIR/bot_monitor.log"
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-}"

# Load from .env if not set
if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ -z "$TELEGRAM_CHAT_ID" ]; then
    if [ -f "$BOT_DIR/.env" ]; then
        export $(grep -E '^(TELEGRAM_BOT_TOKEN|TELEGRAM_CHAT_ID)=' "$BOT_DIR/.env" | xargs)
    fi
fi

# Function to send Telegram notification
send_telegram() {
    local message="$1"
    if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
        curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
            -d "chat_id=$TELEGRAM_CHAT_ID" \
            -d "text=$message" \
            -d "parse_mode=Markdown" > /dev/null 2>&1
    fi
}

# Check if trading bot is running
if pgrep -f "trader_continuous.sh" > /dev/null || pgrep -f "trader.py" > /dev/null; then
    # Bot is running - log but don't notify
    echo "$(date): ✅ Trading bot is running normally" >> "$LOG_FILE"
    exit 0
else
    # Bot is not running - restart and notify
    echo "$(date): ❌ Trading bot NOT running - restarting..." >> "$LOG_FILE"
    
    # Kill any stuck processes
    pkill -9 -f "trader_continuous" 2>/dev/null
    pkill -9 -f "trader.py" 2>/dev/null
    sleep 2
    
    # Start the bot
    cd "$BOT_DIR" || exit 1
    nohup ./scripts/trader_continuous.sh >> trader.log 2>&1 &
    
    sleep 3
    
    # Verify it started
    if pgrep -f "trader_continuous.sh" > /dev/null; then
        echo "$(date): ✅ Bot restarted successfully (PID: $!)" >> "$LOG_FILE"
        send_telegram "⚠️ *Trading Bot Alert*\n\nBot was down and has been restarted automatically.\n\nTime: $(date)\nStatus: ✅ Running"
    else
        echo "$(date): ❌ Failed to restart bot" >> "$LOG_FILE"
        send_telegram "🚨 *Trading Bot CRITICAL*\n\nBot was down and FAILED to restart!\n\nTime: $(date)\nAction: Manual intervention required"
    fi
fi
