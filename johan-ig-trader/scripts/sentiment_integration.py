#!/usr/bin/env python3
"""
Sentiment Integration for IG Trading Bot

Reads sentiment signals from ig_news_scraper and provides trading context
for IG Markets instruments (DAX, S&P 500, NASDAQ, EUR/USD, commodities).
"""

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List

# Path to sentiment files
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
SIGNAL_FILE = DATA_DIR / "news_sentiment.json"
REPORT_FILE = DATA_DIR / "news_sentiment_report.json"

# Epic to market mapping (reverse of scraper's MARKET_KEYWORDS)
EPIC_TO_MARKET = {
    "IX.D.DAX.IFG.IP": "DAX",
    "IX.D.SPTRD.IFE.IP": "SP500",
    "IX.D.NASDAQ.IFE.IP": "NASDAQ",
    "CS.D.EURUSD.MINI.IP": "EURUSD",
    "CS.D.GOLD.CFD.IP": "GOLD",
    "CF.D.LCO.USD.IP": "OIL",
}


def get_sentiment_signal(max_age_hours: int = 6) -> Optional[Dict]:
    """
    Load the latest sentiment signal.
    
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
    except Exception as e:
        print(f"Error reading sentiment signal: {e}")
        return None


def get_sentiment_report(max_age_hours: int = 6) -> Optional[Dict]:
    """
    Load the full sentiment report.
    
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
    except Exception as e:
        print(f"Error reading sentiment report: {e}")
        return None


def get_sentiment_for_epic(epic: str, max_age_hours: int = 6) -> Optional[Dict]:
    """
    Get sentiment specifically for an IG epic.
    
    Args:
        epic: IG epic code (e.g., "IX.D.DAX.IFG.IP")
        max_age_hours: Maximum age of signal
        
    Returns:
        Dict with market-specific sentiment, or None
    """
    signal = get_sentiment_signal(max_age_hours)
    if not signal:
        return None
    
    market = EPIC_TO_MARKET.get(epic)
    if not market:
        # Return overall sentiment if no specific market mapping
        return {
            "signal": signal.get("signal", 0),
            "confidence": signal.get("confidence", 0.5),
            "action": signal.get("action", "NEUTRAL"),
            "key_signals": signal.get("key_signals", []),
            "is_market_specific": False,
        }
    
    market_signals = signal.get("market_signals", {})
    if market in market_signals:
        return {
            "signal": market_signals[market]["signal"],
            "confidence": signal.get("confidence", 0.5),
            "action": market_signals[market]["action"],
            "key_signals": signal.get("key_signals", []),
            "is_market_specific": True,
            "market": market,
        }
    
    # Fall back to overall sentiment
    return {
        "signal": signal.get("signal", 0),
        "confidence": signal.get("confidence", 0.5),
        "action": signal.get("action", "NEUTRAL"),
        "key_signals": signal.get("key_signals", []),
        "is_market_specific": False,
        "requested_market": market,
    }


def sentiment_to_trading_score(sentiment_signal: Optional[Dict], default: float = 0.5) -> float:
    """
    Convert sentiment signal to 0-1 trading score.
    
    Args:
        sentiment_signal: Sentiment signal dict from get_sentiment_for_epic()
        default: Default value if no signal
        
    Returns:
        float: Score from 0.0 (bearish) to 1.0 (bullish)
    """
    if not sentiment_signal:
        return default
    
    # Convert -1 to 1 scale to 0 to 1 scale
    # signal = -1 -> 0.0, signal = 0 -> 0.5, signal = 1 -> 1.0
    raw_signal = sentiment_signal.get("signal", 0)
    confidence = sentiment_signal.get("confidence", 0.5)
    
    # Adjust based on confidence
    score = (raw_signal + 1) / 2  # Convert to 0-1
    score = 0.5 + (score - 0.5) * confidence  # Dampen by confidence
    
    return max(0.0, min(1.0, score))


def get_trading_context(epic: str = "") -> str:
    """
    Get a human-readable context string for news sentiment.
    
    Args:
        epic: Optional epic to get specific context for
        
    Returns:
        str: Context string describing current news sentiment.
    """
    if epic:
        sentiment = get_sentiment_for_epic(epic)
        if sentiment:
            market = EPIC_TO_MARKET.get(epic, "Overall")
            action = sentiment.get("action", "NEUTRAL")
            signal = sentiment.get("signal", 0)
            confidence = sentiment.get("confidence", 0)
            key_signals = sentiment.get("key_signals", [])
            
            context = f"{market} sentiment: {action} ({signal:+.2f}, confidence: {confidence:.0%})"
            if key_signals:
                context += f" | Key signals: {', '.join(key_signals[:3])}"
            return context
    
    # Get overall sentiment
    report = get_sentiment_report()
    if not report:
        return "No recent news sentiment data available."
    
    summary = report.get("summary", {})
    sentiment = summary.get("overall_sentiment", "NEUTRAL")
    strength = summary.get("strength", 0.5)
    top_signals = summary.get("top_signals", [])
    
    context_parts = [f"Current news sentiment: {sentiment} (strength: {strength:.2f})"]
    
    if top_signals:
        signals_str = ", ".join(top_signals[:3])
        context_parts.append(f"Key signals: {signals_str}")
    
    breakdown = summary.get("breakdown", {})
    if breakdown:
        total = breakdown.get("bullish", 0) + breakdown.get("bearish", 0) + breakdown.get("neutral", 0)
        if total > 0:
            context_parts.append(
                f"Articles: {breakdown.get('bullish', 0)} bullish, "
                f"{breakdown.get('bearish', 0)} bearish, "
                f"{breakdown.get('neutral', 0)} neutral"
            )
    
    return " | ".join(context_parts)


def should_trade_with_sentiment(epic: str, technical_signal: str, 
                                 sentiment_threshold: float = 0.3) -> Dict:
    """
    Determine if technical signal aligns with sentiment.
    
    Args:
        epic: IG epic code
        technical_signal: "BUY", "SELL", or "HOLD"
        sentiment_threshold: Minimum sentiment strength to consider
        
    Returns:
        Dict with decision and reasoning
    """
    sentiment = get_sentiment_for_epic(epic)
    
    if not sentiment:
        return {
            "should_trade": technical_signal in ["BUY", "SELL"],
            "reason": "No sentiment data available - relying on technical signal only",
            "sentiment_confidence": 0,
            "technical_signal": technical_signal,
            "sentiment_action": "UNKNOWN",
        }
    
    sentiment_action = sentiment.get("action", "NEUTRAL")
    sentiment_signal = sentiment.get("signal", 0)
    confidence = sentiment.get("confidence", 0)
    
    # Check alignment
    aligned = False
    
    if technical_signal == "BUY":
        if sentiment_action in ["BULLISH", "NEUTRAL"]:
            aligned = True
        elif sentiment_signal > -sentiment_threshold:  # Not strongly bearish
            aligned = True
    elif technical_signal == "SELL":
        if sentiment_action in ["BEARISH", "NEUTRAL"]:
            aligned = True
        elif sentiment_signal < sentiment_threshold:  # Not strongly bullish
            aligned = True
    
    if technical_signal == "HOLD":
        return {
            "should_trade": False,
            "reason": "Technical signal is HOLD",
            "sentiment_confidence": confidence,
            "technical_signal": technical_signal,
            "sentiment_action": sentiment_action,
            "sentiment_signal": sentiment_signal,
        }
    
    # Only trade if aligned or confidence is low
    if aligned or confidence < 0.4:
        should_trade = True
        reason = f"Technical {technical_signal} aligned with {sentiment_action} sentiment"
    else:
        should_trade = False
        reason = f"Technical {technical_signal} conflicts with {sentiment_action} sentiment (signal: {sentiment_signal:+.2f})"
    
    return {
        "should_trade": should_trade,
        "reason": reason,
        "sentiment_confidence": confidence,
        "technical_signal": technical_signal,
        "sentiment_action": sentiment_action,
        "sentiment_signal": sentiment_signal,
        "aligned": aligned,
    }


def get_all_market_sentiments() -> Dict[str, Dict]:
    """
    Get sentiment for all tracked markets.
    
    Returns:
        Dict mapping epic codes to sentiment data
    """
    signal = get_sentiment_signal()
    if not signal:
        return {}
    
    results = {}
    market_signals = signal.get("market_signals", {})
    overall_signal = signal.get("signal", 0)
    overall_confidence = signal.get("confidence", 0.5)
    key_signals = signal.get("key_signals", [])
    
    for epic, market in EPIC_TO_MARKET.items():
        if market in market_signals:
            results[epic] = {
                "signal": market_signals[market]["signal"],
                "action": market_signals[market]["action"],
                "confidence": overall_confidence,
                "key_signals": key_signals,
            }
        else:
            # Use overall sentiment
            results[epic] = {
                "signal": overall_signal,
                "action": signal.get("action", "NEUTRAL"),
                "confidence": overall_confidence,
                "key_signals": key_signals,
            }
    
    return results


def filter_epics_by_sentiment(epics: List[str], min_confidence: float = 0.3) -> List[str]:
    """
    Filter epics based on sentiment strength.
    
    Args:
        epics: List of epic codes to filter
        min_confidence: Minimum confidence level
        
    Returns:
        List of epics with strong sentiment signals
    """
    signal = get_sentiment_signal()
    if not signal or signal.get("confidence", 0) < min_confidence:
        return epics  # Return all if no strong sentiment
    
    market_signals = signal.get("market_signals", {})
    
    # Return epics with clear sentiment signals
    filtered = []
    for epic in epics:
        market = EPIC_TO_MARKET.get(epic)
        if market and market in market_signals:
            market_data = market_signals[market]
            if abs(market_data["signal"]) >= 0.2:  # Has meaningful signal
                filtered.append(epic)
        else:
            # Include epics without specific market data
            filtered.append(epic)
    
    return filtered if filtered else epics


# Example integration
def example_usage():
    """Example of how to integrate with trader.py"""
    print("=" * 50)
    print("Sentiment Integration Example")
    print("=" * 50)
    
    # Test DAX sentiment
    dax_epic = "IX.D.DAX.IFG.IP"
    sentiment = get_sentiment_for_epic(dax_epic)
    if sentiment:
        print(f"\nDAX Sentiment:")
        print(f"  Signal: {sentiment['signal']:+.3f}")
        print(f"  Action: {sentiment['action']}")
        print(f"  Confidence: {sentiment['confidence']:.1%}")
        print(f"  Context: {get_trading_context(dax_epic)}")
        print(f"  Trading score: {sentiment_to_trading_score(sentiment):.3f}")
    else:
        print("\nNo DAX sentiment available")
    
    # Test trading decision
    print("\n" + "=" * 50)
    print("Trading Decision Example")
    print("=" * 50)
    
    for tech_signal in ["BUY", "SELL", "HOLD"]:
        decision = should_trade_with_sentiment(dax_epic, tech_signal)
        print(f"\nTechnical: {tech_signal}")
        print(f"  Should trade: {decision['should_trade']}")
        print(f"  Reason: {decision['reason']}")
    
    # Show all markets
    print("\n" + "=" * 50)
    print("All Market Sentiments")
    print("=" * 50)
    all_sentiments = get_all_market_sentiments()
    for epic, data in all_sentiments.items():
        print(f"{epic}: {data['action']} ({data['signal']:+.2f})")


if __name__ == "__main__":
    example_usage()