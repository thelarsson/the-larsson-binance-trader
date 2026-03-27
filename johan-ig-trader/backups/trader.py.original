#!/usr/bin/env python3
"""IG Markets Trading Bot"""
import json
import os
import sys
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

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

trades_file = BASE / "trades.jsonl"
cooldown_file = BASE / "cooldown.json"


def get_auth_token() -> tuple[str, dict]:
    """Authenticate with IG and return security token + headers."""
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
    security_token = r.headers.get("X-SECURITY-TOKEN")
    cst = r.headers.get("CST")
    auth_headers = {
        "Content-Type": "application/json",
        "X-IG-API-KEY": IG_API_KEY,
        "X-SECURITY-TOKEN": security_token,
        "CST": cst,
    }
    return security_token, auth_headers


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


def get_prices(epic: str, resolution: str = "MINUTE", count: int = 50, auth_headers: dict = None) -> list:
    """Get historical prices."""
    r = requests.get(
        f"{IG_BASE_URL}/prices/{epic}?resolution={resolution}&max={count}",
        headers=auth_headers,
    )
    r.raise_for_status()
    return r.json().get("prices", [])


def calculate_signal(prices: list, strategy: str = "momentum") -> str:
    """Calculate trading signal from price data."""
    if len(prices) < 20:
        return "HOLD"
    
    closes = [p.get("closePrice", {}).get("bid", 0) for p in prices if p.get("closePrice")]
    if len(closes) < 20:
        return "HOLD"
    
    ema_9 = sum(closes[-9:]) / 9
    ema_20 = sum(closes[-20:]) / 20
    
    if strategy == "momentum":
        if ema_9 > ema_20 * 1.001:  # Slight uptrend
            return "BUY"
        elif ema_9 < ema_20 * 0.999:
            return "SELL"
    
    return "HOLD"


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


def open_position(epic: str, direction: str, size: float, auth_headers: dict) -> dict:
    """Open a position on IG."""
    body = {
        "epic": epic,
        "direction": direction,
        "size": size,
        "orderType": "MARKET",
        "currencyCode": "USD",
    }
    r = requests.post(f"{IG_BASE_URL}/positions", headers=auth_headers, json=body)
    r.raise_for_status()
    return r.json()


def close_position(deal_id: str, auth_headers: dict) -> dict:
    """Close a position."""
    body = {"dealId": deal_id}
    r = requests.delete(f"{IG_BASE_URL}/positions", headers=auth_headers, json=body)
    r.raise_for_status()
    return r.json()


def get_positions(auth_headers: dict) -> list:
    """Get open positions."""
    r = requests.get(f"{IG_BASE_URL}/positions", headers=auth_headers)
    r.raise_for_status()
    return r.json().get("positions", [])


def log_trade(action: str, epic: str, size: float = 0, result: str = "", reason: str = ""):
    """Log trade to JSONL file."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "epic": epic,
        "size": size,
        "result": result,
        "reason": reason,
    }
    with open(trades_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


def main():
    logger.info(f"Strategy: {STRATEGY} | Epics: {EPICS} | LLM: {USE_LLM}")
    
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
    
    # Check open positions
    try:
        positions = get_positions(auth_headers)
        logger.info(f"Open positions: {len(positions)}")
    except Exception as e:
        logger.warning(f"Could not get positions: {e}")
        positions = []
    
    # Trading loop
    for epic in EPICS:
        if len(positions) >= MAX_POSITIONS:
            logger.info(f"Max positions ({MAX_POSITIONS}) reached, skipping {epic}")
            continue
        
        try:
            # Get price data
            prices = get_prices(epic, auth_headers=auth_headers)
            if not prices:
                logger.warning(f"No price data for {epic}")
                continue
            
            current_price = prices[-1].get("closePrice", {}).get("bid", 0)
            logger.info(f"{epic}: price=${current_price}")
            
            # Calculate signal
            signal = calculate_signal(prices, STRATEGY)
            logger.info(f"{epic}: signal={signal}")
            
            if signal == "BUY":
                # Check LLM veto
                if USE_LLM and OLLAMA_MODEL:
                    if llm_veto(signal, epic, prices, OLLAMA_MODEL):
                        logger.info(f"{epic}: LLM vetoed BUY")
                        log_trade("BUY_VETO", epic, 0, "VETOED", "LLM sentiment negative")
                        continue
                
                # Calculate position size
                size = (balance * TRADE_SIZE_PCT / 100) / current_price if current_price > 0 else 0
                size = round(size, 2)
                
                if size < 0.01:
                    logger.warning(f"{epic}: position size too small ({size})")
                    continue
                
                # Open position
                result = open_position(epic, "BUY", size, auth_headers)
                logger.info(f"{epic}: opened BUY position, size={size}")
                log_trade("BUY", epic, size, "FILLED", "momentum signal")
                
            elif signal == "SELL":
                # Check if we have a position to close
                pos = next((p for p in positions if p.get("market", {}).get("epic") == epic), None)
                if pos:
                    deal_id = pos.get("position", {}).get("dealId")
                    if deal_id:
                        close_position(deal_id, auth_headers)
                        logger.info(f"{epic}: closed position")
                        log_trade("SELL", epic, 0, "FILLED", "momentum exit")
                else:
                    logger.info(f"{epic}: no position to sell")
                    
        except Exception as e:
            logger.error(f"{epic}: error - {e}")
            continue
    
    logger.info("=== Cycle complete ===")


if __name__ == "__main__":
    main()
