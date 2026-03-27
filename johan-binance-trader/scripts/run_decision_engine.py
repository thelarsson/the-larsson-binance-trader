#!/usr/bin/env python3
"""
Integration helper to run decision engine and provide signals to trader.py

This module bridges the decision engine with the existing trading bot.
It can be imported by trader.py or run standalone for testing.

USAGE:
    # Standalone (prints report)
    python3 run_decision_engine.py BTCUSDT 1h

    # As module in trader.py
    from run_decision_engine import get_decision_signal
    signal = get_decision_signal("BTCUSDT")
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict

# Import decision engine
try:
    from decision_engine import DecisionEngine, Signal, format_signal_report
    DECISION_ENGINE_AVAILABLE = True
except ImportError:
    DECISION_ENGINE_AVAILABLE = False


def get_decision_signal(symbol: str, interval: str = "1h", max_age_minutes: int = 30) -> Optional[Dict]:
    """
    Get the latest decision signal for a symbol.
    
    First checks for cached signal file, then runs analysis if stale.
    
    Args:
        symbol: Trading pair (e.g., "BTCUSDT")
        interval: Kline interval for technical analysis
        max_age_minutes: Maximum age of cached signal before refresh
        
    Returns:
        Dict with signal data, or None if unavailable
    """
    if not DECISION_ENGINE_AVAILABLE:
        return None
    
    signal_file = Path(__file__).parent.parent / "crypto-news-scraper" / "decision_signal.json"
    
    # Check for cached signal
    if signal_file.exists():
        try:
            with open(signal_file) as f:
                cached = json.load(f)
            
            # Check age
            ts_str = cached.get("timestamp")
            if ts_str:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                age = datetime.now(timezone.utc) - ts
                if age < timedelta(minutes=max_age_minutes):
                    # Check if symbol matches
                    if cached.get("symbol") == symbol:
                        return cached
        except Exception:
            pass
    
    # Run fresh analysis
    try:
        engine = DecisionEngine(symbol)
        signal = engine.analyze(interval)
        engine.close()
        
        return {
            "symbol": symbol,
            "interval": interval,
            "signal": signal.signal.name,
            "strength": signal.strength,
            "confidence": signal.confidence,
            "should_trade": signal.should_trade,
            "position_action": signal.position_action,
            "reason": signal.reason,
            "technical_score": signal.technical_score,
            "sentiment_score": signal.sentiment_score,
            "indicators": signal.indicators,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        print(f"Decision engine error: {e}")
        return None


def should_enter_trade(symbol: str, direction: str = "long") -> tuple:
    """
    Determine if we should enter a trade.
    
    Args:
        symbol: Trading pair
        direction: "long" or "short"
        
    Returns:
        Tuple of (should_enter: bool, reason: str)
    """
    signal = get_decision_signal(symbol)
    
    if not signal:
        return False, "No signal available"
    
    strength = signal.get("strength", 0)
    tech_score = signal.get("technical_score", 0)
    sent_score = signal.get("sentiment_score", 0)
    
    if direction.lower() == "long":
        # Strong buy signal
        if signal.get("signal") == "STRONG_BUY":
            return True, f"Strong buy signal (strength: {strength:.2f})"
        # Buy signal with confirmation
        elif signal.get("signal") == "BUY":
            if tech_score > 0.2 and sent_score > -0.1:
                return True, f"Buy signal with confirmation (tech: {tech_score:.2f}, sent: {sent_score:.2f})"
        # Neutral but technically bullish
        elif signal.get("signal") == "NEUTRAL":
            if tech_score > 0.3 and sent_score > 0:
                return True, f"Technically bullish with positive sentiment"
        
        return False, f"Signal: {signal.get('signal')}, not favorable for long entry"
    
    elif direction.lower() == "short":
        # Strong sell signal
        if signal.get("signal") == "STRONG_SELL":
            return True, f"Strong sell signal (strength: {strength:.2f})"
        # Sell signal with confirmation
        elif signal.get("signal") == "SELL":
            if tech_score < -0.2 and sent_score < 0.1:
                return True, f"Sell signal with confirmation (tech: {tech_score:.2f}, sent: {sent_score:.2f})"
        
        return False, f"Signal: {signal.get('signal')}, not favorable for short entry"
    
    return False, f"Unknown direction: {direction}"


def should_exit_trade(symbol: str, position_type: str = "long") -> tuple:
    """
    Determine if we should exit a position.
    
    Args:
        symbol: Trading pair
        position_type: "long" or "short"
        
    Returns:
        Tuple of (should_exit: bool, reason: str)
    """
    signal = get_decision_signal(symbol)
    
    if not signal:
        return False, "No signal available"
    
    strength = signal.get("strength", 0)
    tech_score = signal.get("technical_score", 0)
    
    if position_type.lower() == "long":
        # Exit long on strong sell
        if signal.get("signal") in ["STRONG_SELL", "SELL"]:
            return True, f"Exit signal: {signal.get('signal')} (strength: {strength:.2f})"
        # Exit on technical reversal
        if tech_score < -0.4:
            return True, f"Technical reversal detected (score: {tech_score:.2f})"
        
        return False, f"Signal: {signal.get('signal')}, holding position"
    
    elif position_type.lower() == "short":
        # Exit short on strong buy
        if signal.get("signal") in ["STRONG_BUY", "BUY"]:
            return True, f"Exit signal: {signal.get('signal')} (strength: {strength:.2f})"
        # Exit on technical reversal
        if tech_score > 0.4:
            return True, f"Technical reversal detected (score: {tech_score:.2f})"
        
        return False, f"Signal: {signal.get('signal')}, holding position"
    
    return False, f"Unknown position type: {position_type}"


def get_trading_context(symbol: str) -> str:
    """
    Get a human-readable context string for logging.
    
    Args:
        symbol: Trading pair
        
    Returns:
        str: Context string for logging
    """
    signal = get_decision_signal(symbol)
    
    if not signal:
        return "No decision signal available"
    
    parts = [
        f"Signal: {signal.get('signal')}",
        f"Strength: {signal.get('strength'):+.2f}",
        f"Tech: {signal.get('technical_score'):+.2f}",
        f"Sent: {signal.get('sentiment_score'):+.2f}",
        f"Trade: {'YES' if signal.get('should_trade') else 'NO'}"
    ]
    
    return " | ".join(parts)


# Example integration with trader.py
def integrate_with_trader():
    """
    Example of how to integrate with trader.py
    
    In trader.py, add this to make_decision() or similar:
    
    ```python
    # At top of file:
    from run_decision_engine import (
        get_decision_signal,
        should_enter_trade,
        should_exit_trade,
        get_trading_context
    )
    
    # In make_decision() or main loop:
    def should_buy(symbol, klines, current_price, balance):
        # ... existing technical checks ...
        
        # Add decision engine check
        should_enter, reason = should_enter_trade(symbol, "long")
        if not should_enter:
            log.info(f"Decision engine says NO: {reason}")
            return False
        
        log.info(f"Decision engine: {get_trading_context(symbol)}")
        
        # ... rest of logic ...
    
    def should_sell(symbol, position, current_price):
        # ... existing checks ...
        
        # Add decision engine check for early exit
        should_exit, reason = should_exit_trade(symbol, "long")
        if should_exit:
            log.info(f"Decision engine exit signal: {reason}")
            return True, reason
        
        # ... rest of logic ...
    ```
    """
    pass


if __name__ == "__main__":
    # Standalone execution
    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    interval = sys.argv[2] if len(sys.argv) > 2 else "1h"
    
    print(f"\n🔍 Running decision engine for {symbol} ({interval})...\n")
    
    signal = get_decision_signal(symbol, interval)
    
    if signal:
        print(f"Signal: {signal['signal']}")
        print(f"Strength: {signal['strength']:+.3f}")
        print(f"Confidence: {signal['confidence']:.1%}")
        print(f"Should Trade: {signal['should_trade']}")
        print(f"Action: {signal['position_action'] or 'HOLD'}")
        print(f"Reason: {signal['reason']}")
        print()
        
        should_enter_long, reason = should_enter_trade(symbol, "long")
        print(f"Enter Long: {'✅' if should_enter_long else '❌'} - {reason}")
        
        should_exit_long, reason = should_exit_trade(symbol, "long")
        print(f"Exit Long: {'✅' if should_exit_long else '❌'} - {reason}")
        
        print()
        print(f"Context: {get_trading_context(symbol)}")
    else:
        print("❌ Could not get decision signal")
        print("Make sure crypto_scraper.py has been run recently.")