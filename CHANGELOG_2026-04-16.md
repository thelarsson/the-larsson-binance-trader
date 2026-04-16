# Changelog - 2026-04-16

## Bug Fixes & Improvements

### Dynamic PAIRS System
- Fixed: load_dynamic_pairs.py now reads PAIRS directly from .env file instead of os.getenv()
- Fixed: discovery_and_update.sh handles both dict and string formats in discovery report
- Fixed: Cron job now correctly updates PAIRS without reverting to old values
- Restored: Cron job for hourly PAIRS updates (was accidentally disabled)

### Trading Strategy - Relaxed Thresholds
- Changed: Sentiment threshold for BUY: -0.2 to -0.1 (more aggressive)
- Changed: Technical threshold: 0.3 to 0.1 (more aggressive)
- Changed: Sentiment threshold for SELL: 0.2 to 0.1 (more aggressive)
- Reason: Bot was too cautious, missing +10.5% BTC uptrend

### Decision Engine
- Updated: Relaxed thresholds in decision_engine.py for more trading opportunities
- Added: Comments explaining threshold changes

### Telegram Bot
- Fixed: Now reads coins from summary.coins instead of data.coins
- Fixed: Displays "Top Mentioned Coins" correctly with sentiment scores

## Current Status

Binance Trading Bot:
- Active Pairs: 12 (BTC, ETH, BNB, DOGE, 1000SATS, MBOX, BIO, NEAR, AXL, BLUR, NEIRO, WAL, ENJ)
- Balance: $538.80 USDT
- Strategy: EMA with relaxed thresholds
- Last Trade: April 5, 2026 (waiting for signals)

IG Trading Bot:
- Mode: LIVE
- DCA Amount: 1,000 AED
- Next Trade: May 1, 2026

## Changes Committed

- load_dynamic_pairs.py - Fixed to read from file
- scripts/decision_engine.py - Relaxed thresholds
- scripts/telegram_bot.py - Fixed coin tracking
- discovery_and_update.sh - Fixed for new report format
- Cron job - Re-enabled for automatic updates

## Author
- AI Assistant (OpenClaw) + Johan
- Date: 2026-04-16
