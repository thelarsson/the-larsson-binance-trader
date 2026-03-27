#!/usr/bin/env python3
"""IG Markets Trading Bot"""
import json
import os
import sys
import time
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Tuple, List

try:
    import httpx as requests
    USE_HTTPX = True
except ImportError:
    import requests
    USE_HTTPX = False

# Load environment
BASE = Path(__file__).parent.parent
ENV = {}
if (BASE / ".env").exists():
    for line in (BASE / ".env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            ENV[k.strip()] = v.strip()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("ig-trader")

# Add to existing imports - Decision Engine integration
try:
    from decision_engine import DecisionEngine, Signal as DecisionSignal
    DECISION_ENGINE_AVAILABLE = True
except ImportError:
    DECISION_ENGINE_AVAILABLE = False
    logger.warning("Decision engine not available - using fallback logic")

# Config
IG_API_KEY = ENV.get("IG_API_KEY")
IG_ACCOUNT_ID = ENV.get("IG_ACCOUNT_ID")
IG_PASSWORD = ENV.get("IG_PASSWORD")
IG_BASE_URL = ENV.get("IG_BASE_URL", "https://demo-api.ig.com/gateway/deal")
USE_LLM = ENV.get("USE_LLM", "false").lower() == "true"
OLLAMA_MODEL = ENV.get("OLLAMA_MODEL", "")
OLLAMA_BASE_URL = ENV.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

EPICS = [e.strip() for e in ENV.get("EPICS", "IX.D.DAX.IFG.IP").split(",")]
STRATEGY = ENV.get("STRATEGY", "momentum")
TRADE_SIZE_PCT = float(ENV.get("TRADE_SIZE_PCT", "1"))
MAX_POSITIONS = int(ENV.get("MAX_POSITIONS", "3"))
STOP_LOSS_PCT = float(ENV.get("STOP_LOSS_PCT", "2"))
TAKE_PROFIT_PCT = float(ENV.get("TAKE_PROFIT_PCT", "3"))
COOLDOWN_HOURS = float(ENV.get("COOLDOWN_HOURS", "6"))
MAX_DAILY_LOSS_PCT = float(ENV.get("MAX_DAILY_LOSS_PCT", "2"))

# Sentiment/News configuration
SENTIMENT_STALE_HOURS = int(ENV.get("SENTIMENT_STALE_HOURS", "6"))
SENTIMENT_THRESHOLD = float(ENV.get("SENTIMENT_THRESHOLD", "0.3"))

# IG minimum trade sizes (approximate - varies by market)
IG_MIN_SIZES = {
    "CS.D.EURUSD.MINI.IP": 0.5,  # Forex mini
    "CS.D.GBPUSD.MINI.IP": 0.5,
    "IX.D.DAX.IFG.IP": 1.0,      # Indices
    "IX.D.SPTRD.IFE.IP": 1.0,
    "IX.D.NASDAQ.IFE.IP": 1.0,
    "IX.D.DOW.IFE.IP": 1.0,
}

trades_file = BASE / "trades.jsonl"
cooldown_file = BASE / "cooldown.json"
daily_loss_file = BASE / "daily_loss.json"


class IGSession:
    """Manages IG API session with automatic token refresh."""
    
    def __init__(self):
        self.security_token: Optional[str] = None
        self.cst: Optional[str] = None
        self.auth_time: Optional[datetime] = None
        self.auth_headers: dict = {}
    
    def authenticate(self) -> dict:
        """Authenticate with IG and return auth headers."""
        headers = {
            "Content-Type": "application/json",
            "X-IG-API-KEY": IG_API_KEY,
        }
        body = {
            "identifier": IG_ACCOUNT_ID,
            "password": IG_PASSWORD,
        }
        r = requests.post(f"{IG_BASE_URL}/session", headers=headers, json=body)
        r.raise_for_status()
        
        self.security_token = r.headers.get("X-SECURITY-TOKEN")
        self.cst = r.headers.get("CST")
        self.auth_time = datetime.now(timezone.utc)
        self.auth_headers = {
            "Content-Type": "application/json",
            "X-IG-API-KEY": IG_API_KEY,
            "X-SECURITY-TOKEN": self.security_token,
            "CST": self.cst,
        }
        logger.info("Authenticated with IG")
        return self.auth_headers
    
    def get_headers(self) -> dict:
        """Get valid auth headers, refreshing if needed."""
        # Token expires after ~10 minutes (600 seconds), refresh at 8 minutes
        if (self.auth_time is None or 
            (datetime.now(timezone.utc) - self.auth_time).seconds > 480):
            logger.info("Refreshing session token...")
            return self.authenticate()
        return self.auth_headers


# Global session manager
session = IGSession()


def get_auth_token() -> tuple[str, dict]:
    """Authenticate with IG and return security token + headers."""
    headers = session.get_headers()
    return session.security_token, headers


def get_account(auth_headers: dict) -> dict:
    """Get account details."""
    r = requests.get(f"{IG_BASE_URL}/accounts", headers=auth_headers)
    r.raise_for_status()
    return r.json()


def get_market_data(epic: str, auth_headers: dict) -> dict:
    """Get market data for an epic."""
    r = requests.get(f"{IG_BASE_URL}/markets/{epic}", headers=auth_headers)
    r.raise_for_status()
    return r.json()


def get_min_trade_size(epic: str) -> float:
    """Get minimum trade size for an epic."""
    return IG_MIN_SIZES.get(epic, 0.01)


def get_prices(epic: str, resolution: str = "MINUTE", count: int = 50, auth_headers: dict = None) -> list:
    """Get historical prices."""
    r = requests.get(
        f"{IG_BASE_URL}/prices/{epic}?resolution={resolution}&max={count}",
        headers=auth_headers,
    )
    r.raise_for_status()
    return r.json().get("prices", [])


def calculate_ema(prices: List[float], period: int) -> float:
    """Calculate Exponential Moving Average."""
    if len(prices) < period:
        return sum(prices) / len(prices) if prices else 0
    
    # EMA = Price(t) * k + EMA(y) * (1 - k)
    # where k = 2 / (N + 1)
    k = 2 / (period + 1)
    
    # Start with SMA for first EMA value
    ema = sum(prices[:period]) / period
    
    # Calculate EMA for remaining prices
    for price in prices[period:]:
        ema = price * k + ema * (1 - k)
    
    return ema


def calculate_rsi(prices: List[float], period: int = 14) -> float:
    """Calculate Relative Strength Index."""
    if len(prices) < period + 1:
        return 50.0  # Neutral
    
    gains = []
    losses = []
    
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    # Use only the last 'period' values
    gains = gains[-period:]
    losses = losses[-period:]
    
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    
    # If both gain and loss are 0 (flat prices), return neutral RSI
    if avg_loss == 0 and avg_gain == 0:
        return 50.0
    if avg_loss == 0:
        return 100.0  # Only gains
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def find_support_resistance(prices: List[float], lookback: int = 20) -> Tuple[float, float]:
    """Find support and resistance levels from recent price data."""
    if len(prices) < lookback:
        return prices[-1] * 0.99, prices[-1] * 1.01 if prices else (0, 0)
    
    recent = prices[-lookback:]
    resistance = max(recent)
    support = min(recent)
    return support, resistance


def calculate_signal_fallback(prices: list, strategy: str = "momentum") -> str:
    """Calculate trading signal from price data using legacy logic."""
    if len(prices) < 20:
        return "HOLD"
    
    closes = [p.get("closePrice", {}).get("bid", 0) for p in prices if p.get("closePrice")]
    if len(closes) < 20:
        return "HOLD"
    
    if strategy == "momentum":
        # Proper EMA calculation
        ema_9 = calculate_ema(closes, 9)
        ema_20 = calculate_ema(closes, 20)
        
        if ema_9 > ema_20 * 1.001:  # Slight uptrend
            return "BUY"
        elif ema_9 < ema_20 * 0.999:
            return "SELL"
    
    elif strategy == "mean_reversion":
        # RSI and support/resistance logic
        rsi = calculate_rsi(closes, 14)
        support, resistance = find_support_resistance(closes, 20)
        current_price = closes[-1]
        
        # Buy when RSI is oversold and price near support
        if rsi < 30 and current_price <= support * 1.005:
            return "BUY"
        
        # Sell when RSI is overbought and price near resistance
        elif rsi > 70 and current_price >= resistance * 0.995:
            return "SELL"
    
    return "HOLD"


def calculate_signal(prices: list, epic: str, strategy: str = "momentum"):
    """
    Calculate trading signal using Decision Engine when available.
    
    Returns:
        Tuple of (signal_string, decision_signal_object or None, news_context_string)
    """
    # Use Decision Engine if available
    if DECISION_ENGINE_AVAILABLE:
        try:
            engine = DecisionEngine(epic)
            decision_signal = engine.analyze(prices)
            
            # Convert DecisionSignal to string
            signal_map = {
                DecisionSignal.STRONG_BUY: "BUY",
                DecisionSignal.BUY: "BUY",
                DecisionSignal.NEUTRAL: "HOLD",
                DecisionSignal.SELL: "SELL",
                DecisionSignal.STRONG_SELL: "SELL",
            }
            signal_str = signal_map.get(decision_signal.signal, "HOLD")
            
            # Build news context string
            news_parts = []
            sent_data = decision_signal.indicators.get("sentiment", {})
            if sent_data.get("action") and sent_data["action"] != "NEUTRAL":
                news_parts.append(f"Sentiment: {sent_data['action']}")
            if sent_data.get("key_signals"):
                news_parts.append(f"Signals: {', '.join(sent_data['key_signals'][:2])}")
            
            news_context = " | ".join(news_parts) if news_parts else "No news context"
            
            return signal_str, decision_signal, news_context
            
        except Exception as e:
            logger.warning(f"Decision engine failed for {epic}: {e}, using fallback")
    
    # Fallback to legacy logic
    signal_str = calculate_signal_fallback(prices, strategy)
    return signal_str, None, "Legacy signal (no sentiment)"


def llm_veto(signal: str, epic: str, prices: list, model: str) -> bool:
    """Ask LLM if trade should be vetoed."""
    if not USE_LLM or not model:
        return False
    
    current_price = prices[-1].get("closePrice", {}).get("bid", 0) if prices else 0
    prev_price = prices[-2].get("closePrice", {}).get("bid", 0) if len(prices) > 1 else current_price
    change_pct = ((current_price - prev_price) / prev_price * 100) if prev_price else 0
    
    prompt = f"""Evaluate this trade signal for {epic}.
Current price: {current_price}
Previous price: {prev_price}
Price change: {change_pct:.2f}%
Signal: {signal}

Should this trade proceed? Reply with either PROCEED or VETO and a one-sentence reason."""
    
    try:
        r = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=30,
        )
        r.raise_for_status()
        response = r.json().get("response", "").upper()
        return "VETO" in response
    except Exception as e:
        logger.warning(f"LLM veto check failed: {e}")
        return False


def open_position(epic: str, direction: str, size: float, current_price: float, auth_headers: dict) -> dict:
    """Open a position on IG with stop-loss and take-profit orders."""
    # Calculate stop loss and take profit levels
    if direction == "BUY":
        stop_level = current_price * (1 - STOP_LOSS_PCT / 100)
        profit_level = current_price * (1 + TAKE_PROFIT_PCT / 100)
    else:  # SELL/short
        stop_level = current_price * (1 + STOP_LOSS_PCT / 100)
        profit_level = current_price * (1 - TAKE_PROFIT_PCT / 100)
    
    body = {
        "epic": epic,
        "direction": direction,
        "size": size,
        "orderType": "MARKET",
        "currencyCode": "USD",
        "stopLevel": round(stop_level, 5),
        "limitLevel": round(profit_level, 5),
        "guaranteedStop": False,
        "forceOpen": True,
    }
    
    r = requests.post(f"{IG_BASE_URL}/positions", headers=auth_headers, json=body)
    r.raise_for_status()
    return r.json()


def close_position(deal_id: str, epic: str, size: float, direction: str, auth_headers: dict) -> dict:
    """Close a position using the correct IG API endpoint.
    
    IG API requires posting to /positions/otc with dealId and direction
    opposite to the open position.
    """
    # Direction to close is opposite of open position
    close_direction = "SELL" if direction == "BUY" else "BUY"
    
    body = {
        "dealId": deal_id,
        "direction": close_direction,
        "size": size,
        "orderType": "MARKET",
    }
    
    # Use the OTC endpoint for closing positions
    r = requests.post(f"{IG_BASE_URL}/positions/otc", headers=auth_headers, json=body)
    r.raise_for_status()
    return r.json()


def get_positions(auth_headers: dict) -> list:
    """Get open positions."""
    r = requests.get(f"{IG_BASE_URL}/positions", headers=auth_headers)
    r.raise_for_status()
    return r.json().get("positions", [])


def is_in_cooldown(epic: str) -> bool:
    """Check if epic is in cooldown period."""
    if not cooldown_file.exists():
        return False
    
    try:
        cooldowns = json.loads(cooldown_file.read_text())
        if epic in cooldowns:
            last_trade_time = datetime.fromisoformat(cooldowns[epic])
            cooldown_end = last_trade_time + timedelta(hours=COOLDOWN_HOURS)
            if datetime.now(timezone.utc) < cooldown_end:
                logger.info(f"{epic}: in cooldown until {cooldown_end.isoformat()}")
                return True
    except Exception as e:
        logger.warning(f"Error reading cooldown file: {e}")
    
    return False


def set_cooldown(epic: str):
    """Set cooldown for an epic."""
    cooldowns = {}
    if cooldown_file.exists():
        try:
            cooldowns = json.loads(cooldown_file.read_text())
        except Exception:
            pass
    
    cooldowns[epic] = datetime.now(timezone.utc).isoformat()
    cooldown_file.write_text(json.dumps(cooldowns, indent=2))


def get_daily_loss() -> Tuple[float, str]:
    """Get current daily loss amount and the date."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    if not daily_loss_file.exists():
        return 0.0, today
    
    try:
        data = json.loads(daily_loss_file.read_text())
        if data.get("date") != today:
            return 0.0, today  # New day, reset loss
        return data.get("loss", 0.0), today
    except Exception:
        return 0.0, today


def add_daily_loss(amount: float, date: str):
    """Add to daily loss tracking."""
    data = {"date": date, "loss": amount}
    daily_loss_file.write_text(json.dumps(data, indent=2))


def validate_trade_size(epic: str, size: float) -> Tuple[bool, float]:
    """Validate and adjust trade size against IG minimums."""
    min_size = get_min_trade_size(epic)
    
    if size < min_size:
        logger.warning(f"{epic}: position size {size} below minimum {min_size}, adjusting")
        return True, min_size
    
    return True, size


def log_trade(action: str, epic: str, size: float = 0, result: str = "", reason: str = "", pnl: float = 0, news_context: str = ""):
    """Log trade to JSONL file."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "epic": epic,
        "size": size,
        "result": result,
        "reason": reason,
        "pnl": pnl,
        "news_context": news_context,
    }
    with open(trades_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


def main():
    logger.info(f"Strategy: {STRATEGY} | Epics: {EPICS} | LLM: {USE_LLM} | DecisionEngine: {DECISION_ENGINE_AVAILABLE}")
    
    if not all([IG_API_KEY, IG_ACCOUNT_ID, IG_PASSWORD]):
        logger.error("Missing IG credentials")
        sys.exit(1)
    
    # Authenticate
    try:
        security_token, auth_headers = get_auth_token()
        logger.info("Authenticated with IG")
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        sys.exit(1)
    
    # Get account info
    try:
        account = get_account(auth_headers)
        balance = account.get("accounts", [{}])[0].get("balance", {}).get("available", 0)
        logger.info(f"Available balance: ${balance}")
    except Exception as e:
        logger.warning(f"Could not get account: {e}")
        balance = 0
    
    # Check daily loss limit
    daily_loss, today = get_daily_loss()
    max_loss_amount = balance * MAX_DAILY_LOSS_PCT / 100
    if daily_loss >= max_loss_amount:
        logger.warning(f"Daily loss limit reached: ${daily_loss:.2f} >= ${max_loss_amount:.2f}")
        logger.info("=== Cycle complete (daily limit hit) ===")
        return
    
    # Check open positions
    try:
        positions = get_positions(auth_headers)
        logger.info(f"Open positions: {len(positions)}")
    except Exception as e:
        logger.warning(f"Could not get positions: {e}")
        positions = []
    
    # Build epic -> position lookup
    positions_by_epic = {}
    for pos in positions:
        epic = pos.get("market", {}).get("epic")
        if epic:
            positions_by_epic[epic] = pos
    
    # Trading loop
    for epic in EPICS:
        # Refresh auth headers if needed
        auth_headers = session.get_headers()
        
        if len(positions) >= MAX_POSITIONS:
            logger.info(f"Max positions ({MAX_POSITIONS}) reached, skipping {epic}")
            continue
        
        # Check cooldown
        if is_in_cooldown(epic):
            continue
        
        try:
            # Get price data
            prices = get_prices(epic, auth_headers=auth_headers)
            if not prices:
                logger.warning(f"No price data for {epic}")
                continue
            
            current_price = prices[-1].get("closePrice", {}).get("bid", 0)
            if current_price <= 0:
                logger.warning(f"Invalid price for {epic}: {current_price}")
                continue
            
            logger.info(f"{epic}: price=${current_price}")
            
            # Calculate signal using decision engine when available
            signal_str, decision_signal, news_context = calculate_signal(prices, epic, STRATEGY)
            
            # If using decision engine, check should_trade flag
            if decision_signal:
                logger.info(f"{epic}: signal={decision_signal.signal.name}, strength={decision_signal.strength:+.3f}, confidence={decision_signal.confidence:.1%}")
                logger.info(f"{epic}: news_context={news_context}")
                logger.info(f"{epic}: should_trade={decision_signal.should_trade}")
                
                # Skip if decision engine says not to trade
                if not decision_signal.should_trade:
                    logger.info(f"{epic}: Decision engine vetoed trade - {decision_signal.reason}")
                    log_trade("SKIP", epic, 0, "SKIPPED", decision_signal.reason, news_context=news_context)
                    continue
            else:
                logger.info(f"{epic}: signal={signal_str}")
            
            if signal_str == "BUY":
                # Check if already have a position
                if epic in positions_by_epic:
                    logger.info(f"{epic}: already have position, skipping BUY")
                    continue
                
                # Check LLM veto (legacy - only if decision engine not available)
                if USE_LLM and OLLAMA_MODEL and not DECISION_ENGINE_AVAILABLE:
                    if llm_veto(signal_str, epic, prices, OLLAMA_MODEL):
                        logger.info(f"{epic}: LLM vetoed BUY")
                        log_trade("BUY_VETO", epic, 0, "VETOED", "LLM sentiment negative")
                        continue
                
                # Calculate position size
                size = (balance * TRADE_SIZE_PCT / 100) / current_price
                size = round(size, 2)
                
                # Validate trade size
                valid, size = validate_trade_size(epic, size)
                if not valid:
                    logger.warning(f"{epic}: trade size validation failed")
                    continue
                
                if size <= 0:
                    logger.warning(f"{epic}: position size too small ({size})")
                    continue
                
                # Check if we'd exceed daily loss limit with this trade
                potential_loss = size * current_price * STOP_LOSS_PCT / 100
                if daily_loss + potential_loss > max_loss_amount:
                    logger.warning(f"{epic}: trade would exceed daily loss limit")
                    continue
                
                # Open position with stop-loss and take-profit
                result = open_position(epic, "BUY", size, current_price, auth_headers)
                logger.info(f"{epic}: opened BUY position, size={size}, SL={STOP_LOSS_PCT}%, TP={TAKE_PROFIT_PCT}%")
                
                # Build reason with decision engine data
                if decision_signal:
                    reason = f"{decision_signal.reason} | tech={decision_signal.technical_score:+.2f}, sent={decision_signal.sentiment_score:+.2f}"
                else:
                    reason = f"{STRATEGY} signal"
                
                log_trade("BUY", epic, size, "FILLED", reason, news_context=news_context)
                set_cooldown(epic)
                
            elif signal_str == "SELL":
                # Check if we have a position to close
                pos = positions_by_epic.get(epic)
                if pos:
                    deal_id = pos.get("position", {}).get("dealId")
                    pos_size = pos.get("position", {}).get("size", 0)
                    pos_direction = pos.get("position", {}).get("direction", "BUY")
                    
                    if deal_id and pos_size > 0:
                        close_position(deal_id, epic, pos_size, pos_direction, auth_headers)
                        logger.info(f"{epic}: closed {pos_direction} position")
                        
                        if decision_signal:
                            reason = f"{decision_signal.reason} | tech={decision_signal.technical_score:+.2f}, sent={decision_signal.sentiment_score:+.2f}"
                        else:
                            reason = f"{STRATEGY} exit signal"
                        
                        log_trade("SELL", epic, pos_size, "FILLED", reason, news_context=news_context)
                        set_cooldown(epic)
                else:
                    # Support short selling if configured
                    short_selling = ENV.get("ALLOW_SHORT", "false").lower() == "true"
                    if short_selling:
                        # Similar to BUY but with SELL direction
                        size = (balance * TRADE_SIZE_PCT / 100) / current_price
                        size = round(size, 2)
                        
                        valid, size = validate_trade_size(epic, size)
                        if not valid or size <= 0:
                            logger.warning(f"{epic}: short size validation failed")
                            continue
                        
                        result = open_position(epic, "SELL", size, current_price, auth_headers)
                        logger.info(f"{epic}: opened SHORT position, size={size}")
                        log_trade("SHORT", epic, size, "FILLED", f"{STRATEGY} signal", news_context=news_context)
                        set_cooldown(epic)
                    else:
                        logger.info(f"{epic}: no position to sell and short selling disabled")
                    
        except Exception as e:
            logger.error(f"{epic}: error - {e}")
            continue
    
    logger.info("=== Cycle complete ===")


if __name__ == "__main__":
    main()
