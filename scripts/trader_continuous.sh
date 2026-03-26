#!/bin/bash
# Continuous Binance Trader — runs the bot every 60 seconds with Telegram notifications

cd /home/johan/.openclaw/workspace/trading-bots/johan-binance-trader

echo "Starting continuous Binance trader..."
echo "Press Ctrl+C to stop"
echo ""

# Send startup notification
python3 scripts/notify_telegram.py 2>/dev/null

while true; do
    python3 scripts/trader.py 2>&1 | tee -a trader.log
    
    # Check for new trades and notify
    python3 scripts/notify_telegram.py 2>/dev/null
    
    echo "--- Sleeping 60s ---" | tee -a trader.log
    sleep 60
done
