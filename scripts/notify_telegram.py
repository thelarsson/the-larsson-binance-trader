#!/usr/bin/env python3
"""Notify to Telegram — trades, discovery, and research updates."""
import os, json, time
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
import httpx

load_dotenv()

TRADES_LOG = Path('/home/johan/.openclaw/workspace/trading-bots/johan-binance-trader/trades.jsonl')
DISCOVERY_LOG = Path('/home/johan/.openclaw/workspace/crypto-news-scraper/discovery_report.json')
SENTIMENT_LOG = Path('/home/johan/.openclaw/workspace/crypto-news-scraper/crypto_sentiment_report.json')
STATE_FILE = Path('/home/johan/.openclaw/workspace/trading-bots/johan-binance-trader/.notify-state.json')

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# Track what we've already notified
STATE = {
    "last_trade_line": 0,
    "last_discovery_time": None,
    "last_sentiment_time": None,
    "notified_opportunities": []
}


def load_state():
    global STATE
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                STATE.update(json.load(f))
        except Exception:
            pass


def save_state():
    with open(STATE_FILE, 'w') as f:
        json.dump(STATE, f, indent=2)


def send_telegram(message, parse_mode="Markdown"):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"[NOTIFY] Telegram not configured: {message[:50]}...")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": parse_mode
        }
        with httpx.Client(timeout=15) as c:
            r = c.post(url, json=payload)
            r.raise_for_status()
        print(f"[NOTIFY] Sent to Telegram: {message[:50]}...")
        return True
    except Exception as e:
        print(f"[NOTIFY] Failed to send Telegram: {e}")
        return False


def format_trade_message(row):
    """Format a trade notification."""
    side = row.get('side', '?')
    symbol = row.get('symbol', '?')
    qty = row.get('qty', '?')
    price = row.get('price', '?')
    ts = row.get('ts', '')
    reason = row.get('exit_reason', '')
    
    if side == 'BUY':
        entry_str = row.get('entry_strategy', 'SIGNAL')
        return f"""🟢 *BUY FILLED*

📊 `{symbol}`
💰 Qty: `{qty}`
💵 Price: `${price}`
🎯 Strategy: `{entry_str}`
🕐 `{ts[:19]}Z`"""
    else:
        emoji = "🔴" if reason == "STOP_LOSS" else "✅" if reason == "TAKE_PROFIT" else "⚪"
        return f"""{emoji} *SELL FILLED*

📊 `{symbol}`
💰 Qty: `{qty}`
💵 Price: `${price}`
📍 Trigger: `{reason}`
🕐 `{ts[:19]}Z`"""


def notify_trades():
    """Check for new trades and notify."""
    if not TRADES_LOG.exists():
        return
    
    with open(TRADES_LOG) as f:
        lines = f.readlines()
    
    last_line = STATE.get("last_trade_line", 0)
    new_lines = lines[last_line:]
    
    if not new_lines:
        return
    
    # Track which trade IDs we've already notified
    notified_ids = STATE.get("notified_trade_ids", [])
    newly_notified = []
    
    for line in new_lines:
        line = line.strip()
        if not line:
            continue
        
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        
        # Only notify successful FILLED trades
        if row.get('result') != 'FILLED':
            continue
        
        # Create unique ID for this trade (symbol + side + timestamp)
        trade_id = f"{row.get('symbol')}_{row.get('side')}_{row.get('ts')}"
        
        # Skip if already notified
        if trade_id in notified_ids:
            continue
        
        msg = format_trade_message(row)
        if send_telegram(msg):
            newly_notified.append(trade_id)
            time.sleep(0.5)  # Rate limit
    
    # Update state
    STATE["last_trade_line"] = len(lines)
    if newly_notified:
        STATE["notified_trade_ids"] = (notified_ids + newly_notified)[-100:]  # Keep last 100
        save_state()


def notify_discovery():
    """Check for new discovery opportunities and notify."""
    if not DISCOVERY_LOG.exists():
        return
    
    try:
        with open(DISCOVERY_LOG) as f:
            data = json.load(f)
    except Exception:
        return
    
    ts_str = data.get("timestamp", "")
    
    # Check if we've already notified this discovery
    if STATE.get("last_discovery_time") == ts_str:
        return
    
    new_pairs = data.get("new_pairs_to_add", [])
    recommendations = data.get("recommendations", [])
    
    # Filter out already notified
    notified = STATE.get("notified_opportunities", [])
    new_opportunities = [p for p in new_pairs if p not in notified]
    
    if not new_opportunities:
        return
    
    # Build message
    lines = ["🔍 *NEW OPPORTUNITIES FOUND*", ""]
    
    for i, pair in enumerate(new_opportunities[:5], 1):
        # Find opportunity details
        opp = next((o for o in data.get("opportunities", []) if o.get("symbol") == pair), None)
        if opp:
            score = opp.get("combined_score", 0)
            signal = opp.get("signal", "NEUTRAL")
            price = opp.get("price", 0)
            change = opp.get("price_change_24h", 0)
            
            signal_emoji = "🟢" if "BUY" in signal else "🔴" if "SELL" in signal else "🟡"
            change_emoji = "📈" if change > 0 else "📉" if change < 0 else "➡️"
            
            lines.append(f"{i}. {signal_emoji} `{pair}`")
            lines.append(f"   Score: `{score:+.2f}` | {change_emoji} `{change:+.1f}%`")
            lines.append(f"   Signal: `{signal}` | Price: `${price:.4f}`")
            lines.append("")
        else:
            lines.append(f"{i}. `{pair}`")
            lines.append("")
    
    lines.append(f"_" * 20)
    lines.append(f"🕐 `{ts_str[:19]}Z`")
    
    # Add to PAIRS suggestion
    if new_opportunities:
        lines.append("")
        lines.append(f"💡 Add to PAIRS:")
        lines.append(f"`{','.join(new_opportunities[:3])}`")
    
    msg = "\n".join(lines)
    if send_telegram(msg):
        STATE["last_discovery_time"] = ts_str
        STATE["notified_opportunities"] = notified + new_opportunities
        # Keep only last 50
        STATE["notified_opportunities"] = STATE["notified_opportunities"][-50:]
        save_state()


def notify_sentiment():
    """Notify on significant sentiment changes."""
    if not SENTIMENT_LOG.exists():
        return
    
    try:
        with open(SENTIMENT_LOG) as f:
            data = json.load(f)
    except Exception:
        return
    
    ts_str = data.get("timestamp", "")
    
    # Check if we've already notified this sentiment
    if STATE.get("last_sentiment_time") == ts_str:
        return
    
    summary = data.get("summary", {})
    overall = summary.get("overall_sentiment", "NEUTRAL")
    strength = summary.get("strength", 0)
    breakdown = summary.get("breakdown", {})
    top_signals = summary.get("top_signals", [])
    
    # Only notify on significant changes
    if overall == "NEUTRAL" or strength < 0.3:
        return
    
    # Build message
    emoji = "🟢" if overall == "BULLISH" else "🔴" if overall == "BEARISH" else "🟡"
    
    lines = [
        f"{emoji} *MARKET SENTIMENT: {overall}*",
        "",
        f"Strength: `{strength:.2f}`",
        f"Bullish: `{breakdown.get('bullish', 0)}` | Bearish: `{breakdown.get('bearish', 0)}` | Neutral: `{breakdown.get('neutral', 0)}`",
        ""
    ]
    
    if top_signals:
        lines.append("📊 *Key Signals:*")
        for signal, count in top_signals[:5]:
            lines.append(f"  • `{signal}` ({count}x)")
        lines.append("")
    
    lines.append(f"_" * 20)
    lines.append(f"🕐 `{ts_str[:19]}Z`")
    
    msg = "\n".join(lines)
    if send_telegram(msg):
        STATE["last_sentiment_time"] = ts_str
        save_state()


def main():
    load_state()
    
    # Check for new trades
    notify_trades()
    
    # Check for new discovery
    notify_discovery()
    
    # Check for sentiment changes
    notify_sentiment()


if __name__ == '__main__':
    main()