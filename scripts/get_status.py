#!/usr/bin/env python3
"""
Get trading bot status - OUTPUT ONLY (no Telegram send)
Called by telegram_bot.py
Syncs positions with actual Binance account state
"""

import os
import json
import hmac
import hashlib
import time
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter
import httpx

TRADER_LOG = Path('/home/johan/.openclaw/workspace/trading-bots/johan-binance-trader/trader.log')
TRADES_LOG = Path('/home/johan/.openclaw/workspace/trading-bots/johan-binance-trader/trades.jsonl')
DISCOVERY_LOG = Path('/home/johan/.openclaw/workspace/crypto-news-scraper/discovery_report.json')
SENTIMENT_LOG = Path('/home/johan/.openclaw/workspace/crypto-news-scraper/crypto_sentiment_report.json')

BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', '')
BINANCE_SECRET_KEY = os.getenv('BINANCE_SECRET_KEY', '')
BINANCE_BASE_URL = 'https://api.binance.com'


def get_binance_prices():
    """Get current prices from Binance API."""
    try:
        r = httpx.get(f"{BINANCE_BASE_URL}/api/v3/ticker/price", timeout=15)
        data = r.json()
        return {item['symbol']: float(item['price']) for item in data}
    except:
        return {}


def get_uptime():
    try:
        result = subprocess.run(
            ["ps", "-p", "677115", "-o", "etime="],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip()
    except:
        return "Unknown"


def sign_binance(params):
    """Sign Binance API request."""
    params["timestamp"] = int(time.time() * 1000)
    query = '&'.join([f"{k}={v}" for k, v in params.items()])
    params["signature"] = hmac.new(BINANCE_SECRET_KEY.encode(), query.encode(), hashlib.sha256).hexdigest()
    return params


def binance_get(path, params=None):
    """Make authenticated GET request to Binance API."""
    if not BINANCE_API_KEY or not BINANCE_SECRET_KEY:
        return {}
    
    try:
        signed_params = sign_binance(params or {})
        r = httpx.get(
            f"https://api.binance.com{path}",
            params=signed_params,
            headers={"X-MBX-APIKEY": BINANCE_API_KEY},
            timeout=15
        )
        return r.json()
    except Exception as e:
        return {}


def get_binance_positions():
    """Get actual positions from Binance account. Filters out dust positions under $1 USD."""
    positions = {}
    if not BINANCE_API_KEY or not BINANCE_SECRET_KEY:
        return positions

    try:
        account = binance_get("/api/v3/account", {})
        if account and 'balances' in account:
            # Get current prices to calculate position values
            prices = get_binance_prices()
            for b in account.get('balances', []):
                asset = b.get('asset')
                free = float(b.get('free', 0))
                locked = float(b.get('locked', 0))
                total = free + locked
                if total > 0.0001 and asset != 'USDT':
                    symbol = f"{asset}USDT"
                    current_price = prices.get(symbol, 0)
                    position_value = total * current_price
                    # Filter out dust positions under $1 USD
                    if position_value < 1.0:
                        continue
                    # Try to get avg entry from trade history
                    avg_entry = None
                    try:
                        trades = binance_get("/api/v3/myTrades", {"symbol": symbol, "limit": 50})
                        buy_qty = 0
                        buy_cost = 0
                        for t in trades:
                            if t.get('isBuyer'):
                                qty = float(t.get('qty', 0))
                                price = float(t.get('price', 0))
                                buy_qty += qty
                                buy_cost += qty * price
                        if buy_qty > 0:
                            avg_entry = buy_cost / buy_qty
                    except:
                        pass
                    positions[symbol] = {'qty': total, 'avg_entry': avg_entry}
    except:
        pass

    return positions


def get_local_positions():
    """Calculate positions from local trade log. Filters out dust positions under $1 USD."""
    positions = {}
    if not TRADES_LOG.exists():
        return positions

    try:
        with open(TRADES_LOG) as f:
            for line in f:
                try:
                    trade = json.loads(line.strip())
                    if trade.get('result') != 'FILLED':
                        continue

                    symbol = trade.get('symbol', '')
                    side = trade.get('side', '')
                    qty = float(trade.get('qty', 0) or 0)
                    price = float(trade.get('price', 0) or 0)

                    if symbol not in positions:
                        positions[symbol] = {'qty': 0, 'cost': 0}

                    if side == 'BUY':
                        positions[symbol]['qty'] += qty
                        positions[symbol]['cost'] += qty * price
                    elif side == 'SELL':
                        sell_qty = min(positions[symbol]['qty'], qty)
                        if positions[symbol]['qty'] > 0:
                            avg_price = positions[symbol]['cost'] / positions[symbol]['qty']
                            positions[symbol]['cost'] -= sell_qty * avg_price
                            positions[symbol]['qty'] -= sell_qty
                except:
                    continue

        # Filter out dust positions under $1 USD
        prices = get_binance_prices()
        filtered_positions = {}
        for sym, data in positions.items():
            if data['qty'] > 0.0001:
                current_price = prices.get(sym, 0)
                position_value = data['qty'] * current_price
                if position_value >= 1.0:
                    filtered_positions[sym] = data

        return filtered_positions
    except:
        return positions


def get_merged_positions():
    """
    Merge Binance positions with local data.
    Returns positions with Binance qty (truth) and local avg_entry if available.
    Filters out dust positions under $1 USD.
    """
    binance_pos = get_binance_positions()
    local_pos = get_local_positions()

    result = []
    # Get current prices for filtering
    prices = get_binance_prices()

    # Only include positions that exist on Binance
    for symbol, data in binance_pos.items():
        qty = data['qty']
        avg_entry = data['avg_entry']

        # Skip if qty is 0 or position value under $1
        current_price = prices.get(symbol, avg_entry or 0)
        position_value = qty * current_price
        if position_value < 1.0:
            continue

        # If no avg_entry from Binance trades, try to get from local
        if avg_entry is None and symbol in local_pos:
            local_data = local_pos[symbol]
            if local_data['qty'] > 0:
                avg_entry = local_data['cost'] / local_data['qty']

        result.append({'symbol': symbol, 'qty': qty, 'avg_entry': avg_entry or 0})

    return result


def get_last_cycle():
    if not TRADER_LOG.exists():
        return "Unknown"
    try:
        result = subprocess.run(['tail', '-100', str(TRADER_LOG)],
                              capture_output=True, text=True, timeout=5)
        lines = result.stdout.split('\n')
        for line in reversed(lines):
            if 'Cycle complete' in line:
                if line[:4] == '2026':
                    return line[:19]
        return "Unknown"
    except:
        return "Unknown"


def sign_binance(params):
    """Sign Binance API request."""
    params["timestamp"] = int(time.time() * 1000)
    query = '\u0026'.join([f"{k}={v}" for k, v in params.items()])
    params["signature"] = hmac.new(BINANCE_SECRET_KEY.encode(), query.encode(), hashlib.sha256).hexdigest()
    return params


def binance_get(path, params=None):
    """Make authenticated GET request to Binance API."""
    if not BINANCE_API_KEY or not BINANCE_SECRET_KEY:
        return {}
    
    try:
        signed_params = sign_binance(params or {})
        r = httpx.get(
            f"{BINANCE_BASE_URL}{path}",
            params=signed_params,
            headers={"X-MBX-APIKEY": BINANCE_API_KEY},
            timeout=15
        )
        return r.json()
    except Exception as e:
        print(f"Binance API error: {e}", file=os.sys.stderr)
        return {}


def get_balance():
    """Get USDT balance from Binance API."""
    if not BINANCE_API_KEY or not BINANCE_SECRET_KEY:
        # Fallback to log
        if not TRADER_LOG.exists():
            return "Unknown"
        try:
            result = subprocess.run(['grep', 'USDT balance', str(TRADER_LOG)],
                                  capture_output=True, text=True, timeout=5)
            lines = [l for l in result.stdout.strip().split('\n') if l]
            if lines:
                return lines[-1].split('$')[-1].strip()
            return "Unknown"
        except:
            return "Unknown"
    
    try:
        account = binance_get("/api/v3/account", {})
        if account and 'balances' in account:
            for b in account.get('balances', []):
                if b['asset'] == 'USDT':
                    free = float(b.get('free', 0))
                    locked = float(b.get('locked', 0))
                    return f"{free + locked:.2f} (free: {free:.2f})"
        return "Unknown"
    except:
        return "Unknown"


def get_positions_from_local():
    """Get positions from local trades.jsonl (fallback)."""
    positions = {}
    if not TRADES_LOG.exists():
        return []
    
    try:
        with open(TRADES_LOG) as f:
            for line in f:
                try:
                    trade = json.loads(line.strip())
                    if trade.get('result') != 'FILLED':
                        continue
                    
                    symbol = trade.get('symbol', '')
                    side = trade.get('side', '')
                    qty = float(trade.get('qty', 0) or 0)
                    price = float(trade.get('price', 0) or 0)
                    
                    if symbol not in positions:
                        positions[symbol] = {'qty': 0, 'cost': 0}
                    
                    if side == 'BUY':
                        positions[symbol]['qty'] += qty
                        positions[symbol]['cost'] += qty * price
                    elif side == 'SELL':
                        sell_qty = min(positions[symbol]['qty'], qty)
                        if positions[symbol]['qty'] > 0:
                            avg_price = positions[symbol]['cost'] / positions[symbol]['qty']
                            positions[symbol]['cost'] -= sell_qty * avg_price
                            positions[symbol]['qty'] -= sell_qty
                except:
                    continue
        
        active = []
        for sym, data in positions.items():
            if data['qty'] > 0.0001:
                avg_entry = data['cost'] / data['qty'] if data['qty'] > 0 else 0
                active.append({'symbol': sym, 'qty': data['qty'], 'avg_entry': avg_entry})
        
        return active
    except:
        return []


def get_positions():
    """Get positions - sync with Binance API."""
    positions = {}
    
    # Try Binance API first
    if BINANCE_API_KEY and BINANCE_SECRET_KEY:
        try:
            account = binance_get("/api/v3/account", {})
            if account and 'balances' in account:
                for b in account.get('balances', []):
                    asset = b.get('asset')
                    free = float(b.get('free', 0))
                    locked = float(b.get('locked', 0))
                    total = free + locked
                    if total > 0.0001 and asset != 'USDT':
                        symbol = f"{asset}USDT"
                        # Try to get avg entry from trade history
                        avg_entry = 0
                        try:
                            trades = binance_get("/api/v3/myTrades", {"symbol": symbol, "limit": 50})
                            buy_qty = 0
                            buy_cost = 0
                            for t in trades:
                                if t.get('isBuyer'):
                                    qty = float(t.get('qty', 0))
                                    price = float(t.get('price', 0))
                                    buy_qty += qty
                                    buy_cost += qty * price
                            if buy_qty > 0:
                                avg_entry = buy_cost / buy_qty
                        except:
                            pass
                        positions[symbol] = {'qty': total, 'avg_entry': avg_entry}
                
                # Return as list
                active = []
                for sym, data in positions.items():
                    active.append({'symbol': sym, 'qty': data['qty'], 'avg_entry': data['avg_entry']})
                return active
        except Exception as e:
            print(f"Error getting Binance positions: {e}", file=os.sys.stderr)
    
    # Fallback to local
    return get_positions_from_local()


def get_scanning():
    if not TRADER_LOG.exists():
        return "Unknown"
    try:
        result = subprocess.run(['tail', '-50', str(TRADER_LOG)],
                              capture_output=True, text=True, timeout=5)
        for line in reversed(result.stdout.split('\n')):
            if 'pairs with volume' in line:
                return line.split('Found')[-1].strip()
        return "Unknown"
    except:
        return "Unknown"


def get_discovery():
    if not DISCOVERY_LOG.exists():
        return "No data"
    try:
        with open(DISCOVERY_LOG) as f:
            data = json.load(f)
        ts = data.get('timestamp', 'Unknown')[:16] if data.get('timestamp') else 'Unknown'
        opps = len(data.get('opportunities', []))
        recs = len(data.get('recommendations', []))
        return f"{opps} pairs, {recs} recs (last: {ts})"
    except:
        return "Error"


def get_sentiment():
    if not SENTIMENT_LOG.exists():
        return "No data"
    try:
        with open(SENTIMENT_LOG) as f:
            data = json.load(f)
        summary = data.get('summary', {})
        sentiment = summary.get('overall_sentiment', 'Unknown')
        strength = summary.get('strength', 0)
        breakdown = summary.get('breakdown', {})
        return f"{sentiment} ({strength:.2f}) B:{breakdown.get('bullish',0)} R:{breakdown.get('bearish',0)}"
    except:
        return "Error"


def generate_report():
    lines = [
        "📊 *TRADING BOT STATUS*",
        "",
        f"⏱️ *Uptime:* `{get_uptime()}`",
        "",
        f"🔄 *Last Cycle:* `{get_last_cycle()}`",
        "",
        f"💰 *Balance:* `${get_balance()}` USDT",
        "",
    ]
    
    positions = get_positions()
    if positions:
        lines.append("📈 *Positions:* (synced with Binance)")
        for pos in positions:
            lines.append(f"• `{pos['symbol']}`: {pos['qty']:.4f} @ ${pos['avg_entry']:.2f}")
        lines.append("")
    else:
        lines.extend(["📈 *Positions:* None", ""])
    
    lines.extend([
        f"🔍 *Scanning:* {get_scanning()}",
        "",
        f"🔎 *Discovery:* {get_discovery()}",
        "",
        f"📰 *Sentiment:* {get_sentiment()}",
        "",
        f"_Updated: {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC_"
    ])
    
    return "\n".join(lines)


if __name__ == '__main__':
    print(generate_report())
