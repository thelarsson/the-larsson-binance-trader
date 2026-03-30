#!/bin/bash
# Check if Telegram bot is running, start if not

if ! pgrep -f "telegram_bot.py" > /dev/null; then
    cd /home/johan/.openclaw/workspace/trading-bots/johan-binance-trader/scripts
    rm -f .telegram_bot.lock .telegram_bot_seen.json 2>/dev/null
    nohup python3 telegram_bot.py >> telegram_bot.log 2>&1 &
fi
