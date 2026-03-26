#!/usr/bin/env python3
"""
Decision Engine for Crypto Trading
Combines technical indicators with news sentiment for trading signals.

Integrates with:
- Binance API for market data (klines, price, volume)
- News sentiment from crypto_scraper
- Existing trader.py infrastructure
"""

import json
import httpx
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from decimal import Decimal

# Import sentiment integration from same directory
try:
    from sentiment_integration import (
        get_sentiment_signal,
        get_sentiment_report,
        llm_sentiment_from_news,
        get_trading_context,
        should_adjust_position
    )
    SENTIMENT_AVAILABLE = True
except ImportError:
    SENTIMENT_AVAILABLE = False


class Signal(Enum):
    STRONG_BUY = 2
    BUY = 1
    NEUTRAL = 0
    SELL = -1
    STRONG_SELL = -2


@dataclass
class MarketIndicators:
    """Container for technical indicators."""
    price: float
    price_change_24h: float
    volume_24h: float
    ema_fast: float
    ema_slow: float
    rsi: float
    bollinger_upper: float
    bollinger_lower: float
    bollinger_mid: float
    volume_trend: str  # "increasing", "decreasing", "stable"
    trend: str  # "UP", "DOWN", "SIDEWAYS"


@dataclass
class SentimentData:
    """Container for sentiment data."""
    score: float  # -1 to 1
    confidence: float
    action: str
    key_signals: List[str]
    articles_analyzed: int


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
    position_action: Optional[str] = None  # "enter_long", "exit_long", "enter_short", "exit_short"


class BinanceClient:
    """Simple Binance API client for market data."""
    
    BASE_URL = "https://api.binance.com"
    
    def __init__(self):
        self.client = httpx.Client(timeout=15)
    
    def get_klines(self, symbol: str, interval: str = "1h", limit: int = 50) -> List[Dict]:
        """Get candlestick data."""
        try:
            r = self.client.get(
                f"{self.BASE_URL}/api/v3/klines",
                params={"symbol": symbol, "interval": interval, "limit": limit}
            )
            r.raise_for_status()
            data = r.json()
            return [{
                "t": k[0], "o": float(k[1]), "h": float(k[2]), 
                "l": float(k[3]), "c": float(k[4]), "v": float(k[5])
            } for k in data]
        except Exception as e:
            print(f"Error fetching klines: {e}")
            return []
    
    def get_ticker_24h(self, symbol: str) -> Dict:
        """Get 24hr ticker data."""
        try:
            r = self.client.get(
                f"{self.BASE_URL}/api/v3/ticker/24hr",
                params={"symbol": symbol}
            )
            r.raise_for_status()
            data = r.json()
            return {
                "price": float(data["lastPrice"]),
                "price_change": float(data["priceChange"]),
                "price_change_pct": float(data["priceChangePercent"]),
                "volume": float(data["volume"]),
                "quote_volume": float(data["quoteVolume"])
            }
        except Exception as e:
            print(f"Error fetching ticker: {e}")
            return {}
    
    def close(self):
        self.client.close()


class TechnicalAnalysis:
    """Technical indicator calculations."""
    
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
        sma = sum(prices[-period:]) / period
        variance = sum((p - sma) ** 2 for p in prices[-period:]) / period
        std = variance ** 0.5
        return sma - std_mult * std, sma, sma + std_mult * std
    
    @staticmethod
    def volume_trend(volumes: List[float]) -> str:
        """Determine volume trend."""
        if len(volumes) < 5:
            return "stable"
        recent_avg = sum(volumes[-3:]) / 3
        older_avg = sum(volumes[-5:-2]) / 3
        if recent_avg > older_avg * 1.2:
            return "increasing"
        elif recent_avg < older_avg * 0.8:
            return "decreasing"
        return "stable"


class DecisionEngine:
    """
    Main decision engine combining technical and sentiment analysis.
    
    Weights (configurable):
    - Technical: 60%
    - Sentiment: 40%
    
    Technical factors:
    - EMA crossover (fast/slow)
    - RSI levels
    - Bollinger Band position
    - Volume trend
    - 24h price change
    
    Sentiment factors:
    - News sentiment score
    - Confidence level
    - Key trading signals
    """
    
    # Configuration
    TECHNICAL_WEIGHT = 0.60
    SENTIMENT_WEIGHT = 0.40
    
    # Technical thresholds
    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70
    EMA_BULL_THRESHOLD = 0.02  # 2% above slow EMA
    EMA_BEAR_THRESHOLD = -0.02  # 2% below slow EMA
    
    def __init__(self, symbol: str = "BTCUSDT"):
        self.symbol = symbol
        self.client = BinanceClient()
        self.ta = TechnicalAnalysis()
    
    def fetch_market_indicators(self, interval: str = "1h", limit: int = 50) -> MarketIndicators:
        """Fetch and calculate technical indicators."""
        # Get klines
        klines = self.client.get_klines(self.symbol, interval, limit)
        if not klines:
            raise ValueError(f"No kline data for {self.symbol}")
        
        prices = [k["c"] for k in klines]
        volumes = [k["v"] for k in klines]
        
        # Get 24h ticker
        ticker = self.client.get_ticker_24h(self.symbol)
        current_price = ticker.get("price", prices[-1])
        
        # Calculate indicators
        ema_fast = self.ta.ema(prices, 9)
        ema_slow = self.ta.ema(prices, 20)
        rsi = self.ta.rsi(prices, 14)
        bb_lower, bb_mid, bb_upper = self.ta.bollinger(prices, 20, 2)
        volume_trend = self.ta.volume_trend(volumes)
        
        # Determine trend
        ema_diff_pct = (ema_fast - ema_slow) / ema_slow
        if ema_diff_pct > 0.01 and current_price > ema_fast:
            trend = "UP"
        elif ema_diff_pct < -0.01 and current_price < ema_fast:
            trend = "DOWN"
        else:
            trend = "SIDEWAYS"
        
        return MarketIndicators(
            price=current_price,
            price_change_24h=ticker.get("price_change_pct", 0),
            volume_24h=ticker.get("volume", 0),
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            rsi=rsi,
            bollinger_upper=bb_upper,
            bollinger_lower=bb_lower,
            bollinger_mid=bb_mid,
            volume_trend=volume_trend,
            trend=trend
        )
    
    def get_sentiment_data(self, max_age_hours: int = 6) -> SentimentData:
        """Get news sentiment data."""
        if not SENTIMENT_AVAILABLE:
            return SentimentData(
                score=0, confidence=0.5, action="NEUTRAL",
                key_signals=[], articles_analyzed=0
            )
        
        signal = get_sentiment_signal(max_age_hours)
        if not signal:
            return SentimentData(
                score=0, confidence=0.5, action="NEUTRAL",
                key_signals=[], articles_analyzed=0
            )
        
        return SentimentData(
            score=signal.get("signal", 0),
            confidence=signal.get("confidence", 0.5),
            action=signal.get("action", "NEUTRAL"),
            key_signals=signal.get("key_signals", []),
            articles_analyzed=signal.get("articles_analyzed", 0)
        )
    
    def calculate_technical_score(self, indicators: MarketIndicators) -> Tuple[float, Dict]:
        """
        Calculate technical score from -1 to 1.
        
        Returns:
            Tuple of (score, breakdown_dict)
        """
        scores = []
        breakdown = {}
        
        # 1. EMA Crossover (weight: 30%)
        ema_diff_pct = (indicators.ema_fast - indicators.ema_slow) / indicators.ema_slow
        if ema_diff_pct > self.EMA_BULL_THRESHOLD:
            ema_score = min(1.0, ema_diff_pct * 10)  # Scale up small differences
        elif ema_diff_pct < self.EMA_BEAR_THRESHOLD:
            ema_score = max(-1.0, ema_diff_pct * 10)
        else:
            ema_score = ema_diff_pct * 20  # Small movements near crossover
        
        scores.append(("ema_crossover", ema_score, 0.30))
        breakdown["ema_crossover"] = {
            "score": round(ema_score, 3),
            "fast": round(indicators.ema_fast, 2),
            "slow": round(indicators.ema_slow, 2),
            "diff_pct": round(ema_diff_pct * 100, 2)
        }
        
        # 2. RSI (weight: 25%)
        if indicators.rsi >= self.RSI_OVERBOUGHT:
            rsi_score = -1.0 * (indicators.rsi - self.RSI_OVERBOUGHT) / (100 - self.RSI_OVERBOUGHT)
        elif indicators.rsi <= self.RSI_OVERSOLD:
            rsi_score = 1.0 * (self.RSI_OVERSOLD - indicators.rsi) / self.RSI_OVERSOLD
        else:
            # Neutral zone - score based on direction potential
            rsi_score = (indicators.rsi - 50) / 50 * 0.5  # Max 0.5 in neutral
        
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
            # Position within bands: -1 at lower band, +1 at upper band
            bb_position = (indicators.price - indicators.bollinger_lower) / bb_range
            bb_position = max(0, min(1, bb_position))  # Clamp to 0-1
            # Score: near lower band = bullish (potential bounce), near upper = bearish
            bb_score = (0.5 - bb_position) * 2  # -1 to 1
        
        scores.append(("bollinger", bb_score, 0.15))
        breakdown["bollinger"] = {
            "score": round(bb_score, 3),
            "position": round((indicators.price - indicators.bollinger_lower) / bb_range * 100, 1) if bb_range else 50,
            "upper": round(indicators.bollinger_upper, 2),
            "lower": round(indicators.bollinger_lower, 2)
        }
        
        # 4. Volume Trend (weight: 15%)
        volume_scores = {"increasing": 0.3, "decreasing": -0.2, "stable": 0}
        vol_score = volume_scores.get(indicators.volume_trend, 0)
        
        # Boost if price moving in trend direction with volume
        if indicators.volume_trend == "increasing":
            if indicators.trend == "UP":
                vol_score = 0.5  # Strong bullish signal
            elif indicators.trend == "DOWN":
                vol_score = -0.5  # Strong bearish signal
        
        scores.append(("volume", vol_score, 0.10))
        breakdown["volume"] = {
            "score": round(vol_score, 3),
            "trend": indicators.volume_trend,
            "24h_volume": round(indicators.volume_24h, 0)
        }
        
        # 5. Price Change 24h (weight: 10%)
        price_score = max(-1, min(1, indicators.price_change_24h / 10))  # Scale: 10% = score 1
        scores.append(("price_change", price_score, 0.10))
        breakdown["price_change"] = {
            "score": round(price_score, 3),
            "change_pct": round(indicators.price_change_24h, 2)
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
            "articles_analyzed": sentiment.articles_analyzed
        }
        
        # Adjust score based on confidence
        # Low confidence dampens the impact
        adjusted_score = sentiment.score * sentiment.confidence
        
        # Boost if multiple key signals align
        signal_boost = 0
        bullish_signals = ["bottom", "breakout", "etf", "institutional", "support"]
        bearish_signals = ["resistance", "hacked", "sec", "regulation", "ban"]
        
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
        # Weighted combination
        combined = (
            technical_score * self.TECHNICAL_WEIGHT +
            sentiment_score * self.SENTIMENT_WEIGHT
        )
        
        # Determine signal strength
        if combined >= 0.5:
            signal = Signal.STRONG_BUY
        elif combined >= 0.2:
            signal = Signal.BUY
        elif combined <= -0.5:
            signal = Signal.STRONG_SELL
        elif combined <= -0.2:
            signal = Signal.SELL
        else:
            signal = Signal.NEUTRAL
        
        return signal, combined
    
    def analyze(self, interval: str = "1h") -> TradingSignal:
        """
        Run full analysis and generate trading signal.
        
        Args:
            interval: Kline interval for technical analysis
            
        Returns:
            TradingSignal with complete analysis
        """
        # Fetch data
        try:
            indicators = self.fetch_market_indicators(interval)
        except Exception as e:
            print(f"Error fetching market data: {e}")
            return TradingSignal(
                signal=Signal.NEUTRAL,
                strength=0,
                confidence=0,
                reason=f"Error fetching market data: {e}",
                technical_score=0,
                sentiment_score=0,
                indicators={},
                should_trade=False
            )
        
        sentiment = self.get_sentiment_data()
        
        # Calculate scores
        technical_score, tech_breakdown = self.calculate_technical_score(indicators)
        sentiment_score, sent_breakdown = self.calculate_sentiment_score(sentiment)
        
        # Generate signal
        signal, combined_strength = self.generate_signal(technical_score, sentiment_score)
        
        # Determine if we should trade
        should_trade = False
        position_action = None
        
        if signal in [Signal.STRONG_BUY, Signal.BUY]:
            if technical_score > 0.3 and sentiment_score > -0.2:
                should_trade = True
                position_action = "enter_long" if signal == Signal.STRONG_BUY else "consider_long"
        elif signal in [Signal.STRONG_SELL, Signal.SELL]:
            if technical_score < -0.3 and sentiment_score < 0.2:
                should_trade = True
                position_action = "exit_long" if signal == Signal.STRONG_SELL else "consider_exit"
        
        # Build reason
        reasons = []
        if tech_breakdown.get("ema_crossover", {}).get("score", 0) > 0.2:
            reasons.append("Bullish EMA crossover")
        elif tech_breakdown.get("ema_crossover", {}).get("score", 0) < -0.2:
            reasons.append("Bearish EMA crossover")
        
        rsi_zone = tech_breakdown.get("rsi", {}).get("zone", "neutral")
        if rsi_zone == "oversold":
            reasons.append("RSI oversold")
        elif rsi_zone == "overbought":
            reasons.append("RSI overbought")
        
        if sentiment.key_signals:
            reasons.append(f"News signals: {', '.join(sentiment.key_signals[:3])}")
        
        if indicators.trend != "SIDEWAYS":
            reasons.append(f"Trend: {indicators.trend}")
        
        reason = " | ".join(reasons) if reasons else signal.name
        
        # Calculate confidence based on alignment
        alignment = 1 - abs(technical_score - sentiment_score) / 2  # Higher when aligned
        confidence = (sentiment.confidence * 0.5 + alignment * 0.5)
        
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
    
    def close(self):
        """Cleanup."""
        self.client.close()


def format_signal_report(signal: TradingSignal, symbol: str) -> str:
    """Format signal as human-readable report."""
    lines = [
        "=" * 60,
        f"📊 DECISION ENGINE REPORT: {symbol}",
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
            lines.append(f"   EMA: Fast {ema['fast']:.0f} vs Slow {ema['slow']:.0f} ({ema['diff_pct']:+.2f}%)")
        if "rsi" in tech:
            rsi = tech["rsi"]
            lines.append(f"   RSI: {rsi['value']:.1f} ({rsi['zone']})")
        if "bollinger" in tech:
            bb = tech["bollinger"]
            lines.append(f"   BB Position: {bb['position']:.1f}% within bands")
        if "volume" in tech:
            vol = tech["volume"]
            lines.append(f"   Volume: {vol['trend']} ({vol['24h_volume']:,.0f})")
        if "price_change" in tech:
            pc = tech["price_change"]
            lines.append(f"   24h Change: {pc['change_pct']:+.2f}%")
    
    lines.extend([
        "",
        "📰 NEWS SENTIMENT:",
        f"   Score: {signal.sentiment_score:+.3f}",
    ])
    
    sent = signal.indicators.get("sentiment", {})
    if sent:
        lines.append(f"   Raw Score: {sent.get('raw_score', 0):+.3f}")
        lines.append(f"   Confidence: {sent.get('confidence', 0):.1%}")
        if sent.get("key_signals"):
            lines.append(f"   Key Signals: {', '.join(sent['key_signals'][:5])}")
        lines.append(f"   Articles Analyzed: {sent.get('articles_analyzed', 0)}")
    
    lines.extend([
        "",
        f"💡 REASON: {signal.reason}",
        "",
        f"🚦 SHOULD TRADE: {'✅ YES' if signal.should_trade else '❌ NO'}",
        "=" * 60
    ])
    
    return "\n".join(lines)


# Main execution
if __name__ == "__main__":
    import sys
    
    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    interval = sys.argv[2] if len(sys.argv) > 2 else "1h"
    
    print(f"\n🔍 Analyzing {symbol} ({interval} timeframe)...\n")
    
    engine = DecisionEngine(symbol)
    try:
        signal = engine.analyze(interval)
        print(format_signal_report(signal, symbol))
        
        # Save to JSON for bot integration
        output = {
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
        
        output_path = Path(__file__).parent / "decision_signal.json"
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)
        
        print(f"\n💾 Signal saved to {output_path}")
        
    finally:
        engine.close()