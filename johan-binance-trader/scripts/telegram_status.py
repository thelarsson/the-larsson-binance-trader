#!/usr/bin/env python3
"""
Telegram Status Bot for Trading Bot
Reports: positions, balance, uptime, last cycle, scanning status
"""

import os
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import httpx
from dotenv import load_dotenv

load_dotenv()

TRADER_LOG = Path('/home/johan/.openclaw/workspace/trading-bots/johan-binance-trader/trader.log')
TRADES_LOG = Path('/home/johan/.openclaw/workspace/trading-bots/johan-binance-trader/trades.jsonl')
DISCOVERY_LOG = Path('/home/johan/.openclaw/workspace/crypto-news-scraper/discovery_report.json')
SENTIMENT_LOG = Path('/home/johan/.openclaw/workspace/crypto-news-scraper/crypto_sentiment_report.json')

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')


def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram not configured")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        with httpx.Client(timeout=15) as c:
            r = c.post(url, json=payload)
            r.raise_for_status()
        return True
    except Exception as e:
        print(f"Failed to send Telegram: {e}")
        return False


def get_uptime():
    """Get bot uptime from process."""
    try:
        result = subprocess.run(
            ["ps", "-p", "677115", "-o", "etime="],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass
    
    # Fallback - parse from log
    if TRADER_LOG.exists():
        try:
            with open(TRADER_LOG) as f:
                first_line = f.readline()
                if first_line:
                    # Extract timestamp
                    ts_str = first_line[:19]
                    ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                    now = datetime.now()
                    uptime = now - ts
                    hours = uptime.total_seconds() / 3600
                    return f"{hours:.1f}h"
        except:
            pass
    return "Unknown"


def get_last_cycle_info():
    """Get last cycle timestamp and status."""
    if not TRADER_LOG.exists():
        return "No log found", "Unknown"
    
    try:
        # Get last 100 lines
        result = subprocess.run(
            ["tail", "-100", str(TRADER_LOG)],
            capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.strip().split('\n')
        
        last_cycle = None
        scanning = None
        balance = None
        
        for line in reversed(lines):
            if "Cycle complete" in line and not last_cycle:
                # Extract timestamp
                if line.startswith('20'):
                    last_cycle = line[:19]
            if "Found" in line and "pairs" in line and not scanning:
                scanning = line.split("Found")[-1].strip()
            if "USDT balance" in line and not balance:
                try:
                    balance = line.split('$')[-1].strip()
                except:
                    pass
        
        return last_cycle or "Unknown", scanning or "Unknown", balance or "Unknown"
    except Exception as e:
        return f"Error: {e}", "Unknown", "Unknown"


def get_positions():
    """Get current positions from trades log."""
    if not TRADES_LOG.exists():
        return []
    
    positions = {}
    try:
        with open(TRADES_LOG) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    trade = json.loads(line)
                    if trade.get('result') != 'FILLED':
                        continue
                    
                    symbol = trade.get('symbol', '')
                    side = trade.get('side', '')
                    qty = float(trade.get('qty', 0))
                    price = float(trade.get('price', 0))
                    
                    if symbol not in positions:
                        positions[symbol] = {'qty': 0, 'cost': 0, 'entry_price': 0}
                    
                    if side == 'BUY':
                        positions[symbol]['qty'] += qty
                        positions[symbol]['cost'] += qty * price
                    elif side == 'SELL':
                        positions[symbol]['qty'] -= qty
                        positions[symbol]['cost'] -= qty * price
                        
                except:
                    continue
        
        # Filter active positions - exclude staking rewards and dust
        active = []
        prices = get_current_prices()
        for symbol, data in positions.items():
            if data['qty'] > 0.0001:
                avg_entry = data['cost'] / data['qty'] if data['qty'] > 0 else 0

                # Calculate current value and skip if under $1
                current_price = prices.get(symbol, avg_entry)
                position_value = data['qty'] * current_price
                if position_value < 1.0:
                    continue
                active.append({
                    'symbol': symbol,
                    'qty': data['qty'],
                    'avg_entry': avg_entry
                })
        
        return active
    except Exception as e:
        return []


def get_current_prices():
    """Get current prices from log."""
    prices = {}
    if not TRADER_LOG.exists():
        return prices
    
    try:
        result = subprocess.run(
            ["tail", "-200", str(TRADER_LOG)],
            capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.strip().split('\n')
        
        for line in reversed(lines):
            if "price=$" in line and "signal=" in line:
                try:
                    # Extract symbol and price
                    parts = line.split()
                    for part in parts:
                        if "price=$" in part:
                            price = float(part.split('$')[1])
                        if "USDT:" in line:
                            symbol = line.split(':')[0].split()[-1]
                            prices[symbol] = price
                            break
                except:
                    continue
        
        return prices
    except:
        return {}


def get_discovery_status():
    """Get discovery scan status."""
    if not DISCOVERY_LOG.exists():
        return "No discovery data"
    
    try:
        with open(DISCOVERY_LOG) as f:
            data = json.load(f)
        
        ts = data.get('timestamp', 'Unknown')[:19] if data.get('timestamp') else 'Unknown'
        opportunities = len(data.get('opportunities', []))
        recommendations = len(data.get('recommendations', []))
        
        return f"{opportunities} pairs, {recommendations} recs (last: {ts})"
    except:
        return "Error reading discovery"


def get_sentiment_status():
    """Get news sentiment status."""
    if not SENTIMENT_LOG.exists():
        return "No sentiment data"
    
    try:
        with open(SENTIMENT_LOG) as f:
            data = json.load(f)
        
        summary = data.get('summary', {})
        sentiment = summary.get('overall_sentiment', 'Unknown')
        strength = summary.get('strength', 0)
        breakdown = summary.get('breakdown', {})
        
        return f"{sentiment} ({strength:.2f}) B:{breakdown.get('bullish',0)} R:{breakdown.get('bearish',0)}"
    except:
        return "Error reading sentiment"


def generate_status_report():
    """Generate full status report."""
    lines = [
        "📊 *TRADING BOT STATUS*",
        "",
        "⏱️ *Uptime:*",
        f"`{get_uptime()}`",
        "",
    ]
    
    # Last cycle info
    last_cycle, scanning, balance = get_last_cycle_info()
    lines.extend([
        "🔄 *Last Cycle:*",
        f"`{last_cycle}`",
        "",
        "💰 *Balance:*",
        f"`${balance}` USDT",
        "",
    ])
    
    # Positions
    positions = get_positions()
    if positions:
        lines.append("📈 *Positions:*")
        for pos in positions:
            symbol = pos['symbol']
            qty = pos['qty']
            entry = pos['avg_entry']
            lines.append(f"• `{symbol}`: {qty:.4f} @ ${entry:.2f}")
        lines.append("")
    else:
        lines.extend([
            "📈 *Positions:*",
            "No active positions",
            "",
        ])
    
    # Scanning
    lines.extend([
        "🔍 *Scanning:*",
        f"`{scanning}`",
        "",
    ])
    
    # Discovery
    discovery = get_discovery_status()
    lines.extend([
        "🔎 *Discovery:*",
        f"`{discovery}`",
        "",
    ])
    
    # Sentiment
    sentiment = get_sentiment_status()
    lines.extend([
        "📰 *Sentiment:*",
        f"`{sentiment}`",
        "",
    ])
    
    lines.append(f"_Updated: {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC_")
    
    return "\n".join(lines)


def main():
    """Send status report to Telegram."""
    report = generate_status_report()
    print(report)
    print()
    
    if send_telegram(report):
        print("✅ Status sent to Telegram")
    else:
        print("❌ Failed to send to Telegram")


if __name__ == '__main__':
    main()