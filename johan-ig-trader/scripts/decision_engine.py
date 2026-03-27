#!/usr/bin/env python3
"""
Decision Engine for IG Trading Bot
Combines technical indicators with news sentiment for trading signals.

Integrates with:
- IG API for market data (prices, positions)
- News sentiment from sentiment_integration
- Existing trader.py infrastructure
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from decimal import Decimal

# Import sentiment integration
try:
    from sentiment_integration import (
        get_sentiment_for_epic,
        sentiment_to_trading_score,
        get_trading_context,
        should_trade_with_sentiment,
        get_all_market_sentiments,
    )
    SENTIMENT_AVAILABLE = True
except ImportError:
    SENTIMENT_AVAILABLE = False
    print("Warning: sentiment_integration not available")


class Signal(Enum):
    STRONG_BUY = 2
    BUY = 1
    NEUTRAL = 0
    SELL = -1
    STRONG_SELL = -2


@dataclass
class TechnicalIndicators:
    """Container for technical indicators."""
    price: float
    ema_fast: float
    ema_slow: float
    rsi: float
    bollinger_upper: float
    bollinger_lower: float
    bollinger_mid: float
    trend: str  # "UP", "DOWN", "SIDEWAYS"
    volume_trend: str  # "increasing", "decreasing", "stable"


@dataclass
class SentimentData:
    """Container for sentiment data."""
    score: float  # -1 to 1
    confidence: float
    action: str
    key_signals: List[str]


@dataclass
class TradingSignal:
    """Final trading signal output."""
    signal: Signal
    strength: float
    confidence: float
    reason: str
    technical_score: float
    sentiment_score: float
    indicators: Dict
    should_trade: bool
    position_action: Optional[str] = None


class TechnicalAnalysis:
    """Technical indicator calculations for IG data."""
    
    @staticmethod
    def ema(prices: List[float], period: int) -> float:
        """Calculate EMA."""
        if len(prices) < period:
            return prices[-1] if prices else 0
        k = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        for p in prices[period:]:
            ema = p * k + ema * (1 - k)
        return ema
    
    @staticmethod
    def rsi(prices: List[float], period: int = 14) -> float:
        """Calculate RSI."""
        if len(prices) < period + 1:
            return 50
        deltas = [prices[i+1] - prices[i] for i in range(len(prices)-1)]
        gains = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def bollinger(prices: List[float], period: int = 20, std_mult: float = 2) -> Tuple[float, float, float]:
        """Calculate Bollinger Bands."""
        if len(prices) < period:
            period = len(prices)
        if period == 0:
            return 0, 0, 0
        sma = sum(prices[-period:]) / period
        variance = sum((p - sma) ** 2 for p in prices[-period:]) / period
        std = variance ** 0.5
        return sma - std_mult * std, sma, sma + std_mult * std
    
    @staticmethod
    def calculate_indicators(prices: List[Dict]) -> TechnicalIndicators:
        """Calculate all technical indicators from IG price data."""
        closes = [p.get("closePrice", {}).get("bid", 0) for p in prices if p.get("closePrice")]
        if len(closes) < 20:
            # Return minimal indicators if insufficient data
            last_price = closes[-1] if closes else 0
            return TechnicalIndicators(
                price=last_price,
                ema_fast=last_price,
                ema_slow=last_price,
                rsi=50,
                bollinger_upper=last_price * 1.02,
                bollinger_lower=last_price * 0.98,
                bollinger_mid=last_price,
                trend="SIDEWAYS",
                volume_trend="stable"
            )
        
        current_price = closes[-1]
        
        # Calculate EMAs
        ema_fast = TechnicalAnalysis.ema(closes, 9)
        ema_slow = TechnicalAnalysis.ema(closes, 20)
        
        # Calculate RSI
        rsi = TechnicalAnalysis.rsi(closes, 14)
        
        # Calculate Bollinger Bands
        bb_lower, bb_mid, bb_upper = TechnicalAnalysis.bollinger(closes, 20, 2)
        
        # Determine trend
        ema_diff_pct = (ema_fast - ema_slow) / ema_slow if ema_slow else 0
        if ema_diff_pct > 0.005 and current_price > ema_fast:
            trend = "UP"
        elif ema_diff_pct < -0.005 and current_price < ema_fast:
            trend = "DOWN"
        else:
            trend = "SIDEWAYS"
        
        # Volume trend (using price movement as proxy since IG doesn't provide volume directly)
        if len(closes) >= 5:
            recent_range = max(closes[-3:]) - min(closes[-3:])
            older_range = max(closes[-5:-2]) - min(closes[-5:-2])
            if recent_range > older_range * 1.2:
                volume_trend = "increasing"
            elif recent_range < older_range * 0.8:
                volume_trend = "decreasing"
            else:
                volume_trend = "stable"
        else:
            volume_trend = "stable"
        
        return TechnicalIndicators(
            price=current_price,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            rsi=rsi,
            bollinger_upper=bb_upper,
            bollinger_lower=bb_lower,
            bollinger_mid=bb_mid,
            trend=trend,
            volume_trend=volume_trend
        )


class DecisionEngine:
    """
    Main decision engine combining technical and sentiment analysis.
    
    Weights (configurable via environment):
    - Technical: 60%
    - Sentiment: 40%
    
    Technical factors:
    - EMA crossover (fast/slow)
    - RSI levels
    - Bollinger Band position
    - Trend direction
    
    Sentiment factors:
    - News sentiment score
    - Confidence level
    - Key trading signals
    """
    
    # Configuration
    TECHNICAL_WEIGHT = 0.60
    SENTIMENT_WEIGHT = 0.40
    MIN_CONFIDENCE = 0.3
    
    # Technical thresholds
    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70
    EMA_BULL_THRESHOLD = 0.01  # 1% above slow EMA
    EMA_BEAR_THRESHOLD = -0.01  # 1% below slow EMA
    
    def __init__(self, epic: str = "IX.D.DAX.IFG.IP"):
        self.epic = epic
        self.ta = TechnicalAnalysis()
    
    def get_sentiment_data(self) -> SentimentData:
        """Get news sentiment data for this epic."""
        if not SENTIMENT_AVAILABLE:
            return SentimentData(score=0, confidence=0, action="NEUTRAL", key_signals=[])
        
        sentiment = get_sentiment_for_epic(self.epic)
        if not sentiment:
            return SentimentData(score=0, confidence=0, action="NEUTRAL", key_signals=[])
        
        return SentimentData(
            score=sentiment.get("signal", 0),
            confidence=sentiment.get("confidence", 0),
            action=sentiment.get("action", "NEUTRAL"),
            key_signals=sentiment.get("key_signals", [])
        )
    
    def calculate_technical_score(self, indicators: TechnicalIndicators) -> Tuple[float, Dict]:
        """
        Calculate technical score from -1 to 1.
        
        Returns:
            Tuple of (score, breakdown_dict)
        """
        scores = []
        breakdown = {}
        
        # 1. EMA Crossover (weight: 35%)
        ema_diff_pct = (indicators.ema_fast - indicators.ema_slow) / indicators.ema_slow if indicators.ema_slow else 0
        if ema_diff_pct > self.EMA_BULL_THRESHOLD:
            ema_score = min(1.0, ema_diff_pct * 20)
        elif ema_diff_pct < self.EMA_BEAR_THRESHOLD:
            ema_score = max(-1.0, ema_diff_pct * 20)
        else:
            ema_score = ema_diff_pct * 50
        
        scores.append(("ema_crossover", ema_score, 0.35))
        breakdown["ema_crossover"] = {
            "score": round(ema_score, 3),
            "fast": round(indicators.ema_fast, 2),
            "slow": round(indicators.ema_slow, 2),
            "diff_pct": round(ema_diff_pct * 100, 3)
        }
        
        # 2. RSI (weight: 25%)
        if indicators.rsi >= self.RSI_OVERBOUGHT:
            rsi_score = -1.0 * (indicators.rsi - self.RSI_OVERBOUGHT) / (100 - self.RSI_OVERBOUGHT)
        elif indicators.rsi <= self.RSI_OVERSOLD:
            rsi_score = 1.0 * (self.RSI_OVERSOLD - indicators.rsi) / self.RSI_OVERSOLD
        else:
            rsi_score = (indicators.rsi - 50) / 50 * 0.3
        
        scores.append(("rsi", rsi_score, 0.25))
        breakdown["rsi"] = {
            "score": round(rsi_score, 3),
            "value": round(indicators.rsi, 1),
            "zone": "overbought" if indicators.rsi >= 70 else "oversold" if indicators.rsi <= 30 else "neutral"
        }
        
        # 3. Bollinger Band Position (weight: 20%)
        bb_range = indicators.bollinger_upper - indicators.bollinger_lower
        if bb_range == 0:
            bb_score = 0
        else:
            bb_position = (indicators.price - indicators.bollinger_lower) / bb_range
            bb_position = max(0, min(1, bb_position))
            bb_score = (0.5 - bb_position) * 2
        
        scores.append(("bollinger", bb_score, 0.20))
        breakdown["bollinger"] = {
            "score": round(bb_score, 3),
            "position": round(bb_position * 100, 1) if bb_range else 50,
            "upper": round(indicators.bollinger_upper, 2),
            "lower": round(indicators.bollinger_lower, 2)
        }
        
        # 4. Trend (weight: 20%)
        trend_scores = {"UP": 0.5, "DOWN": -0.5, "SIDEWAYS": 0}
        trend_score = trend_scores.get(indicators.trend, 0)
        
        if indicators.trend == "UP" and ema_diff_pct > 0:
            trend_score = 0.7
        elif indicators.trend == "DOWN" and ema_diff_pct < 0:
            trend_score = -0.7
        
        scores.append(("trend", trend_score, 0.20))
        breakdown["trend"] = {
            "score": round(trend_score, 3),
            "direction": indicators.trend,
            "volume": indicators.volume_trend
        }
        
        # Calculate weighted average
        total_weight = sum(s[2] for s in scores)
        technical_score = sum(s[1] * s[2] for s in scores) / total_weight
        
        return technical_score, breakdown
    
    def calculate_sentiment_score(self, sentiment: SentimentData) -> Tuple[float, Dict]:
        """
        Calculate sentiment score impact.
        
        Returns:
            Tuple of (score, breakdown_dict)
        """
        breakdown = {
            "raw_score": sentiment.score,
            "confidence": sentiment.confidence,
            "action": sentiment.action,
            "key_signals": sentiment.key_signals,
        }
        
        # Adjust score based on confidence
        adjusted_score = sentiment.score * sentiment.confidence
        
        # Boost if multiple key signals align
        signal_boost = 0
        bullish_signals = ["rally", "surge", "strong", "breakout", "support", "bullish", "buy"]
        bearish_signals = ["sell-off", "correction", "bearish", "resistance", "weak", "recession"]
        
        for signal in sentiment.key_signals:
            if signal in bullish_signals:
                signal_boost += 0.1
            elif signal in bearish_signals:
                signal_boost -= 0.1
        
        final_score = max(-1, min(1, adjusted_score + signal_boost))
        
        breakdown["adjusted_score"] = round(final_score, 3)
        breakdown["signal_boost"] = round(signal_boost, 3)
        
        return final_score, breakdown
    
    def generate_signal(self, technical_score: float, sentiment_score: float) -> Tuple[Signal, float]:
        """
        Generate final trading signal.
        
        Returns:
            Tuple of (Signal enum, combined_strength)
        """
        combined = (
            technical_score * self.TECHNICAL_WEIGHT +
            sentiment_score * self.SENTIMENT_WEIGHT
        )
        
        if combined >= 0.4:
            signal = Signal.STRONG_BUY
        elif combined >= 0.15:
            signal = Signal.BUY
        elif combined <= -0.4:
            signal = Signal.STRONG_SELL
        elif combined <= -0.15:
            signal = Signal.SELL
        else:
            signal = Signal.NEUTRAL
        
        return signal, combined
    
    def analyze(self, prices: List[Dict]) -> TradingSignal:
        """
        Run full analysis and generate trading signal.
        
        Args:
            prices: List of IG price data dicts
            
        Returns:
            TradingSignal with complete analysis
        """
        # Calculate technical indicators
        indicators = self.ta.calculate_indicators(prices)
        
        # Get sentiment data
        sentiment = self.get_sentiment_data()
        
        # Calculate scores
        technical_score, tech_breakdown = self.calculate_technical_score(indicators)
        sentiment_score, sent_breakdown = self.calculate_sentiment_score(sentiment)
        
        # Generate signal
        signal, combined_strength = self.generate_signal(technical_score, sentiment_score)
        
        # Determine if we should trade (alignment check)
        should_trade = False
        position_action = None
        
        if signal in [Signal.STRONG_BUY, Signal.BUY]:
            # Require technical to be positive and sentiment not strongly negative
            if technical_score > 0.2 and sentiment_score > -0.3:
                should_trade = True
                position_action = "enter_long" if signal == Signal.STRONG_BUY else "consider_long"
            elif technical_score > 0.1 and sentiment.confidence < 0.4:
                # Low sentiment confidence, rely more on technical
                should_trade = True
                position_action = "enter_long_weak"
        elif signal in [Signal.STRONG_SELL, Signal.SELL]:
            # For IG CFDs, SELL can mean exit long OR enter short
            if technical_score < -0.2 and sentiment_score < 0.3:
                should_trade = True
                position_action = "exit_long" if signal == Signal.STRONG_SELL else "consider_exit"
            elif technical_score < -0.1 and sentiment.confidence < 0.4:
                should_trade = True
                position_action = "exit_long_weak"
        
        # Build reason
        reasons = []
        
        # Technical reasons
        if tech_breakdown.get("ema_crossover", {}).get("score", 0) > 0.15:
            reasons.append("Bullish EMA crossover")
        elif tech_breakdown.get("ema_crossover", {}).get("score", 0) < -0.15:
            reasons.append("Bearish EMA crossover")
        
        rsi_zone = tech_breakdown.get("rsi", {}).get("zone", "neutral")
        if rsi_zone == "oversold":
            reasons.append("RSI oversold")
        elif rsi_zone == "overbought":
            reasons.append("RSI overbought")
        
        if indicators.trend != "SIDEWAYS":
            reasons.append(f"Trend: {indicators.trend}")
        
        # Sentiment reasons
        if sentiment.key_signals:
            reasons.append(f"News: {', '.join(sentiment.key_signals[:2])}")
        
        if sentiment.action != "NEUTRAL":
            reasons.append(f"Sentiment: {sentiment.action}")
        
        reason = " | ".join(reasons) if reasons else signal.name
        
        # Calculate confidence
        alignment = 1 - abs(technical_score - sentiment_score) / 2
        confidence = (sentiment.confidence * 0.4 + alignment * 0.6)
        
        return TradingSignal(
            signal=signal,
            strength=combined_strength,
            confidence=confidence,
            reason=reason,
            technical_score=technical_score,
            sentiment_score=sentiment_score,
            indicators={
                "price": indicators.price,
                "trend": indicators.trend,
                "technical": tech_breakdown,
                "sentiment": sent_breakdown
            },
            should_trade=should_trade,
            position_action=position_action
        )


def format_signal_report(signal: TradingSignal, epic: str) -> str:
    """Format signal as human-readable report."""
    lines = [
        "=" * 60,
        f"📊 DECISION ENGINE REPORT: {epic}",
        "=" * 60,
        "",
        f"🎯 SIGNAL: {signal.signal.name}",
        f"   Strength: {signal.strength:+.3f}",
        f"   Confidence: {signal.confidence:.1%}",
        f"   Action: {signal.position_action or 'HOLD'}",
        "",
        "📈 TECHNICAL ANALYSIS:",
        f"   Score: {signal.technical_score:+.3f}",
    ]
    
    tech = signal.indicators.get("technical", {})
    if tech:
        if "ema_crossover" in tech:
            ema = tech["ema_crossover"]
            lines.append(f"   EMA: Fast {ema['fast']:.0f} vs Slow {ema['slow']:.0f} ({ema['diff_pct']:+.3f}%)")
        if "rsi" in tech:
            rsi = tech["rsi"]
            lines.append(f"   RSI: {rsi['value']:.1f} ({rsi['zone']})")
        if "bollinger" in tech:
            bb = tech["bollinger"]
            lines.append(f"   BB Position: {bb['position']:.1f}%")
        if "trend" in tech:
            trend = tech["trend"]
            lines.append(f"   Trend: {trend['direction']}, Vol: {trend['volume']}")
    
    lines.extend([
        "",
        "📰 NEWS SENTIMENT:",
        f"   Score: {signal.sentiment_score:+.3f}",
    ])
    
    sent = signal.indicators.get("sentiment", {})
    if sent:
        lines.append(f"   Raw: {sent.get('raw_score', 0):+.3f}")
        lines.append(f"   Confidence: {sent.get('confidence', 0):.1%}")
        if sent.get("key_signals"):
            lines.append(f"   Signals: {', '.join(sent['key_signals'][:3])}")
    
    lines.extend([
        "",
        f"💡 REASON: {signal.reason}",
        "",
        f"🚦 SHOULD TRADE: {'✅ YES' if signal.should_trade else '❌ NO'}",
        "=" * 60
    ])
    
    return "\n".join(lines)


def save_signal_json(signal: TradingSignal, epic: str):
    """Save signal to JSON for bot integration."""
    SCRIPT_DIR = Path(__file__).parent
    output = {
        "epic": epic,
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
    
    output_path = SCRIPT_DIR / f"decision_{epic.replace('.', '_')}.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    
    return output_path


# Main execution
if __name__ == "__main__":
    import sys
    
    epic = sys.argv[1] if len(sys.argv) > 1 else "IX.D.DAX.IFG.IP"
    
    print(f"\n🔍 Testing Decision Engine for {epic}...")
    print("Note: This requires price data from IG API")
    print("\nTo use in trader.py:")
    print("  from decision_engine import DecisionEngine, TradingSignal, Signal")
    print("  engine = DecisionEngine(epic)")
    print("  signal = engine.analyze(prices)")
    print("  if signal.should_trade and signal.signal in [Signal.STRONG_BUY, Signal.BUY]:")
    print("      # Execute buy...")