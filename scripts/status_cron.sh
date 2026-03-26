#!/bin/bash
# Send status update to Telegram every hour

cd /home/johan/.openclaw/workspace/trading-bots/johan-binance-trader
python3 scripts/telegram_status.py > /dev/null 2>&1