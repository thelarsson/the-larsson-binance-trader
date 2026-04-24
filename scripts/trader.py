#!/usr/bin/env python3
"""Binance Spot Trader — LLM-enhanced autonomous trading bot with news sentiment integration."""
import os, sys, json, time, logging, hmac, hashlib
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from dotenv import load_dotenv
import httpx

# Decision Engine Integration
USE_DECISION_ENGINE = os.getenv("USE_DECISION_ENGINE", "true").lower() == "true"
DECISION_SENTIMENT_WEIGHT = float(os.getenv("DECISION_SENTIMENT_WEIGHT", "0.4"))

# Auto-Discovery Integration
USE_AUTO_DISCOVERY = os.getenv("USE_AUTO_DISCOVERY", "true").lower() == "true"
DISCOVERY_MIN_SCORE = float(os.getenv("DISCOVERY_MIN_SCORE", "0.3"))
DISCOVERY_AUTO_ADD = os.getenv("DISCOVERY_AUTO_ADD", "false").lower() == "true"

try:
    from decision_engine import DecisionEngine, Signal
    from run_decision_engine import should_enter_trade, should_exit_trade, get_trading_context
    DECISION_ENGINE_AVAILABLE = True
except ImportError:
    DECISION_ENGINE_AVAILABLE = False

try:
    from auto_discovery import check_for_new_pairs, get_discovered_pairs, get_pair_opportunity, format_discovery_summary
    DISCOVERY_AVAILABLE = True
except ImportError:
    DISCOVERY_AVAILABLE = False
    DECISION_ENGINE_AVAILABLE = False

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("trader")

API_KEY = os.environ["BINANCE_API_KEY"]
SECRET_KEY = os.environ["BINANCE_SECRET_KEY"]
LLM_API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY", "")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "").strip()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
PAIRS = os.getenv("PAIRS", "BTCUSDT").split(",")
STRATEGY = os.getenv("STRATEGY", "momentum")
TRADE_SIZE_PCT = float(os.getenv("TRADE_SIZE_PCT", "5"))
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", "5"))
TP_PCT = float(os.getenv("TAKE_PROFIT_PCT", "5"))
SL_PCT = float(os.getenv("STOP_LOSS_PCT", "3"))
USE_LLM = os.getenv("USE_LLM", "true").lower() == "true"
DCA_AMOUNT = float(os.getenv("DCA_AMOUNT_USDT", "50"))
COOLDOWN_HOURS = float(os.getenv("COOLDOWN_HOURS", "12"))
MAX_DAILY_LOSS_PCT = float(os.getenv("MAX_DAILY_LOSS_PCT", "2"))
MAX_TRADES_PER_PAIR_PER_DAY = int(os.getenv("MAX_TRADES_PER_PAIR_PER_DAY", "2"))
USDT_RESERVE_PCT = float(os.getenv("USDT_RESERVE_PCT", "40"))
KLINE_INTERVAL = os.getenv("KLINE_INTERVAL", "1h")
HTF_INTERVAL = os.getenv("HTF_INTERVAL", "15m")
HTF_PERIOD = int(os.getenv("HTF_PERIOD", "20"))
FAST_EMA_PERIOD = int(os.getenv("FAST_EMA_PERIOD", "9"))
SLOW_EMA_PERIOD = int(os.getenv("SLOW_EMA_PERIOD", "20"))
EXIT_CONFIRM_CANDLES = int(os.getenv("EXIT_CONFIRM_CANDLES", "2"))
MAX_TOTAL_ENTRIES_PER_DAY = int(os.getenv("MAX_TOTAL_ENTRIES_PER_DAY", "2"))
ANTI_CHASE_PCT = float(os.getenv("ANTI_CHASE_PCT", "1.0"))
REENTRY_COOLDOWN_HOURS = float(os.getenv("REENTRY_COOLDOWN_HOURS", "4"))
HTF_TREND_MIN_PCT = float(os.getenv("HTF_TREND_MIN_PCT", "0.15"))
MIN_POSITION_VALUE_USD = float(os.getenv("MIN_POSITION_VALUE_USD", "1.0"))

BASE = "https://api.binance.com"
TRADES_LOG = Path("trades.jsonl")


def load_trade_history():
    if not TRADES_LOG.exists():
        return []
    rows = []
    with open(TRADES_LOG) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def get_position_state(symbol):
    qty = 0.0
    cost = 0.0
    for row in load_trade_history():
        result = row.get("result", "")
        if row.get("symbol") != symbol or result not in ("FILLED", "SYNCED"):
            continue
        side = row.get("side")
        trade_qty = float(row.get("qty", 0) or 0)
        trade_price = float(row.get("price", 0) or 0)
        if side == "BUY":
            qty += trade_qty
            cost += trade_qty * trade_price
        elif side == "SELL":
            sell_qty = min(qty, trade_qty)
            avg_price = (cost / qty) if qty > 0 else 0
            cost -= sell_qty * avg_price
            qty -= sell_qty
            if qty <= 1e-12:
                qty = 0.0
                cost = 0.0
        # Handle SYNCED entries (position already closed externally)
        if result == "SYNCED":
            qty = 0.0
            cost = 0.0
    avg_entry = (cost / qty) if qty > 0 else None
    return {"qty": qty, "cost": cost, "avg_entry": avg_entry}


def risk_signal(symbol, current_price):
    position = get_position_state(symbol, verify_binance=True)  # Verify with Binance
    avg_entry = position["avg_entry"]
    if not avg_entry or position["qty"] <= 0:
        return None, position
    # Ignore positions under $1
    if position["qty"] * current_price < MIN_POSITION_VALUE_USD:
        return None, position

    stop_price = avg_entry * (1 - SL_PCT / 100)
    take_profit_price = avg_entry * (1 + TP_PCT / 100)

    if current_price <= stop_price:
        return "STOP_LOSS", position
    if current_price >= take_profit_price:
        return "TAKE_PROFIT", position
    return None, position


def parse_ts(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def current_open_symbols(current_prices=None):
    """Get symbols with actual positions on Binance account. Filters out dust positions under $1 USD."""
    symbols = set()

    # Get actual positions from Binance (source of truth)
    binance_positions = get_binance_positions()

    for symbol, pos in binance_positions.items():
        qty = pos.get("qty", 0)
        if qty <= 0.0001:
            continue
        # Check position value (dust filter already applied in get_binance_positions, but double-check)
        price = current_prices.get(symbol) if current_prices else pos.get("avg_entry", 0)
        if price and qty * price >= MIN_POSITION_VALUE_USD:
            symbols.add(symbol)

    # Check configured pairs - but ONLY use Binance as source of truth
    # Don't add positions that exist locally but not on Binance (manual sales)
    for symbol in PAIRS:
        if symbol in binance_positions:
            # Already handled above
            continue
        # If not on Binance, check local history for info only (don't count as open)
        pos = get_position_state(symbol)
        if pos["qty"] > 0:
            log.info(f"{symbol}: Local position exists but not on Binance. Treating as closed.")

    return symbols


def trades_today(symbol=None):
    today = datetime.now(timezone.utc).date()
    rows = []
    for row in load_trade_history():
        ts = parse_ts(row.get("ts"))
        if not ts or ts.date() != today:
            continue
        if row.get("result") != "FILLED":
            continue
        if symbol and row.get("symbol") != symbol:
            continue
        rows.append(row)
    return rows


def realized_pnl_today():
    pnl = 0.0
    state = {}
    for row in trades_today():
        symbol = row.get("symbol")
        side = row.get("side")
        qty = float(row.get("qty", 0) or 0)
        price = float(row.get("price", 0) or 0)
        if not symbol or qty <= 0:
            continue
        pos = state.setdefault(symbol, {"qty": 0.0, "cost": 0.0})
        if side == "BUY":
            pos["qty"] += qty
            pos["cost"] += qty * price
        elif side == "SELL" and pos["qty"] > 0:
            sell_qty = min(pos["qty"], qty)
            avg_entry = (pos["cost"] / pos["qty"]) if pos["qty"] > 0 else 0.0
            pnl += (price - avg_entry) * sell_qty
            pos["cost"] -= avg_entry * sell_qty
            pos["qty"] -= sell_qty
            if pos["qty"] <= 1e-12:
                pos["qty"] = 0.0
                pos["cost"] = 0.0
    return pnl


def daily_loss_limit_hit(balance):
    pnl = realized_pnl_today()
    threshold = balance * (MAX_DAILY_LOSS_PCT / 100)
    return pnl <= -threshold, pnl, threshold


def in_cooldown(symbol):
    stop_cutoff = datetime.now(timezone.utc).timestamp() - COOLDOWN_HOURS * 3600
    reentry_cutoff = datetime.now(timezone.utc).timestamp() - REENTRY_COOLDOWN_HOURS * 3600
    for row in reversed(load_trade_history()):
        if row.get("symbol") != symbol:
            continue
        ts = parse_ts(row.get("ts"))
        if not ts:
            continue
        if row.get("side") == "SELL" and row.get("exit_reason") == "STOP_LOSS" and ts.timestamp() >= stop_cutoff:
            return True, ts
        if row.get("side") == "SELL" and ts.timestamp() >= reentry_cutoff:
            return True, ts
        if ts.timestamp() < min(stop_cutoff, reentry_cutoff):
            break
    return False, None

def sign(params: dict) -> dict:
    params["timestamp"] = int(time.time() * 1000)
    query = urlencode(params)
    params["signature"] = hmac.new(SECRET_KEY.encode(), query.encode(), hashlib.sha256).hexdigest()
    return params

def api_get(path, params=None):
    with httpx.Client(timeout=15) as c:
        if params and "signature" in params:
            r = c.get(f"{BASE}{path}", params=params, headers={"X-MBX-APIKEY": API_KEY})
        else:
            r = c.get(f"{BASE}{path}", params=params or {})
        return r.json()

def api_post(path, params):
    with httpx.Client(timeout=15) as c:
        r = c.post(f"{BASE}{path}", params=sign(params), headers={"X-MBX-APIKEY": API_KEY})
        return r.json()

def get_symbol_filters(symbol):
    info = api_get("/api/v3/exchangeInfo", {"symbol": symbol})
    symbols = info.get("symbols", [])
    if not symbols:
        return {}
    filters = {f.get("filterType"): f for f in symbols[0].get("filters", [])}
    return filters

def floor_to_step(value, step):
    value_dec = Decimal(str(value))
    step_dec = Decimal(str(step))
    if step_dec <= 0:
        return value_dec
    return (value_dec / step_dec).to_integral_value(rounding=ROUND_DOWN) * step_dec

def format_quantity(symbol, quantity, price=None):
    filters = get_symbol_filters(symbol)
    lot = filters.get("LOT_SIZE", {})
    min_qty = Decimal(str(lot.get("minQty", 0) or 0))
    step = Decimal(str(lot.get("stepSize", 0) or 0))
    qty = floor_to_step(quantity, step) if step else Decimal(str(quantity))
    if qty < min_qty:
        return None, f"qty {qty} below minQty {min_qty}"
    min_notional_filter = filters.get("MIN_NOTIONAL") or filters.get("NOTIONAL") or {}
    min_notional = Decimal(str(min_notional_filter.get("minNotional", 0) or 0))
    if price and min_notional and qty * Decimal(str(price)) < min_notional:
        return None, f"notional {(qty * Decimal(str(price))):.4f} below minNotional {min_notional}"
    qty_str = format(qty.normalize(), 'f')
    return qty_str, None

def get_klines(symbol, interval=KLINE_INTERVAL, limit=50):
    data = api_get("/api/v3/klines", {"symbol": symbol, "interval": interval, "limit": limit})
    return [{"t": k[0], "o": float(k[1]), "h": float(k[2]), "l": float(k[3]), "c": float(k[4]), "v": float(k[5])} for k in data]

def ema(prices, period):
    k = 2 / (period + 1)
    e = prices[0]
    for p in prices[1:]:
        e = p * k + e * (1 - k)
    return e

def rsi(prices, period=14):
    deltas = [prices[i+1] - prices[i] for i in range(len(prices)-1)]
    gains = [d if d > 0 else 0 for d in deltas[-period:]]
    losses = [-d if d < 0 else 0 for d in deltas[-period:]]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0: return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def bollinger(prices, period=20, std_mult=2):
    sma = sum(prices[-period:]) / period
    variance = sum((p - sma) ** 2 for p in prices[-period:]) / period
    std = variance ** 0.5
    return sma - std_mult * std, sma, sma + std_mult * std

def llm_sentiment(symbol, klines):
    """Get sentiment score combining LLM analysis with news sentiment."""
    # Start with base LLM sentiment
    base_sentiment = 0.5
    
    if USE_LLM:
        prices = [k["c"] for k in klines[-10:]]
        vol = [k["v"] for k in klines[-10:]]
        prompt = f"""Rate market sentiment for {symbol} on a scale from 0.0 (very bearish) to 1.0 (very bullish).
Use only the structured market data below.
Last 10 closes: {[round(p,2) for p in prices]}
Volume trend: {'increasing' if vol[-1] > sum(vol[:-1])/len(vol[:-1]) else 'decreasing'}
Current RSI: {rsi(prices):.0f}
Reply with ONLY the numeric score, nothing else."""

        if OLLAMA_MODEL:
            try:
                with httpx.Client(timeout=30) as c:
                    resp = c.post(
                        f"{OLLAMA_BASE_URL}/api/chat",
                        json={
                            "model": OLLAMA_MODEL,
                            "stream": False,
                            "messages": [
                                {"role": "system", "content": "You output only a single number between 0.0 and 1.0."},
                                {"role": "user", "content": prompt},
                            ],
                        },
                    )
                resp.raise_for_status()
                data = resp.json()
                text = data.get("message", {}).get("content", "0.5").strip()
                base_sentiment = float(text.split()[0].strip(".,"))
            except Exception as exc:
                log.warning(f"Ollama sentiment fallback (error: {exc})")

        if not OLLAMA_MODEL and LLM_API_KEY:
            try:
                with httpx.Client(timeout=30) as c:
                    resp = c.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
                        json={
                            "model": "gpt-4o-mini",
                            "temperature": 0,
                            "max_tokens": 10,
                            "messages": [
                                {"role": "system", "content": "You output only a single number between 0.0 and 1.0."},
                                {"role": "user", "content": prompt},
                            ],
                        },
                    )
                resp.raise_for_status()
                data = resp.json()
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "0.5").strip()
                base_sentiment = float(text.split()[0].strip(".,"))
            except Exception as exc:
                log.warning(f"OpenAI sentiment fallback (error: {exc})")

    # Incorporate news sentiment from decision engine
    if USE_DECISION_ENGINE and DECISION_ENGINE_AVAILABLE:
        try:
            from sentiment_integration import llm_sentiment_from_news
            news_sentiment = llm_sentiment_from_news(symbol, default=0.5)
            # Combine: weight news sentiment based on DECISION_SENTIMENT_WEIGHT
            combined = base_sentiment * (1 - DECISION_SENTIMENT_WEIGHT) + news_sentiment * DECISION_SENTIMENT_WEIGHT
            log.info(f"Sentiment: LLM={base_sentiment:.2f}, News={news_sentiment:.2f}, Combined={combined:.2f}")
            return combined
        except Exception as e:
            log.warning(f"News sentiment integration failed: {e}")
    
    return base_sentiment

def get_balance(asset="USDT"):
    info = api_get("/api/v3/account", sign({}))
    for b in info.get("balances", []):
        if b["asset"] == asset:
            return float(b["free"])
    return 0


def get_binance_positions():
    """Get actual positions from Binance account - the source of truth. Filters out dust positions under $1 USD."""
    info = api_get("/api/v3/account", sign({}))
    positions = {}
    # Get current prices to calculate position values
    prices_data = api_get("/api/v3/ticker/price")
    prices = {p['symbol']: float(p['price']) for p in prices_data} if isinstance(prices_data, list) else {}
    for b in info.get("balances", []):
        asset = b["asset"]
        free = float(b.get("free", 0))
        locked = float(b.get("locked", 0))
        total = free + locked
        if total > 0.0001 and asset != "USDT":
            # Try to get avg price from recent trades
            symbol = f"{asset}USDT"
            current_price = prices.get(symbol, 0)
            position_value = total * current_price
            # Filter out dust positions under $1 USD
            if position_value < MIN_POSITION_VALUE_USD:
                continue
            avg_entry = None
            try:
                trades = api_get("/api/v3/myTrades", sign({"symbol": symbol, "limit": 50}))
                buy_qty = 0
                buy_cost = 0
                for t in trades:
                    if t.get("isBuyer"):
                        qty = float(t.get("qty", 0))
                        price = float(t.get("price", 0))
                        buy_qty += qty
                        buy_cost += qty * price
                if buy_qty > 0:
                    avg_entry = buy_cost / buy_qty
            except:
                pass
            positions[symbol] = {"qty": total, "avg_entry": avg_entry}
    return positions


def get_position_state(symbol, verify_binance=False, current_price=None):
    """
    Get position state from local trade log, optionally verifying with Binance.

    Args:
        symbol: Trading pair symbol
        verify_binance: If True, check actual Binance account and warn on mismatch
        current_price: Current market price for dust position filtering (optional)
    """
    qty = 0.0
    cost = 0.0
    for row in load_trade_history():
        result = row.get("result", "")
        if row.get("symbol") != symbol or result not in ("FILLED", "SYNCED"):
            continue
        side = row.get("side")
        trade_qty = float(row.get("qty", 0) or 0)
        trade_price = float(row.get("price", 0) or 0)
        if side == "BUY":
            qty += trade_qty
            cost += trade_qty * trade_price
        elif side == "SELL":
            sell_qty = min(qty, trade_qty)
            avg_price = (cost / qty) if qty > 0 else 0
            cost -= sell_qty * avg_price
            qty -= sell_qty
            if qty <= 1e-12:
                qty = 0.0
                cost = 0.0
        # Handle SYNCED entries (position already closed externally)
        if result == "SYNCED":
            qty = 0.0
            cost = 0.0
    avg_entry = (cost / qty) if qty > 0 else None

    # Filter out dust positions under $1 USD
    if current_price and qty > 0:
        position_value = qty * current_price
        if position_value < MIN_POSITION_VALUE_USD:
            qty = 0.0
            cost = 0.0
            avg_entry = None

    # Verify with Binance if requested
    if verify_binance:
        try:
            binance_positions = get_binance_positions()
            binance_qty = binance_positions.get(symbol, {}).get("qty", 0)
            if abs(qty - binance_qty) > 0.0001:
                log.warning(f"{symbol}: Position mismatch! Local: {qty:.6f}, Binance: {binance_qty:.6f}. Using Binance value.")
                # Update local calculation to match Binance reality
                qty = binance_qty
                cost = binance_qty * (avg_entry or 0)
        except Exception as e:
            log.warning(f"Could not verify position with Binance: {e}")

    return {"qty": qty, "cost": cost, "avg_entry": avg_entry}

def place_order(symbol, side, quantity, extra=None, market_price=None):
    qty_str, qty_error = format_quantity(symbol, quantity, market_price)
    if qty_error:
        log.warning(f"ORDER {side} skipped for {symbol}: {qty_error}")
        result = {"status": "SKIPPED", "msg": qty_error}
        payload = {"ts": datetime.now(timezone.utc).isoformat(), "symbol": symbol,
            "side": side, "qty": quantity, "result": result.get("status", "UNKNOWN"),
            "price": float(market_price or 0)
        }
        if extra:
            payload.update(extra)
        with open(TRADES_LOG, "a") as f:
            f.write(json.dumps(payload) + "\n")
        return result

    params = {"symbol": symbol, "side": side, "type": "MARKET", "quantity": qty_str}
    result = api_post("/api/v3/order", params)
    log.info(f"ORDER {side}: {symbol} qty={qty_str} -> {result.get('status', 'UNKNOWN')} {result.get('msg', '')}")
    
    # Handle SELL failure - sync with Binance to avoid repeated attempts
    if side == "SELL" and result.get('status') != 'FILLED':
        error_msg = result.get('msg', '').lower()
        if 'insufficient balance' in error_msg or 'insufficient asset' in error_msg:
            # Verify actual Binance balance
            try:
                base_asset = symbol.replace("USDT", "")
                actual_balance = get_balance(base_asset)
                if actual_balance * (market_price or 0) < MIN_POSITION_VALUE_USD:
                    log.info(f"SELL failed but position already closed on Binance. Syncing local state.")
                    # Log a 'SYNCED' entry to clear local position
                    payload = {"ts": datetime.now(timezone.utc).isoformat(), "symbol": symbol,
                        "side": "SELL", "qty": float(qty_str), "result": "SYNCED",
                        "price": float(market_price or 0), "exit_reason": "ALREADY_CLOSED"
                    }
                    if extra:
                        payload.update(extra)
                    with open(TRADES_LOG, "a") as f:
                        f.write(json.dumps(payload) + "\n")
                    return result
            except Exception as e:
                log.warning(f"Could not verify position after failed SELL: {e}")
    
    payload = {"ts": datetime.now(timezone.utc).isoformat(), "symbol": symbol,
        "side": side, "qty": float(qty_str), "result": result.get("status", "UNKNOWN"),
        "price": float(result.get("fills", [{}])[0].get("price", 0)) if result.get("fills") else float(market_price or 0)
    }
    if extra:
        payload.update(extra)
    with open(TRADES_LOG, "a") as f:
        f.write(json.dumps(payload) + "\n")
    return result

def bullish_htf_filter(klines):
    prices = [k["c"] for k in klines]
    if len(prices) <= HTF_PERIOD:
        return False
    trend_ema = ema(prices, HTF_PERIOD)
    prev_trend_ema = ema(prices[:-1], HTF_PERIOD)
    return prices[-1] > trend_ema and trend_ema > prev_trend_ema


def momentum_signal(klines, htf_klines=None):
    prices = [k["c"] for k in klines]
    fast_ema = ema(prices, FAST_EMA_PERIOD)
    slow_ema = ema(prices, SLOW_EMA_PERIOD)
    current = prices[-1]
    htf_ok = bullish_htf_filter(htf_klines) if htf_klines else True
    if htf_ok and current > slow_ema and fast_ema > slow_ema:
        return "BUY"
    below_count = sum(1 for p in prices[-EXIT_CONFIRM_CANDLES:] if p < slow_ema)
    if fast_ema < slow_ema or below_count >= EXIT_CONFIRM_CANDLES:
        return "SELL"
    return "HOLD"

def mean_reversion_signal(klines):
    prices = [k["c"] for k in klines]
    r = rsi(prices)
    lower, mid, upper = bollinger(prices)
    current = prices[-1]
    if r < 30 and current <= lower * 1.02: return "BUY"
    if r > 70 or current >= upper * 0.98: return "SELL"
    return "HOLD"

def rsi_signal(klines, htf_klines=None):
    """RSI Strategy with optional HTF filter."""
    prices = [k["c"] for k in klines]
    r = rsi(prices)
    current = prices[-1]
    
    # HTF filter check
    htf_ok = bullish_htf_filter(htf_klines) if htf_klines else True
    
    # Buy signal: RSI oversold (< 30) and HTF confirms
    if htf_ok and r < 30:
        return "BUY"
    
    # Sell signal: RSI overbought (> 70)
    if r > 70:
        return "SELL"
    
    return "HOLD"

def ema_signal(klines, htf_klines=None):
    """EMA Crossover Strategy with optional HTF filter."""
    prices = [k["c"] for k in klines]
    fast_ema = ema(prices, 9)  # Fast EMA 9-period
    slow_ema = ema(prices, 20)  # Slow EMA 20-period
    current = prices[-1]
    
    # HTF filter check
    htf_ok = bullish_htf_filter(htf_klines) if htf_klines else True
    
    # Buy signal: fast EMA crosses above slow EMA, price above slow EMA, HTF confirms
    if htf_ok and current > slow_ema and fast_ema > slow_ema:
        # Check if fast just crossed above slow (recent candles)
        prev_fast = ema(prices[:-1], 9)
        prev_slow = ema(prices[:-1], 20)
        if fast_ema > slow_ema and prev_fast <= prev_slow:
            return "BUY"
        # Also buy if sustained uptrend
        if fast_ema > slow_ema * 1.001:  # Fast slightly above slow
            return "BUY"
    
    # Sell signal: fast EMA below slow EMA or price drops below
    below_count = sum(1 for p in prices[-3:] if p < slow_ema)
    if fast_ema < slow_ema or below_count >= 2:
        return "SELL"
    
    return "HOLD"

def run():
    log.info(f"Strategy: {STRATEGY} | Pairs: {PAIRS} | Interval: {KLINE_INTERVAL} | HTF: {HTF_INTERVAL} | AntiChase: {ANTI_CHASE_PCT}% | HTFMinGap: {HTF_TREND_MIN_PCT}%")
    log.info(f"LLM: {USE_LLM} | Decision Engine: {USE_DECISION_ENGINE and DECISION_ENGINE_AVAILABLE} | Sentiment Weight: {DECISION_SENTIMENT_WEIGHT}")
    
    # Auto-discovery: Check for new opportunities
    active_pairs = list(PAIRS)
    if USE_AUTO_DISCOVERY and DISCOVERY_AVAILABLE:
        try:
            new_pairs = check_for_new_pairs(active_pairs)
            if new_pairs:
                log.info(f"🔍 Discovery: Found {len(new_pairs)} new opportunities: {new_pairs}")
                if DISCOVERY_AUTO_ADD:
                    active_pairs = active_pairs + new_pairs
                    log.info(f"🔍 Discovery: Auto-added pairs, now trading: {active_pairs}")
                else:
                    log.info(f"🔍 Discovery: Consider adding to PAIRS: {','.join(new_pairs)}")
        except Exception as e:
            log.warning(f"Discovery check failed: {e}")
    
    balance = get_balance("USDT")
    log.info(f"USDT balance: ${balance:.2f}")

    if balance < 10:
        log.error("Insufficient USDT balance")
        return

    stop_day, pnl_today, daily_threshold = daily_loss_limit_hit(balance)
    if stop_day:
        log.error(f"Daily loss limit hit: pnl=${pnl_today:.2f} threshold=${daily_threshold:.2f}")
        return

    reserve_usdt = balance * (USDT_RESERVE_PCT / 100)

    for symbol in active_pairs:
        try:
            # Check if pair is discoverable
            if USE_AUTO_DISCOVERY and DISCOVERY_AVAILABLE:
                opp = get_pair_opportunity(symbol)
                if opp:
                    log.info(f"  Discovery data: score={opp.get('combined_score', 0):+.2f} news={opp.get('news_mentions', 0)}x {opp.get('news_sentiment', 'NEUTRAL')}")
            
            klines = get_klines(symbol, KLINE_INTERVAL, 50)
            if not klines:
                continue
            htf_klines = get_klines(symbol, HTF_INTERVAL, 50) if STRATEGY == "momentum" else None

            if STRATEGY == "momentum":
                signal = momentum_signal(klines, htf_klines)
            elif STRATEGY == "mean_reversion":
                signal = mean_reversion_signal(klines)
            elif STRATEGY == "ema":
                signal = ema_signal(klines, htf_klines)
            elif STRATEGY == "rsi":
                signal = rsi_signal(klines, htf_klines)
            elif STRATEGY == "dca":
                signal = "BUY"
            else:
                signal = "HOLD"

            current_price = klines[-1]["c"]
            current_prices = {symbol: current_price}
            open_symbols = current_open_symbols(current_prices)
            risk_event, position = risk_signal(symbol, current_price)
            avg_entry = position["avg_entry"]
            if avg_entry:
                stop_price = avg_entry * (1 - SL_PCT / 100)
                take_profit_price = avg_entry * (1 + TP_PCT / 100)
                log.info(
                    f"{symbol}: price=${current_price:.2f} signal={signal} avg_entry=${avg_entry:.2f} "
                    f"stop=${stop_price:.2f} take_profit=${take_profit_price:.2f}"
                )
            else:
                log.info(f"{symbol}: price=${current_price:.2f} signal={signal}")

            if risk_event in {"STOP_LOSS", "TAKE_PROFIT"}:
                held = get_balance(symbol.replace("USDT", ""))
                if held * current_price > MIN_POSITION_VALUE_USD:
                    log.info(f"  Risk exit triggered: {risk_event}")
                    place_order(symbol, "SELL", held, {"exit_reason": risk_event})
                else:
                    log.info("  Risk exit triggered but no sellable position found")
                continue

            if signal == "BUY":
                # Get current positions from Binance (source of truth) before making decisions
                open_symbols = current_open_symbols({symbol: current_price})
                if symbol in open_symbols:
                    log.info("  Skip BUY: already holding this pair")
                    continue
                if len(open_symbols) >= MAX_POSITIONS:
                    log.info(f"  Skip BUY: MAX_POSITIONS reached ({MAX_POSITIONS})")
                    continue
                cooldown, cooldown_ts = in_cooldown(symbol)
                if cooldown:
                    log.info(f"  Skip BUY: cooldown active since {cooldown_ts.isoformat()}")
                    continue
                pair_trades_today = len(trades_today(symbol))
                if pair_trades_today >= MAX_TRADES_PER_PAIR_PER_DAY:
                    log.info(f"  Skip BUY: trade cap reached for {symbol} ({pair_trades_today})")
                    continue
                total_entries_today = len([r for r in trades_today() if r.get("side") == "BUY"])
                if total_entries_today >= MAX_TOTAL_ENTRIES_PER_DAY:
                    log.info(f"  Skip BUY: total daily entry cap reached ({total_entries_today})")
                    continue

                # Decision engine check
                if USE_DECISION_ENGINE and DECISION_ENGINE_AVAILABLE:
                    try:
                        should_enter, reason = should_enter_trade(symbol, "long")
                        if not should_enter:
                            log.info(f"  Decision Engine VETO — {reason}")
                            continue
                        log.info(f"  Decision Engine: {get_trading_context(symbol)}")
                    except Exception as e:
                        log.warning(f"  Decision engine check failed: {e}")

                if USE_LLM:
                    sentiment = llm_sentiment(symbol, klines)
                    log.info(f"  LLM sentiment: {sentiment:.2f}")
                    if sentiment < 0.35:
                        log.info("  LLM VETO — bearish sentiment")
                        continue

                if STRATEGY == "dca":
                    trade_usdt = DCA_AMOUNT
                else:
                    trade_usdt = balance * (TRADE_SIZE_PCT / 100)

                available_usdt = max(0.0, balance - reserve_usdt)
                trade_usdt = min(trade_usdt, available_usdt)
                qty = trade_usdt / current_price if current_price > 0 else 0
                if trade_usdt >= 10:
                    place_order(symbol, "BUY", qty, {"entry_strategy": STRATEGY})
                else:
                    log.info(f"  Skip BUY: usable trade size ${trade_usdt:.2f} below $10 minimum")

            elif signal == "SELL":
                # Decision engine early exit check
                if USE_DECISION_ENGINE and DECISION_ENGINE_AVAILABLE and avg_entry:
                    try:
                        should_exit, reason = should_exit_trade(symbol, "long")
                        if should_exit:
                            log.info(f"  Decision Engine early exit: {reason}")
                            base_asset = symbol.replace("USDT", "")
                            held = get_balance(base_asset)
                            if held * current_price > MIN_POSITION_VALUE_USD:
                                place_order(symbol, "SELL", held, {"exit_reason": f"DECISION_ENGINE: {reason}"})
                                continue
                    except Exception as e:
                        log.warning(f"  Decision engine exit check failed: {e}")
                
                base_asset = symbol.replace("USDT", "")
                held = get_balance(base_asset)
                if held * current_price > 10:
                    place_order(symbol, "SELL", held, {"exit_reason": "SIGNAL"})
                else:
                    log.info(f"  No {base_asset} position to sell")

        except Exception as e:
            log.error(f"{symbol} error: {e}")

    log.info("=== Cycle complete ===")

if __name__ == "__main__":
    run()
