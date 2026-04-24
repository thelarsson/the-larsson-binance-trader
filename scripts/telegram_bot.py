#!/usr/bin/env python3
"""
Telegram Bot - SINGLE INSTANCE with file lock and deduplication
Syncs positions with actual Binance account state
"""

import os
import sys
import json
import subprocess
import time
import fcntl
import hmac
import hashlib
from pathlib import Path
from dotenv import load_dotenv
import httpx

load_dotenv()

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
TRADER_DIR = Path('/home/johan/.openclaw/workspace/trading-bots/johan-binance-trader')
TRADER_LOG = TRADER_DIR / 'trader.log'
LOCK_FILE = TRADER_DIR / '.telegram_bot.lock'
SEEN_FILE = TRADER_DIR / '.telegram_bot_seen.json'

# Binance API credentials for position sync
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', '')
BINANCE_SECRET_KEY = os.getenv('BINANCE_SECRET_KEY', '')
BINANCE_BASE_URL = 'https://api.binance.com'


def acquire_lock():
    """Ensure only one instance runs."""
    try:
        global lock_fd
        lock_fd = open(LOCK_FILE, 'w')
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()
        return True
    except:
        print("Another instance is already running!")
        sys.exit(1)


def release_lock():
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except:
        pass


def send(msg):
    if not TOKEN or not CHAT_ID:
        return False
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=15
        )
        return r.status_code == 200
    except:
        return False


def load_seen():
    if SEEN_FILE.exists():
        try:
            with open(SEEN_FILE) as f:
                data = json.load(f)
                return set(data.get('ids', [])), data.get('last_id', 0)
        except:
            pass
    return set(), 0


def save_seen(seen_ids, last_id):
    try:
        with open(SEEN_FILE, 'w') as f:
            json.dump({'ids': list(seen_ids)[-200:], 'last_id': last_id}, f)
    except:
        pass


def get_updates(offset):
    try:
        r = httpx.get(
            f"https://api.telegram.org/bot{TOKEN}/getUpdates",
            params={"offset": offset, "limit": 5},
            timeout=35
        )
        return r.json().get('result', [])
    except:
        return []


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
            f"{BINANCE_BASE_URL}{path}",
            params=signed_params,
            headers={"X-MBX-APIKEY": BINANCE_API_KEY},
            timeout=15
        )
        return r.json()
    except Exception as e:
        print(f"Binance API error: {e}")
        return {}


def get_binance_positions():
    """
    Get actual positions from Binance account - SOURCE OF TRUTH.
    Falls back to local trades.jsonl if API fails.
    Filters out dust positions under $1 USD value.
    """
    positions = {}

    # Try Binance API first
    if BINANCE_API_KEY and BINANCE_SECRET_KEY:
        try:
            account = binance_get("/api/v3/account", {})
            prices = get_binance_prices()  # Get current prices for value calculation
            if account and 'balances' in account:
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

                        # Try to get avg entry price from trade history
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
                return positions
        except Exception as e:
            print(f"Error fetching Binance positions: {e}")

    # Fallback: Calculate from local trade log
    print("Falling back to local trade log for positions")
    return get_positions_from_local()


def get_positions_from_local():
    """Get positions from local trades.jsonl (fallback only). Filters out dust positions under $1 USD."""
    positions = {}
    trades_file = TRADER_DIR / 'trades.jsonl'
    if not trades_file.exists():
        return {}

    try:
        with open(trades_file) as f:
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

        # Get current prices to calculate position values
        prices = get_binance_prices()

        # Convert to final format, filtering out dust positions under $1 USD
        active = {}
        for sym, data in positions.items():
            if data['qty'] > 0.0001:
                avg_entry = data['cost'] / data['qty'] if data['qty'] > 0 else 0
                current_price = prices.get(sym, avg_entry)
                position_value = data['qty'] * current_price
                # Filter out dust positions under $1 USD
                if position_value < 1.0:
                    continue

                active[sym] = {'qty': data['qty'], 'avg_entry': avg_entry}

        return active
    except:
        return {}


def get_binance_prices():
    """Get current prices from Binance API."""
    try:
        r = httpx.get(f"{BINANCE_BASE_URL}/api/v3/ticker/price", timeout=15)
        data = r.json()
        return {item['symbol']: float(item['price']) for item in data}
    except:
        return {}


def get_positions():
    """Main function to get positions - uses Binance API."""
    return get_binance_positions()


def get_prices():
    """Get current market prices."""
    prices = get_binance_prices()
    if prices:
        return prices
    
    # Fallback to log parsing
    try:
        r = subprocess.run(['tail', '-300', str(TRADER_LOG)],
                          capture_output=True, text=True, timeout=10)
        for line in r.stdout.split('\n'):
            if 'signal=' in line and 'price=$' in line:
                for part in line.split():
                    if 'USDT:' in line:
                        symbol = line.split('INFO]')[-1].split(':')[0].strip() + 'USDT'
                    if 'price=$' in part:
                        try:
                            price = float(part.split('$')[1])
                            if 'symbol' in locals():
                                prices[symbol] = price
                        except:
                            pass
    except:
        pass
    return prices


def handle_command(cmd):
    cmd = cmd.lower().strip()
    
    if cmd == '/status':
        r = subprocess.run(['python3', str(TRADER_DIR / 'scripts' / 'get_status.py')],
                          capture_output=True, text=True, timeout=30)
        return r.stdout or "Error getting status"
    
    elif cmd == '/positions':
        pos = get_positions()
        prices = get_prices()
        
        if not pos:
            return "📈 *Positions*: No active positions on Binance account"
        
        lines = ["📈 *Active Positions* (synced with Binance):", ""]
        
        total_value = 0
        total_pnl = 0
        
        for sym in sorted(pos.keys()):
            data = pos[sym]
            qty = data['qty']
            entry = data['avg_entry'] or 0
            current = prices.get(sym, entry)
            value = qty * current
            pnl = ((current - entry) / entry * 100) if entry > 0 else 0
            pnl_usd = (current - entry) * qty
            
            total_value += value
            total_pnl += pnl_usd
            
            emoji = "🟢" if pnl >= 0 else "🔴"
            lines.append(f"• `{sym}`")
            lines.append(f"  Qty: `{qty:.6f}` | Value: `${value:.2f}`")
            if entry:
                lines.append(f"  Entry: `${entry:.4f}` | Current: `${current:.4f}`")
                lines.append(f"  PnL: {emoji} `{pnl:+.2f}%` (${pnl_usd:+.2f})")
            lines.append("")
        
        # Add summary
        total_emoji = "🟢" if total_pnl >= 0 else "🔴"
        lines.append(f"💰 *Total Value:* `${total_value:.2f}`")
        lines.append(f"📊 *Total PnL:* {total_emoji} `${total_pnl:+.2f}`")
        lines.append("")
        lines.append("_(Synced with actual Binance account)_")
        
        return "\n".join(lines)
    
    elif cmd == '/balance':
        if BINANCE_API_KEY and BINANCE_SECRET_KEY:
            try:
                account = binance_get("/api/v3/account", {})
                if account and 'balances' in account:
                    usdt_balance = 0
                    for b in account.get('balances', []):
                        if b['asset'] == 'USDT':
                            usdt_balance = float(b.get('free', 0)) + float(b.get('locked', 0))
                            break
                    return f"💰 *Binance USDT Balance:* `${usdt_balance:.2f}`\n_(Live from API)_"
            except Exception as e:
                return f"Error getting balance: {e}"
        
        # Fallback to log
        r = subprocess.run(['grep', 'USDT balance', str(TRADER_LOG)],
                          capture_output=True, text=True, timeout=5)
        lines = [l for l in r.stdout.strip().split('\n') if l]
        return f"💰 *Balance*: `{lines[-1] if lines else 'Unknown'}`\n_(From log - API unavailable)_"
    
    elif cmd == '/sync':
        """Manually sync positions with Binance."""
        binance_pos = get_binance_positions()
        local_pos = get_positions_from_local()
        
        if not binance_pos and not local_pos:
            return "📈 No positions on Binance or in local records."
        
        messages = []
        messages.append("🔄 *Position Sync Report:*")
        messages.append("")
        
        # Check for mismatches
        mismatches = []
        all_symbols = set(binance_pos.keys()) | set(local_pos.keys())
        
        for sym in all_symbols:
            binance_qty = binance_pos.get(sym, {}).get('qty', 0)
            local_qty = local_pos.get(sym, {}).get('qty', 0)
            
            if abs(binance_qty - local_qty) > 0.0001:
                mismatches.append({
                    'symbol': sym,
                    'binance': binance_qty,
                    'local': local_qty
                })
        
        if mismatches:
            messages.append("⚠️ *Position Mismatches Detected:*")
            for m in mismatches:
                messages.append(f"• `{m['symbol']}`: Binance `{m['binance']:.6f}` vs Local `{m['local']:.6f}`")
            messages.append("")
            messages.append("Bot will use Binance values for trading.")
        else:
            messages.append("✅ All positions synced correctly with Binance.")
        
        return "\n".join(messages)
    
    elif cmd == '/uptime':
        """Check uptime of trading bot."""
        try:
            # Find the main trader process
            r = subprocess.run(['pgrep', '-f', 'trader'],
                              capture_output=True, text=True, timeout=5)
            if r.returncode == 0 and r.stdout.strip():
                # Get the first PID
                pid = r.stdout.strip().split('\n')[0]
                r2 = subprocess.run(['ps', '-p', pid, '-o', 'etime='],
                                   capture_output=True, text=True, timeout=5)
                if r2.returncode == 0:
                    uptime = r2.stdout.strip()
                    return f"⏱️ *Uptime*: `{uptime}`\n✅ Trading bot is running"
            return "⏱️ *Uptime*: `Not running`\n❌ Trading bot is not active"
        except Exception as e:
            return f"⏱️ *Uptime*: `Error`\n⚠️ {str(e)[:30]}"
    
    elif cmd == '/sentiment':
        """Get news sentiment report."""
        import json as json_module
        try:
            sentiment_file = Path('/home/johan/.openclaw/workspace/crypto-news-scraper/crypto_sentiment_report.json')
            if not sentiment_file.exists():
                return "📰 *Sentiment*: No sentiment data available yet."
            
            with open(sentiment_file) as f:
                data = json_module.load(f)
            
            summary = data.get('summary', {})
            sentiment = summary.get('overall_sentiment', 'Unknown')
            strength = summary.get('strength', 0)
            breakdown = summary.get('breakdown', {})
            
            # Get top mentioned coins from summary.coins (new structure)
            coins_data = summary.get('coins', {})
            if coins_data:
                # Sort by mentions and take top 5
                sorted_coins = sorted(coins_data.items(), key=lambda x: x[1].get('mentions', 0), reverse=True)[:5]
                coin_lines = []
                for symbol, coin in sorted_coins:
                    mentions = coin.get('mentions', 0)
                    coin_sent = coin.get('sentiment_score', 0)
                    coin_emoji = "🟢" if coin_sent > 0.6 else "🔴" if coin_sent < 0.4 else "⚪"
                    coin_lines.append(f"• {coin_emoji} `{symbol}`: {mentions} mentions (sentiment: {coin_sent:.2f})")
            else:
                coin_lines = []
            
            emoji = "🟢" if sentiment == "BULLISH" else "🔴" if sentiment == "BEARISH" else "⚪"
            
            return (f"📰 *Market Sentiment* {emoji}\n\n"
                    f"Overall: *{sentiment}* (strength: {strength:.2f})\n\n"
                    f"Breakdown:\n"
                    f"• 🟢 Bullish signals: {breakdown.get('bullish', 0)}\n"
                    f"• 🔴 Bearish signals: {breakdown.get('bearish', 0)}\n"
                    f"• ⚪ Neutral signals: {breakdown.get('neutral', 0)}\n\n"
                    f"📈 *Top Mentioned Coins:*\n"
                    f"{chr(10).join(coin_lines) if coin_lines else 'No coins tracked'}")
        except Exception as e:
            return f"📰 *Sentiment*: Error reading data - {str(e)[:50]}"
    
    elif cmd == '/discovery':
        """Get discovery opportunities."""
        import json as json_module
        try:
            discovery_file = Path('/home/johan/.openclaw/workspace/crypto-news-scraper/discovery_report.json')
            if not discovery_file.exists():
                return "🔍 *Discovery*: No discovery data available yet."
            
            with open(discovery_file) as f:
                data = json_module.load(f)
            
            opportunities = data.get('opportunities', [])
            if not opportunities:
                return "🔍 *Discovery*: No opportunities found."
            
            lines = ["🔍 *Discovery Opportunities:*\n"]
            for opp in opportunities[:10]:  # Top 10
                symbol = opp.get('symbol', 'N/A')
                score = opp.get('combined_score', 0)
                signal = opp.get('signal', 'NEUTRAL')
                news = opp.get('news_mentions', 0)
                emoji = "🟢" if signal == "BULLISH" else "🔴" if signal == "BEARISH" else "⚪"
                lines.append(f"• {emoji} `{symbol}`: score={score:.2f} news={news}x")
            
            return "\n".join(lines)
        except Exception as e:
            return f"🔍 *Discovery*: Error reading data - {str(e)[:50]}"

    elif cmd == '/pairs':
        """Show current PAIRS list from .env"""
        try:
            env_file = TRADER_DIR / '.env'
            pairs_line = "Not configured"
            if env_file.exists():
                with open(env_file) as f:
                    for line in f:
                        if line.startswith('PAIRS='):
                            pairs_line = line.strip().split('=', 1)[1]
                            break
            
            pairs = pairs_line.split(',') if ',' in pairs_line else [pairs_line]
            
            lines = ["📋 *Current PAIRS List*:", ""]
            lines.append(f"Total: {len(pairs)} trading pairs")
            lines.append("")
            
            for i, pair in enumerate(pairs, 1):
                lines.append(f"{i}. `{pair}`")
            
            lines.append("")
            lines.append("_(Updates automatically every hour based on scores)_")
            
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Error reading PAIRS: {str(e)[:50]}"
    
    elif cmd == '/abort_switch':
        """Abort pending strategy switch"""
        import sys
        sys.path.insert(0, str(TRADER_DIR / 'scripts'))
        try:
            from auto_strategy_switcher import ProductionStrategySwitcher
            switcher = ProductionStrategySwitcher()
            if switcher.abort_pending_switch():
                return "✅ *Strategy switch ABORTED*\n\nCurrent strategy remains active. No changes made."
            else:
                return "ℹ️ No pending strategy switch to abort."
        except Exception as e:
            return f"❌ Error: {e}"
    
    elif cmd == '/confirm_switch':
        """Confirm pending strategy switch immediately"""
        import sys
        sys.path.insert(0, str(TRADER_DIR / 'scripts'))
        try:
            from auto_strategy_switcher import ProductionStrategySwitcher
            switcher = ProductionStrategySwitcher()
            if switcher.confirm_early():
                return "✅ *Strategy switch CONFIRMED and EXECUTED*\n\nNew strategy is now active."
            else:
                return "ℹ️ No pending strategy switch to confirm."
        except Exception as e:
            return f"❌ Error: {e}"
    
    elif cmd == '/strategy_status':
        """Check current strategy and pending switches"""
        import sys
        import json
        sys.path.insert(0, str(TRADER_DIR / 'scripts'))
        
        lines = ["📊 *Strategy Status*", ""]
        
        # Load current strategy
        state_file = TRADER_DIR / '.strategy_switcher_state.json'
        if state_file.exists():
            with open(state_file) as f:
                data = json.load(f)
                current = data.get('current_strategy', 'EMA_CROSSOVER')
                last_update = data.get('last_updated', 'Unknown')
                switches = data.get('switches_this_week', 0)
                
                lines.append(f"Current Strategy: *{current}*")
                lines.append(f"Last Updated: {last_update[:16] if last_update != 'Unknown' else 'Unknown'}")
                lines.append(f"Switches This Week: {switches}/1")
        else:
            lines.append("Current Strategy: *EMA_CROSSOVER* (default)")
        
        lines.append("")
        
        # Check pending
        pending_file = TRADER_DIR / '.pending_strategy_switch.json'
        if pending_file.exists():
            try:
                with open(pending_file) as f:
                    data = json.load(f)
                    if data.get('status') != 'aborted':
                        proposed = data.get('proposed_strategy', 'Unknown')
                        execute_after = data.get('execute_after', '')
                        improvement = data.get('expected_improvement', 0)
                        
                        lines.append("⚠️ *PENDING SWITCH*:")
                        lines.append(f"Proposed: *{proposed}*")
                        lines.append(f"Expected Improvement: *{improvement:.2f}%*")
                        if execute_after:
                            lines.append(f"Auto-execute at: *{execute_after[11:16] if len(execute_after) > 16 else 'Unknown'} UTC*")
                        lines.append("")
                        lines.append("To abort: */abort_switch*")
                        lines.append("To confirm now: */confirm_switch*")
                    else:
                        lines.append("✅ No pending switches")
            except:
                lines.append("✅ No pending switches")
        else:
            lines.append("✅ No pending switches")
        
        lines.append("")
        lines.append("Analysis runs daily at 08:00 UTC")
        return "\n".join(lines)
    
    elif cmd == '/signals':
        """Show current trading signals for all pairs"""
        try:
            import sys
            import os
            sys.path.insert(0, str(TRADER_DIR / 'scripts'))
            os.chdir(str(TRADER_DIR))
            
            from trader import get_klines, rsi_signal, ema_signal
            from dotenv import load_dotenv
            load_dotenv()
            
            # Get pairs from .env
            pairs = os.getenv('PAIRS', 'BTCUSDT,ETHUSDT').split(',')
            strategy = os.getenv('STRATEGY', 'ema')
            
            lines = [f"📊 *Trading Signals* ({strategy.upper()})", ""]
            
            # Track signals
            buy_signals = []
            sell_signals = []
            hold_signals = []
            
            for pair in pairs[:20]:  # Limit to first 20
                try:
                    klines = get_klines(pair, '1h', 50)
                    if not klines:
                        continue
                    
                    # Get signal based on strategy
                    if strategy == 'rsi':
                        signal = rsi_signal(klines)
                    elif strategy == 'ema':
                        signal = ema_signal(klines)
                    else:
                        signal = 'HOLD'
                    
                    current_price = klines[-1]['c']
                    
                    if signal == 'BUY':
                        buy_signals.append(f"• 🟢 `{pair}`: ${current_price:,.4f}")
                    elif signal == 'SELL':
                        sell_signals.append(f"• 🔴 `{pair}`: ${current_price:,.4f}")
                    else:
                        hold_signals.append(f"• ⚪ `{pair}`: ${current_price:,.4f}")
                except Exception:
                    continue
            
            # Format output
            if buy_signals:
                lines.append(f"🟢 *BUY Signals ({len(buy_signals)})*:")
                lines.extend(buy_signals)
                lines.append("")
            
            if sell_signals:
                lines.append(f"🔴 *SELL Signals ({len(sell_signals)})*:")
                lines.extend(sell_signals)
                lines.append("")
            
            if hold_signals:
                lines.append(f"⚪ *HOLD ({len(hold_signals)})*:")
                lines.extend(hold_signals)  # Limit shown
                lines.append("")
            
            lines.append(f"Strategy: *{strategy.upper()}*")
            lines.append(f"Checked: {len(buy_signals) + len(sell_signals) + len(hold_signals)} pairs")
            
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Error: {str(e)[:50]}"
    
    elif cmd == '/ema':
        """Show EMA status for top 5 pairs"""
        try:
            # Get PAIRS from .env
            pairs = []
            env_file = TRADER_DIR / '.env'
            if env_file.exists():
                with open(env_file) as f:
                    for line in f:
                        if line.startswith('PAIRS='):
                            pairs = line.strip().split('=', 1)[1].split(',')
                            break
            
            if not pairs:
                return "❌ No PAIRS configured"
            
            lines = ["📊 *EMA Status* (Top 5 pairs):", ""]
            
            import httpx
            
            for pair in pairs[:5]:  # Only top 5 to keep message short
                try:
                    r = httpx.get(f"https://api.binance.com/api/v3/klines?symbol={pair}&interval=1h&limit=50", timeout=5)
                    if r.status_code == 200:
                        klines = r.json()
                        if len(klines) >= 20:
                            closes = [float(k[4]) for k in klines]
                            
                            # Simple EMA calc
                            def ema_calc(prices, period):
                                mult = 2 / (period + 1)
                                ema = prices[0]
                                for p in prices[1:]:
                                    ema = (p * mult) + (ema * (1 - mult))
                                return ema
                            
                            ema_9 = ema_calc(closes[-9:], 9)
                            ema_20 = ema_calc(closes[-20:], 20)
                            
                            if ema_9 > ema_20 * 1.001:
                                status = "🟢"
                            elif ema_9 < ema_20 * 0.999:
                                status = "🔴"
                            else:
                                status = "⚪"
                            
                            lines.append(f"{status} `{pair}`: EMA9={ema_9:.2f} vs EMA20={ema_20:.2f}")
                        else:
                            lines.append(f"⚪ `{pair}`: No data")
                    else:
                        lines.append(f"⚪ `{pair}`: API error")
                except:
                    lines.append(f"⚠️ `{pair}`: Error")
            
            lines.append("")
            lines.append("🟢 = Bullish | 🔴 = Bearish | ⚪ = Neutral")
            lines.append(f"\nTotal {len(pairs)} pairs. Use /pairs for full list.")
            
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Error: {str(e)[:30]}"
    
    elif cmd == '/help':
        return ("📋 *Commands*:\n"
                "/status - Full bot status\n"
                "/positions - Show positions (synced with Binance)\n"
                "/balance - USDT balance (live from Binance)\n"
                "/signals - Current trading signals (BUY/SELL/HOLD)\n"
                "/pairs - Show current PAIRS list\n"
                "/ema - Show EMA status for all pairs\n"
                "/sync - Sync/verify positions with Binance\n"
                "/uptime - Bot uptime\n"
                "/sentiment - News sentiment report\n"
                "/discovery - Trading opportunities\n"
                "/strategy_status - Check current strategy and pending switches\n"
                "/abort_switch - Cancel pending strategy switch\n"
                "/confirm_switch - Execute pending switch immediately\n"
                "/help - This message")
    
    else:
        return f"❓ Unknown: `{cmd}`. Use /help"


def handle_chat_message(text):
    """Handle regular (non-command) chat messages."""
    text_lower = text.lower().strip()
    
    # Simple keyword-based responses for common messages
    if any(greeting in text_lower for greeting in ['hello', 'hi', 'hey', 'sup']):
        return "👋 Hello! I'm your trading bot. Use /help to see available commands."
    
    elif 'how are you' in text_lower or 'how are things' in text_lower:
        return "🤖 I'm running smoothly! Use /status for bot details or /positions to see your trades."
    
    elif any(thanks in text_lower for thanks in ['thanks', 'thank you', 'thx']):
        return "You're welcome! 👍"
    
    elif any(bye in text_lower for bye in ['bye', 'goodbye', 'see you']):
        return "👋 Goodbye! Ping me anytime with /help for commands."
    
    elif 'price' in text_lower or 'market' in text_lower:
        return "📊 I can show position prices! Try /positions to see your active positions with current prices."
    
    elif 'trade' in text_lower or 'trading' in text_lower or 'buy' in text_lower or 'sell' in text_lower:
        return "💹 Trading is handled automatically by the bot. Use /positions to see active trades or /status for bot info."
    
    elif 'profit' in text_lower or 'pnl' in text_lower or 'gain' in text_lower:
        return "💰 Check /positions to see your PnL on all active positions!"
    
    elif 'balance' in text_lower or 'money' in text_lower or 'funds' in text_lower:
        return "💵 Use /balance to check your USDT balance."
    
    elif any(help_word in text_lower for help_word in ['help', 'commands', 'what can you do']):
        return handle_command('/help')
    
    elif '?' in text:
        return "🤔 I see you have a question! Try /help for a list of commands, or ask me about prices, positions, or the bot status."
    
    else:
        # Generic response for unrecognized messages
        return f"I received: \"{text}\"\n\nI'm a trading bot - use /help to see what I can do!"


def main():
    acquire_lock()
    
    seen_ids, last_id = load_seen()
    next_offset = last_id + 1 if last_id else 0
    
    print(f"Bot started. PID: {os.getpid()}, next_offset: {next_offset}")
    send("🤖 *The Larsson Binance Trader* ready!\n\nUse /help for commands")
    
    try:
        while True:
            try:
                updates = get_updates(next_offset)
                
                if not updates:
                    time.sleep(2)
                    continue
                
                print(f"Processing {len(updates)} updates")
                
                for upd in updates:
                    upd_id = upd.get('update_id', 0)
                    
                    # CRITICAL: Update offset FIRST
                    next_offset = upd_id + 1
                    
                    # Skip if already seen
                    if upd_id in seen_ids:
                        print(f"SKIP {upd_id}")
                        continue
                    
                    # Mark as seen BEFORE processing
                    seen_ids.add(upd_id)
                    save_seen(seen_ids, upd_id)
                    
                    msg = upd.get('message', {})
                    chat = str(msg.get('chat', {}).get('id', ''))
                    text = msg.get('text', '')
                    
                    if chat != str(CHAT_ID):
                        continue
                    
                    # Handle bot commands (messages starting with /)
                    if text.startswith('/'):
                        cmd = text.split()[0].lower()
                        print(f"CMD: {cmd} (id:{upd_id})")
                        resp = handle_command(cmd)
                    # Handle regular chat messages
                    else:
                        print(f"MSG: {text[:50]}... (id:{upd_id})")
                        resp = handle_chat_message(text)
                    
                    if resp:
                        send(resp)
                        print(f"Sent reply")
                    
                    time.sleep(1)  # Prevent flood
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(5)
    
    finally:
        release_lock()
        print("Bot stopped")


if __name__ == '__main__':
    main()
