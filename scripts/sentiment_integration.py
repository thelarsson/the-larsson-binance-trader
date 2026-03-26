#!/usr/bin/env python3
"""
Sentiment Integration for Trading Bots
Reads sentiment signals from crypto_scraper and provides LLM-style sentiment.

This module can be imported by trading bots to incorporate news sentiment
into their decision-making process.
"""

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict

# Path to sentiment signal file (relative to this file)
SCRIPT_DIR = Path(__file__).parent
SIGNAL_FILE = SCRIPT_DIR / "trading_signal.json"
REPORT_FILE = SCRIPT_DIR / "crypto_sentiment_report.json"


def get_sentiment_signal(max_age_hours: int = 6) -> Optional[Dict]:
    """Load the latest sentiment signal.
    
    Args:
        max_age_hours: Maximum age of signal before it's considered stale.
        
    Returns:
        Dict with signal data, or None if stale/missing.
    """
    if not SIGNAL_FILE.exists():
        return None
    
    try:
        with open(SIGNAL_FILE) as f:
            signal = json.load(f)
        
        # Check age
        ts_str = signal.get("timestamp")
        if ts_str:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            age = datetime.now(timezone.utc) - ts
            if age > timedelta(hours=max_age_hours):
                return None
        
        return signal
    except Exception:
        return None


def get_sentiment_report(max_age_hours: int = 6) -> Optional[Dict]:
    """Load the full sentiment report.
    
    Args:
        max_age_hours: Maximum age of report before it's considered stale.
        
    Returns:
        Dict with full report, or None if stale/missing.
    """
    if not REPORT_FILE.exists():
        return None
    
    try:
        with open(REPORT_FILE) as f:
            report = json.load(f)
        
        # Check age
        ts_str = report.get("timestamp")
        if ts_str:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            age = datetime.now(timezone.utc) - ts
            if age > timedelta(hours=max_age_hours):
                return None
        
        return report
    except Exception:
        return None


def llm_sentiment_from_news(symbol: str, default: float = 0.5) -> float:
    """Get sentiment score compatible with trading bot's LLM sentiment function.
    
    This mirrors the llm_sentiment() function in trader.py but uses news sentiment.
    
    Args:
        symbol: Trading pair (e.g., "BTCUSDT")
        default: Default value if no signal available
        
    Returns:
        float: Sentiment score from 0.0 (very bearish) to 1.0 (very bullish)
    """
    signal = get_sentiment_signal()
    
    if not signal:
        return default
    
    # Convert signal (-1 to 1) to 0-1 scale
    # signal = -1 -> 0.0, signal = 0 -> 0.5, signal = 1 -> 1.0
    news_sentiment = signal.get("signal", 0)
    llm_score = (news_sentiment + 1) / 2  # Convert to 0-1 scale
    
    # Clamp to valid range
    llm_score = max(0.0, min(1.0, llm_score))
    
    return llm_score


def get_trading_context() -> str:
    """Get a human-readable context string for news sentiment.
    
    Returns:
        str: Context string describing current news sentiment.
    """
    report = get_sentiment_report()
    
    if not report:
        return "No recent news sentiment data available."
    
    summary = report.get("summary", {})
    signal = report.get("trading_signal", {})
    
    sentiment = summary.get("overall_sentiment", "NEUTRAL")
    strength = summary.get("strength", 0.5)
    top_signals = summary.get("top_signals", [])
    
    context_parts = [f"Current news sentiment: {sentiment} (strength: {strength:.2f})"]
    
    if top_signals:
        signals_str = ", ".join([f"{s[0]} ({s[1]} mentions)" for s in top_signals[:3]])
        context_parts.append(f"Key signals: {signals_str}")
    
    breakdown = summary.get("breakdown", {})
    if breakdown:
        context_parts.append(f"Article breakdown: {breakdown.get('bullish', 0)} bullish, {breakdown.get('bearish', 0)} bearish, {breakdown.get('neutral', 0)} neutral")
    
    return " | ".join(context_parts)


def should_adjust_position(sentiment_threshold: float = 0.3) -> Optional[str]:
    """Determine if sentiment suggests position adjustment.
    
    Args:
        sentiment_threshold: Minimum signal strength to trigger recommendation.
        
    Returns:
        str: "reduce_long", "reduce_short", or None
    """
    signal = get_sentiment_signal()
    
    if not signal:
        return None
    
    news_sentiment = signal.get("signal", 0)
    confidence = signal.get("confidence", 0.5)
    
    # Only recommend if confidence is decent
    if confidence < 0.4:
        return None
    
    if news_sentiment < -sentiment_threshold:
        return "reduce_long"  # Bearish news, consider reducing longs
    elif news_sentiment > sentiment_threshold:
        return "reduce_short"  # Bullish news, consider reducing shorts
    
    return None


# Example integration with trading bot
def integrate_with_trader():
    """Example of how to integrate with trader.py
    
    In trader.py, modify the decision logic to include news sentiment:
    
    ```python
    # Add import
    from sentiment_integration import llm_sentiment_from_news, get_trading_context
    
    # In make_decision() or similar:
    def make_decision(symbol, klines, current_price, balance):
        # ... existing logic ...
        
        # Get news sentiment
        news_sentiment = llm_sentiment_from_news(symbol)
        
        # Combine with LLM sentiment (if using)
        if USE_LLM:
            llm_score = llm_sentiment(symbol, klines)
            combined = (news_sentiment * 0.3 + llm_score * 0.7)  # Weight news 30%
        else:
            combined = news_sentiment
        
        # Use combined sentiment in decision
        if combined > 0.65 and htf_trend == "UP":
            # Strong bullish signal
            pass
        elif combined < 0.35 and htf_trend == "DOWN":
            # Strong bearish signal
            pass
        
        # Log context
        log.info(f"News sentiment: {get_trading_context()}")
        
        # ... rest of logic ...
    ```
    """
    pass


if __name__ == "__main__":
    # Test the integration
    print("=" * 50)
    print("📊 Sentiment Integration Test")
    print("=" * 50)
    
    signal = get_sentiment_signal()
    if signal:
        print(f"Signal: {signal['signal']:+.2f}")
        print(f"Action: {signal['action']}")
        print(f"Confidence: {signal['confidence']}")
        print(f"Key signals: {signal['key_signals']}")
    else:
        print("No recent sentiment signal available.")
        print("Run: python3 crypto_scraper.py [--content]")
    
    print()
    print("Context:")
    print(get_trading_context())
    
    print()
    print("LLM-style score:", llm_sentiment_from_news("BTCUSDT"))
    
    adjustment = should_adjust_position()
    if adjustment:
        print(f"Position recommendation: {adjustment}")
    else:
        print("No position adjustment recommended.")